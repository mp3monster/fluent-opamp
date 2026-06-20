"""Client filtering and agent-description parsing helpers for provider app."""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from google.protobuf import text_format

from opamp_provider.app_constants import (
    AGENT_DESCRIPTION_ATTRIBUTE_SPLIT_PATTERN,
    AGENT_DESCRIPTION_CACHE_SIZE,
    BOOLEAN_FALSE_VALUES,
    BOOLEAN_TRUE_VALUES,
    ERROR_INVALID_BOOLEAN_FILTER,
)
from opamp_provider.proto import opamp_pb2
from opamp_provider.state import ClientRecord
from shared.opamp_config import anyvalue_to_string


def serialize_client_record_for_api(
    record: ClientRecord,
    *,
    model_dump_mode: str,
    provider_remote_config_enabled: bool,
    remote_config_capability_reported: bool,
) -> dict[str, object]:
    """Return one API-facing client payload enriched with provider capability flags."""
    payload = record.model_dump(mode=model_dump_mode)
    payload["provider_remote_config_enabled"] = provider_remote_config_enabled
    payload["remote_config_capability_reported"] = remote_config_capability_reported
    payload["remote_config_files_allowed"] = (
        provider_remote_config_enabled and remote_config_capability_reported
    )
    return payload


def coerce_bool_setting(value: object, *, key: str) -> bool:
    """Coerce UI/API boolean payload values for settings endpoints."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"{key} must be a boolean")


def normalize_query_text(value: str | None) -> str | None:
    """Return stripped query text or None when empty/unset."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def parse_optional_bool(
    value: str | bool | None,
    *,
    parameter_name: str,
) -> bool | None:
    """Parse a bool-like query value into `bool | None`."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    if normalized in BOOLEAN_TRUE_VALUES:
        return True
    if normalized in BOOLEAN_FALSE_VALUES:
        return False
    raise ValueError(ERROR_INVALID_BOOLEAN_FILTER % parameter_name)


def matches_text(value: str | None, query: str | None) -> bool:
    """Return True when query is unset or is a case-insensitive substring match."""
    if query is None:
        return True
    if not value:
        return False
    return query.lower() in value.lower()


def any_matches_text(values: tuple[str, ...], query: str | None) -> bool:
    """Return True when any value matches query (case-insensitive substring)."""
    if query is None:
        return True
    needle = query.lower()
    for value in values:
        if needle in str(value).lower():
            return True
    return False


@lru_cache(maxsize=AGENT_DESCRIPTION_CACHE_SIZE)
def parse_agent_description_attributes(
    agent_description: str,
) -> dict[str, tuple[str, ...]]:
    """Parse AgentDescription text and return key -> tuple(values) mapping."""
    desc = opamp_pb2.AgentDescription()
    text_format.Parse(agent_description, desc)
    collected: dict[str, list[str]] = {}
    for item in [*desc.identifying_attributes, *desc.non_identifying_attributes]:
        key = str(item.key).strip()
        value = anyvalue_to_string(item.value)
        if not key or value is None:
            continue
        collected.setdefault(key, []).append(value)
    return {key: tuple(values) for key, values in collected.items()}


def record_agent_description_attributes(
    record: ClientRecord,
    *,
    logger: logging.Logger,
) -> dict[str, tuple[str, ...]]:
    """Read parsed agent-description attributes for one client record."""
    if not record.agent_description:
        return {}
    try:
        return parse_agent_description_attributes(record.agent_description)
    except text_format.ParseError:
        logger.debug(
            "unable to parse agent_description for client_id=%s",
            record.client_id,
            exc_info=True,
        )
        return {}


def record_service_instance_ids(
    record: ClientRecord,
    *,
    logger: logging.Logger,
) -> tuple[str, ...]:
    """Return service-instance display-name candidates for filtering."""
    attributes = record_agent_description_attributes(record, logger=logger)
    candidates: list[str] = list(attributes.get("service.instance.id", ()))
    if not candidates and record.client_id:
        candidates.append(record.client_id)
    seen: set[str] = set()
    deduped: list[str] = []
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return tuple(deduped)


def record_host_names(
    record: ClientRecord,
    *,
    logger: logging.Logger,
) -> tuple[str, ...]:
    """Return host name values extracted from agent description."""
    attributes = record_agent_description_attributes(record, logger=logger)
    candidates: list[str] = []
    for key in ("host.name", "hostname"):
        candidates.extend(attributes.get(key, ()))
    seen: set[str] = set()
    deduped: list[str] = []
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return tuple(deduped)


def record_host_ips(
    record: ClientRecord,
    *,
    logger: logging.Logger,
) -> tuple[str, ...]:
    """Return host IP candidates from remote_addr and agent description fields."""
    candidates: list[str] = []
    if record.remote_addr:
        candidates.append(record.remote_addr)
    attributes = record_agent_description_attributes(record, logger=logger)
    for key in ("host.ip", "ip_address", "ip"):
        for raw in attributes.get(key, ()):
            stripped = str(raw).strip().strip("[]")
            if not stripped:
                continue
            for part in re.split(AGENT_DESCRIPTION_ATTRIBUTE_SPLIT_PATTERN, stripped):
                normalized = part.strip()
                if normalized:
                    candidates.append(normalized)
    seen: set[str] = set()
    deduped: list[str] = []
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return tuple(deduped)


def client_matches_api_clients_filters(
    client: ClientRecord,
    *,
    service_instance_id: str | None,
    client_version: str | None,
    host_name: str | None,
    host_ip: str | None,
    invert_filter: bool,
    has_active_filters: bool,
    logger: logging.Logger,
) -> bool:
    """Evaluate whether one client satisfies requested /api/clients filters."""
    active_matches: list[bool] = []
    if service_instance_id is not None:
        active_matches.append(
            any_matches_text(
                record_service_instance_ids(client, logger=logger),
                service_instance_id,
            )
        )
    if client_version is not None:
        active_matches.append(matches_text(client.client_version, client_version))
    if host_name is not None:
        active_matches.append(
            any_matches_text(record_host_names(client, logger=logger), host_name)
        )
    if host_ip is not None:
        active_matches.append(
            any_matches_text(record_host_ips(client, logger=logger), host_ip)
        )

    matches = True if not active_matches else any(active_matches)
    if invert_filter and has_active_filters:
        return not matches
    return matches
