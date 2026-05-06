from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from importlib import import_module
from typing import Any

ERR_UI_AUTH_CONFIG_INVALID = "invalid ui-use-authorization configuration"


@dataclass(frozen=True)
class UIAuthResult:
    allowed: bool
    status_code: int = HTTPStatus.OK
    error: str = ""
    www_authenticate: str | None = None


def evaluate_ui_http_auth(
    *,
    path: str,
    method: str,
    authorization_header: str | None,
    remote_addr: str | None,
) -> UIAuthResult:
    """Evaluate non-OpAMP HTTP auth using provider auth stack when available.

    This intentionally reuses OpAMP provider auth modules to avoid introducing a
    separate auth model for config-service.
    """
    try:
        provider_auth = import_module("opamp_provider.auth")
        opamp_protocol = import_module("opamp_provider.opamp_protocol")
    except ModuleNotFoundError:
        # Standalone fallback when provider modules are not importable.
        return UIAuthResult(allowed=True)

    decision: Any = opamp_protocol.evaluate_non_opamp_http_auth(
        path=path,
        method=method,
        authorization_header=authorization_header,
        remote_addr=remote_addr,
        invalid_config_error=ERR_UI_AUTH_CONFIG_INVALID,
    )
    if decision.allowed:
        return UIAuthResult(allowed=True)

    www_authenticate = None
    if decision.status_code == HTTPStatus.UNAUTHORIZED:
        www_authenticate = str(provider_auth.WWW_AUTHENTICATE_BEARER)

    return UIAuthResult(
        allowed=False,
        status_code=int(decision.status_code),
        error=str(decision.error or "authorization failed"),
        www_authenticate=www_authenticate,
    )
