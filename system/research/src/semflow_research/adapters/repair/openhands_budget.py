"""Translate SDK call handshakes into the existing durable execution journal."""

import json
import time
from uuid import UUID

from semflow_contracts.errors import ResearchError

from semflow_research.runtime.calls import CallJournal


class WorkerBudget:
    def __init__(self, context, directory):
        self.context, self.directory = context, directory / "calls"
        self.journal = CallJournal(
            context.executions, context.execution_id, context.execution_id
        )
        self.active = set()
        started = next(
            event.occurred_at.timestamp()
            for event in context.executions.events(context.execution_id)
            if event.phase_code == "execution_started"
        )
        self.deadline = (
            started + context.spec.policy.max_seconds
            if context.spec.policy.max_seconds
            else None
        )

    def poll(self):
        if self.deadline is not None and time.time() >= self.deadline:
            raise ResearchError(
                "budget_exhausted",
                "OpenHands exhausted the shared execution wall-time budget",
            )
        for path in sorted(self.directory.glob("*.request.json")):
            response = path.with_name(path.name.replace(".request.", ".response."))
            if response.exists():
                continue
            # WIRE-RECV:research.openhands — peer: engines.openhands.budget.guarded.
            # AGENT: worker requests never own the budget; enforce the same
            # global and method caps as semantic model calls and retain unknowns.
            value = json.loads(path.read_text())
            call_id = UUID(value["call_id"])
            try:
                if value["action"] == "reserve":
                    limit = self.context.spec.inputs.method_policy.model_call_limit
                    if limit and len(self.journal.receipts()) >= limit:
                        raise ResearchError(
                            "budget_exhausted", "Repair model-call limit exhausted"
                        )
                    minimum = self.context.spec.inputs.openhands.output_tokens + 8192
                    tokens = value["reserved_tokens"]
                    if type(tokens) is not int or tokens < minimum:
                        raise ResearchError(
                            "invalid_contract", "Worker token reservation is invalid"
                        )
                    remaining = self.journal.reserve(
                        call_id,
                        input_digest=value["input_digest"],
                        reserved_tokens=tokens,
                    )
                    self.active.add(call_id)
                    self._respond(
                        response,
                        {
                            "allowed": True,
                            "timeout_seconds": min(
                                remaining,
                                self.context.spec.inputs.openhands.timeout_seconds,
                            ),
                        },
                    )
                    continue
                elif value["action"] == "finish" and call_id in self.active:
                    self.journal.finish(
                        call_id, value["receipt"], outcome=value["outcome"]
                    )
                    self.active.remove(call_id)
                else:
                    raise ResearchError(
                        "invalid_contract", "Unexpected worker call handshake"
                    )
            except ResearchError as error:
                result = {"allowed": False, "code": error.code}
                self._respond(response, result)
                raise
            self._respond(response, {"allowed": True})

    @staticmethod
    def _respond(path, body):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(body))
        temporary.replace(path)

    def abandon(self):
        for call_id in self.active:
            self.journal.finish(call_id, {"engine": "openhands"}, outcome="unknown")
        self.active.clear()
