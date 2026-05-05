from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SchemaOptions(BaseModel):
    strict: bool = True


class ValidateRequest(BaseModel):
    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
    profile: str | None = None


class RenderYamlRequest(BaseModel):
    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
    include_comments: bool = False


class ParseTextRequest(BaseModel):
    text: str


class RenderTextRequest(BaseModel):
    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
