from typing import Protocol, TypeVar

from pydantic import BaseModel

Response = TypeVar("Response", bound=BaseModel)


class ModelProvider(Protocol):
    model: str
    usage: dict

    def generate(
        self, purpose: str, payload: dict, schema: type[Response]
    ) -> Response: ...
