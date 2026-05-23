# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Quart route registration for OpAMP config-catalog UI."""

from __future__ import annotations

import html
import logging
from functools import lru_cache
from http import HTTPStatus
from pathlib import Path

from quart import Response, Quart, jsonify, request

from catalog_service.config import CatalogServiceConfig
from catalog_service.service import CatalogFileIndexService

CONFIG_EDITOR_ENTRY_POINT = "config_service.opamp_integration:register_config_service_feature"
HTML_DIR = Path(__file__).resolve().parent / "html"
CATALOG_HTML_PATH = HTML_DIR / "catalog.html"
CATALOG_HELP_HTML_PATH = HTML_DIR / "catalog_help.html"
PLACEHOLDER_TITLE = "__CATALOG_TITLE__"
PLACEHOLDER_ROUTE_PATH = "__CATALOG_ROUTE_PATH__"
PLACEHOLDER_HELP_PATH = "__CATALOG_HELP_PATH__"
PLACEHOLDER_CSS_PATH = "__CATALOG_CSS_PATH__"
PLACEHOLDER_CONFIG_EDITOR_ENTRY_POINT = "__CATALOG_CONFIG_EDITOR_ENTRY_POINT__"
REQUEST_ARG_PATH = "path"
RESPONSE_KEY_ERROR = "error"
ERR_PATH_REQUIRED = "path is required"
ERR_FILE_NOT_FOUND = "catalog file not found: {file_path}"
ERR_FILE_NOT_ALLOWED = "catalog file is not part of configured sources: {file_path}"
LOGGER = logging.getLogger(__name__)

@lru_cache(maxsize=4)
def _load_html_asset(template_path: str) -> str:
    """Return cached HTML asset text for catalog UI pages."""
    return Path(template_path).read_text(encoding="utf-8")


def _render_html_asset(*, template_path: Path, replacements: dict[str, str]) -> str:
    """Apply placeholder substitutions to one external HTML asset."""
    rendered = _load_html_asset(str(template_path))
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def _catalog_html(config: CatalogServiceConfig) -> str:
    """Render catalog UI HTML from external asset markup."""
    return _render_html_asset(
        template_path=CATALOG_HTML_PATH,
        replacements={
            PLACEHOLDER_TITLE: html.escape(config.menu_label),
            PLACEHOLDER_ROUTE_PATH: html.escape(config.route_path),
            PLACEHOLDER_HELP_PATH: html.escape(config.help_path),
            PLACEHOLDER_CSS_PATH: html.escape(config.ui_base_css_path),
            PLACEHOLDER_CONFIG_EDITOR_ENTRY_POINT: CONFIG_EDITOR_ENTRY_POINT,
        },
    )


def _help_html(config: CatalogServiceConfig) -> str:
    """Render catalog help HTML from external asset markup."""
    return _render_html_asset(
        template_path=CATALOG_HELP_HTML_PATH,
        replacements={
            PLACEHOLDER_TITLE: html.escape(config.menu_label),
            PLACEHOLDER_ROUTE_PATH: html.escape(config.route_path),
            PLACEHOLDER_CSS_PATH: html.escape(config.ui_base_css_path),
        },
    )


def register_catalog_routes(
    *,
    app: Quart,
    config: CatalogServiceConfig,
    service: CatalogFileIndexService,
) -> None:
    """Register provider catalog UI/help/API routes for the configured path."""

    if config.enabled is not True:
        LOGGER.info("catalog routes not registered because catalog feature is disabled")
        return
    LOGGER.info(
        "registering catalog routes route_path=%s help_path=%s source_count=%s",
        config.route_path,
        config.help_path,
        len(config.sources),
    )

    @app.get(config.route_path)
    async def catalog_ui() -> Response:
        return Response(_catalog_html(config), content_type="text/html; charset=utf-8")

    @app.get(config.help_path)
    async def catalog_help() -> Response:
        return Response(_help_html(config), content_type="text/html; charset=utf-8")

    @app.get(f"{config.route_path}/api/files")
    async def catalog_files() -> Response:
        return jsonify(service.scan()), HTTPStatus.OK

    @app.get(f"{config.route_path}/api/file-content")
    async def catalog_file_content() -> Response:
        file_path = str(request.args.get(REQUEST_ARG_PATH) or "").strip()
        if not file_path:
            LOGGER.warning(
                "catalog file-content request rejected because path argument is missing route_path=%s remote_addr=%s",
                config.route_path,
                request.remote_addr,
            )
            return jsonify({RESPONSE_KEY_ERROR: ERR_PATH_REQUIRED}), HTTPStatus.BAD_REQUEST
        try:
            payload = service.read_file_text(file_path)
        except FileNotFoundError:
            LOGGER.warning(
                "catalog file-content request failed because file was not found path=%s remote_addr=%s",
                file_path,
                request.remote_addr,
            )
            return jsonify({RESPONSE_KEY_ERROR: ERR_FILE_NOT_FOUND.format(file_path=file_path)}), HTTPStatus.NOT_FOUND
        except PermissionError:
            LOGGER.warning(
                "catalog file-content request rejected because file is outside configured sources path=%s remote_addr=%s",
                file_path,
                request.remote_addr,
            )
            return jsonify({RESPONSE_KEY_ERROR: ERR_FILE_NOT_ALLOWED.format(file_path=file_path)}), HTTPStatus.FORBIDDEN
        except OSError as exc:
            LOGGER.exception(
                "catalog file-content request failed due to filesystem error path=%s remote_addr=%s",
                file_path,
                request.remote_addr,
                exc_info=exc,
            )
            return jsonify({RESPONSE_KEY_ERROR: str(exc)}), HTTPStatus.INTERNAL_SERVER_ERROR
        return jsonify(payload), HTTPStatus.OK
