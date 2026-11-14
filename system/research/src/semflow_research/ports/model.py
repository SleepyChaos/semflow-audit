"""Algorithm extracted from app.ports.model.

Runtime dependencies are passed explicitly; no platform ORM or configuration.
Changes to JSON require checking the corresponding semflow_contracts/wire peer.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

Response = TypeVar("Response", bound=BaseModel)


class ModelProvider(Protocol):
    model: str
    usage: dict

    def generate(
        self, purpose: str, payload: dict, schema: type[Response]
    ) -> Response: ...
