#!/usr/bin/env python3
# Copyright 2026 mp3monster.org
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

SECTION_KIND = {
    "inputs": "input",
    "filters": "filter",
    "outputs": "output",
}
SECTION_FLAG = {
    "inputs": "-i",
    "filters": "-F",
    "outputs": "-o",
}
USER_AGENT = "Mozilla/5.0 (compatible; config-service-plugin-name-checker/1.0)"


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if data:
            self._chunks.append(data)

    def text(self) -> str:
        return "\n".join(self._chunks)


@dataclass(frozen=True)
class PluginNameResolution:
    current_name: str
    expected_name: str | None
    evidence: str | None
    doc_url: str


def fetch_page_text(url: str, *, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="ignore")
    parser = _HtmlTextExtractor()
    parser.feed(html)
    return parser.text()


def extract_expected_name(page_text: str, section: str) -> tuple[str | None, str | None]:
    kind = SECTION_KIND[section]
    flag = SECTION_FLAG[section]
    patterns = (
        (
            re.compile(rf"\[{kind}\s*:\s*([a-z0-9_-]+)", re.IGNORECASE),
            f"[{kind}:name]",
        ),
        (
            re.compile(rf"\[{section[:-1]}\]\s+name\s+([a-z0-9_-]+)", re.IGNORECASE),
            f"[{section[:-1].upper()}] Name",
        ),
        (
            re.compile(rf"{re.escape(flag)}\s+([a-z0-9_-]+)", re.IGNORECASE),
            flag,
        ),
    )
    for pattern, label in patterns:
        match = pattern.search(page_text)
        if match:
            return match.group(1).strip().lower(), label
    return None, None


def resolve_expected_name(
    doc_url: str,
    section: str,
    *,
    timeout: int,
    page_cache: dict[str, str] | None = None,
    text_fetcher: Callable[..., str] = fetch_page_text,
) -> tuple[str | None, str | None]:
    if not doc_url:
        return None, None
    page_text = page_cache.get(doc_url) if page_cache is not None else None
    if page_text is None:
        page_text = text_fetcher(doc_url, timeout=timeout)
        if page_cache is not None:
            page_cache[doc_url] = page_text
    return extract_expected_name(page_text, section)


def collect_plugin_name_resolutions(
    section_plugins: Mapping[str, dict[str, Any]],
    section: str,
    *,
    timeout: int,
    page_cache: dict[str, str] | None = None,
    text_fetcher: Callable[..., str] = fetch_page_text,
) -> list[PluginNameResolution]:
    resolutions: list[PluginNameResolution] = []
    for current_name, plugin_def in sorted(section_plugins.items()):
        doc_url = ""
        if isinstance(plugin_def, dict):
            doc_url = str(plugin_def.get("doc_url") or "").strip()
        expected_name, evidence = resolve_expected_name(
            doc_url,
            section,
            timeout=timeout,
            page_cache=page_cache,
            text_fetcher=text_fetcher,
        )
        resolutions.append(
            PluginNameResolution(
                current_name=str(current_name),
                expected_name=expected_name,
                evidence=evidence,
                doc_url=doc_url,
            )
        )
    return resolutions


def conflicting_expected_names(resolutions: list[PluginNameResolution]) -> dict[str, list[str]]:
    collisions: dict[str, set[str]] = {}
    for resolution in resolutions:
        if not resolution.expected_name:
            continue
        collisions.setdefault(resolution.expected_name, set()).add(resolution.current_name)
    return {
        expected_name: sorted(current_names)
        for expected_name, current_names in collisions.items()
        if len(current_names) > 1
    }


def normalize_plugin_map(
    section_plugins: Mapping[str, dict[str, Any]],
    section: str,
    *,
    timeout: int,
    logger: logging.Logger | None = None,
    page_cache: dict[str, str] | None = None,
    text_fetcher: Callable[..., str] = fetch_page_text,
) -> tuple[dict[str, dict[str, Any]], list[PluginNameResolution], dict[str, list[str]]]:
    resolutions = collect_plugin_name_resolutions(
        section_plugins,
        section,
        timeout=timeout,
        page_cache=page_cache,
        text_fetcher=text_fetcher,
    )
    resolution_map = {item.current_name: item for item in resolutions}
    collisions = conflicting_expected_names(resolutions)
    normalized: dict[str, dict[str, Any]] = {}

    for current_name, plugin_def in sorted(section_plugins.items()):
        resolution = resolution_map[str(current_name)]
        target_name = str(current_name)
        if resolution.expected_name and resolution.expected_name != resolution.current_name:
            if resolution.expected_name in collisions:
                if logger:
                    logger.warning(
                        "skip plugin-name collision section=%s from=%s expected=%s conflicts=%s url=%s",
                        section,
                        resolution.current_name,
                        resolution.expected_name,
                        ",".join(collisions[resolution.expected_name]),
                        resolution.doc_url,
                    )
            else:
                target_name = resolution.expected_name
                if logger:
                    logger.info(
                        "normalize plugin name section=%s from=%s to=%s evidence=%s url=%s",
                        section,
                        resolution.current_name,
                        resolution.expected_name,
                        resolution.evidence,
                        resolution.doc_url,
                    )
        if target_name in normalized:
            raise ValueError(f"Duplicate normalized plugin name '{target_name}' in section '{section}'")
        normalized[target_name] = copy.deepcopy(plugin_def)

    return normalized, resolutions, collisions
