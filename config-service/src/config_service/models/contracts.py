"""Pydantic request contracts for the config-service API.

These models define the stable interface between clients (CLI, UI tools, and
automation) and config-service endpoints that parse, validate, and render
Fluent Bit and related OpAMP-managed configuration documents.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SchemaOptions(BaseModel):
    """Schema-level validation toggles shared by config processing workflows."""

    strict: bool = True


class ValidateRequest(BaseModel):
    """Payload for validating a parsed config against config-service rules.

    This is used by callers that need fast validation feedback before rendering
    or shipping configuration through the broader OpAMP toolchain.
    """

    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
    included_documents: list[dict[str, Any]] = Field(default_factory=list)
    merge_includes_for_validation: bool = False
    profile: str | None = None


class RenderYamlRequest(BaseModel):
    """Payload for rendering normalized config data to YAML output.

    This model is primarily used when the tool needs human-readable config
    artifacts with optional comments and include handling.
    """

    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
    included_documents: list[dict[str, Any]] = Field(default_factory=list)
    include_comments: bool = False
    render_included_files: bool = False
    header_comments: str = ""
    include_config_header: bool = False


class ParseTextRequest(BaseModel):
    """Payload for parsing raw config text into structured model data.

    This forms the ingestion entry point for text files before validation,
    transformation, or re-rendering by other config-service operations.
    """

    text: str
    source_path: str | None = None
    resolve_includes: bool = False


class RenderTextRequest(BaseModel):
    """Payload for rendering normalized config data to plain text format.

    This supports clients that need text output compatible with downstream
    config files while preserving include and header options.
    """

    config: dict[str, Any]
    annotations: dict[str, str] = Field(default_factory=dict)
    included_documents: list[dict[str, Any]] = Field(default_factory=list)
    render_included_files: bool = False
    header_comments: str = ""
    include_config_header: bool = False


class UiPrepareFileRequest(BaseModel):
    """Request for preparing an in-memory UI-edited file for service processing.

    Used by UI workflows to send draft content plus metadata before parsing or
    validation in the shared backend pipeline.
    """

    text: str
    file_name: str = ""
    config_type: str = ""


class UiLoadSourceFileRequest(BaseModel):
    """Request for loading a source file from disk in UI-assisted workflows.

    This bridges UI file selection to backend parsing so the same models and
    validation logic are reused across CLI and UI tooling.
    """

    source_path: str
    config_type: str = ""
