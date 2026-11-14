"""Worker-only call handshake; the parent owns the durable research budget.

No research/platform imports are needed in the pinned SDK interpreter.
"""

import hashlib
import json
import time
from pathlib import Path
from uuid import uuid4


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    temporary.replace(path)


def exchange(directory, value, timeout):
    identifier = uuid4().hex
    write(directory / f"{identifier}.request.json", value)
    response = directory / f"{identifier}.response.json"
    deadline = time.monotonic() + timeout
    while not response.is_file():
        if time.monotonic() >= deadline:
            raise RuntimeError("Research budget controller did not acknowledge call")
        time.sleep(0.02)
    result = json.loads(response.read_text())
    if not result["allowed"]:
        raise RuntimeError("Research budget rejected call: " + result["code"])
    return result


def install(llm_type, directory, *, output_tokens, timeout):
    """Instrument the pinned synchronous Agent.generate route, before any call."""
    directory = Path(directory) / "calls"
    directory.mkdir()
    generate = llm_type.generate

    def guarded(self, messages, *args, **kwargs):
        # WIRE-SEND:research.openhands — peer: adapters.repair.openhands_budget.poll.
        # AGENT: reserve BEFORE sending; finish only a received outcome. Parent
        # loss leaves an unknown charged call, never permission to repeat it.
        body = json.dumps(
            {"messages": messages, "args": args, "kwargs": kwargs},
            default=lambda value: (
                value.model_dump(mode="json")
                if hasattr(value, "model_dump")
                else str(value)
            ),
            ensure_ascii=False,
        ).encode()
        call_id = str(uuid4())
        permission = exchange(
            directory,
            {
                "action": "reserve",
                "call_id": call_id,
                "input_digest": hashlib.sha256(body).hexdigest(),
                # UTF-8 bytes conservatively bound tokenized messages/tools; extra
                # allowance covers SDK-inserted wrappers and security fields.
                "reserved_tokens": len(body) + output_tokens + 8192,
            },
            timeout,
        )
        # Parent includes time spent by earlier semantic/SDK calls. The SDK may
        # shorten its timeout, never reset or widen the shared execution budget.
        self.timeout = min(
            getattr(self, "timeout", timeout), permission["timeout_seconds"]
        )
        before = self.metrics.model_dump(mode="json").get("accumulated_token_usage")
        try:
            result = generate(self, messages, *args, **kwargs)
        except Exception:
            exchange(
                directory,
                {
                    "action": "finish",
                    "call_id": call_id,
                    "outcome": "unknown",
                    "receipt": {},
                },
                timeout,
            )
            raise
        after = self.metrics.model_dump(mode="json").get("accumulated_token_usage")
        receipt = {"engine": "openhands", "model": self.model}
        for public, native in (
            ("input_tokens", "prompt_tokens"),
            ("output_tokens", "completion_tokens"),
        ):
            receipt[public] = (
                after[native] - (before[native] if before else 0) if after else None
            )
        exchange(
            directory,
            {
                "action": "finish",
                "call_id": call_id,
                "outcome": "known",
                "receipt": receipt,
            },
            timeout,
        )
        return result

    llm_type.generate = guarded
