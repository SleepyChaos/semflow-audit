"""Translate presentation text only; identifiers, source and verdicts are immutable."""

from pydantic import Field

from app.contracts.stages import StrictModel


class TranslatedText(StrictModel):
    key: str
    text: str = Field(min_length=1, max_length=6000)


class TranslationResponse(StrictModel):
    translations: list[TranslatedText] = Field(min_length=1, max_length=200)
