from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SchemaOptions(BaseModel):
    strict: bool = True


class ValidateRequest(BaseModel):
    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
    included_documents: list[dict[str, Any]] = Field(default_factory=list)
    merge_includes_for_validation: bool = False
    profile: str | None = None


class RenderYamlRequest(BaseModel):
    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
    included_documents: list[dict[str, Any]] = Field(default_factory=list)
    include_comments: bool = False
    render_included_files: bool = False
    header_comments: str = ""
    include_config_header: bool = False


class ParseTextRequest(BaseModel):
    text: str
    source_path: str | None = None
    resolve_includes: bool = False


class RenderTextRequest(BaseModel):
    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
    included_documents: list[dict[str, Any]] = Field(default_factory=list)
    render_included_files: bool = False
    header_comments: str = ""
    include_config_header: bool = False


class UiPrepareFileRequest(BaseModel):
    text: str
    file_name: str = ""
    config_type: str = ""


class UiLoadSourceFileRequest(BaseModel):
    source_path: str
    config_type: str = ""
