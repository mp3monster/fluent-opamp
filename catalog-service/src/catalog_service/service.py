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

"""Filesystem indexing service for catalog-service view."""

from __future__ import annotations

import datetime
import io
import logging
import pathlib
import re
import threading
from dataclasses import dataclass

from catalog_service.config import CatalogServiceConfig, CatalogSource
from catalog_service.config_classifiers import CompositeConfigClassifier

LOGGER = logging.getLogger(__name__)
HEADER_LINE_PATTERN = re.compile(r"^\s*(?:#|//|;)\s?(.*)$")
METADATA_PATTERN = re.compile(r"^config-service:\s*([A-Za-z0-9_.-]+)\s*=\s*(.*?)\s*$")
KEY_CONFIG_TYPE = "config_type"
ROW_KEY_FOLDER = "folder"
ROW_KEY_FILENAME = "filename"
ROW_KEY_PATH = "path"
ROW_KEY_LAST_EDITED = "last_edited"
ROW_KEY_METADATA = "metadata"
ROW_KEY_COLUMNS = "columns"
ROW_KEY_ROWS = "rows"
ROW_KEY_TOTAL = "total"
ROW_KEY_TEXT = "text"
COLUMN_ORDER_BASE = (ROW_KEY_FOLDER, ROW_KEY_FILENAME, ROW_KEY_LAST_EDITED)
FileSignature = tuple[int, int]


@dataclass(frozen=True)
class CatalogRow:
    """One indexed catalog file row with extracted header metadata."""

    folder: str
    filename: str
    full_path: str
    last_edited: str
    metadata: dict[str, str]


class CatalogFileIndexService:
    """Scans configured folders and extracts top-comment config metadata."""

    def __init__(self, *, repo_root: pathlib.Path, config: CatalogServiceConfig) -> None:
        self.repo_root = pathlib.Path(repo_root).resolve()
        self.config = config
        self.classifier = CompositeConfigClassifier()
        self._lock = threading.RLock()
        self._file_signatures: dict[str, FileSignature] = {}
        self._cached_payload: dict[str, object] | None = None

    def scan(self) -> dict[str, object]:
        """Return table-ready payload, refreshing cached metadata when source files change."""
        with self._lock:
            current_signatures = self._source_file_signatures()
            if self._cached_payload is not None and current_signatures == self._file_signatures:
                return self._cached_payload

            payload = self._build_payload()
            self._file_signatures = current_signatures
            self._cached_payload = payload
            return payload

    def _build_payload(self) -> dict[str, object]:
        """Scan configured sources and build the table-ready payload."""
        rows: list[CatalogRow] = []
        metadata_keys: set[str] = set()
        for source in self.config.sources:
            rows.extend(self._scan_source(source, metadata_keys=metadata_keys))
        rows.sort(key=lambda item: (item.folder.lower(), item.filename.lower()))

        payload_rows = [
            {
                ROW_KEY_FOLDER: row.folder,
                ROW_KEY_FILENAME: row.filename,
                ROW_KEY_PATH: row.full_path,
                ROW_KEY_LAST_EDITED: row.last_edited,
                ROW_KEY_METADATA: row.metadata,
            }
            for row in rows
        ]
        return {
            ROW_KEY_COLUMNS: [*COLUMN_ORDER_BASE, *sorted(metadata_keys)],
            ROW_KEY_ROWS: payload_rows,
            ROW_KEY_TOTAL: len(payload_rows),
        }

    def _source_file_signatures(self) -> dict[str, FileSignature]:
        """Return watched source file signatures keyed by resolved path."""
        signatures: dict[str, FileSignature] = {}
        for source in self.config.sources:
            base_dir = (self.repo_root / source.folder).resolve()
            if not base_dir.exists() or not base_dir.is_dir():
                continue
            allowed_ext = {ext.lower() for ext in source.extensions}
            for path in sorted(base_dir.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in allowed_ext:
                    continue
                try:
                    stat_result = path.stat()
                except OSError:
                    continue
                signatures[str(path.resolve())] = (int(stat_result.st_mtime_ns), int(stat_result.st_size))
        return signatures

    def read_file_text(self, full_path: str) -> dict[str, str]:
        """Return readonly file content for one catalog-managed file path."""
        resolved = pathlib.Path(str(full_path or "")).expanduser().resolve(strict=True)
        if resolved.is_file() is not True:
            raise FileNotFoundError(str(resolved))
        if self._is_allowed_catalog_file(resolved) is not True:
            raise PermissionError(str(resolved))
        LOGGER.info("catalog file read requested path=%s", resolved)
        return {
            ROW_KEY_FILENAME: resolved.name,
            ROW_KEY_PATH: str(resolved),
            ROW_KEY_TEXT: resolved.read_text(encoding="utf-8", errors="ignore"),
        }

    def _scan_source(self, source: CatalogSource, *, metadata_keys: set[str]) -> list[CatalogRow]:
        base_dir = (self.repo_root / source.folder).resolve()
        if not base_dir.exists() or not base_dir.is_dir():
            return []

        allowed_ext = {ext.lower() for ext in source.extensions}
        rows: list[CatalogRow] = []
        for path in sorted(base_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in allowed_ext:
                continue
            metadata = self._extract_row_metadata(path)
            metadata_keys.update(metadata.keys())
            folder = str(path.parent.resolve().relative_to(self.repo_root)).replace("\\", "/")
            last_edited = datetime.datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=datetime.timezone.utc,
            ).replace(microsecond=0).isoformat()
            rows.append(
                CatalogRow(
                    folder=folder,
                    filename=path.name,
                    full_path=str(path.resolve()),
                    last_edited=last_edited,
                    metadata=metadata,
                )
            )
        return rows

    def _extract_row_metadata(self, path: pathlib.Path) -> dict[str, str]:
        metadata: dict[str, str] = {}
        LOGGER.info("catalog file indexed path=%s", path.resolve())
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return metadata

        metadata.update(self._extract_header_metadata(text))
        classification = self.classifier.classify(io.StringIO(text))
        if classification is not None:
            metadata.setdefault(KEY_CONFIG_TYPE, classification.config_type)
            for key, value in classification.attributes.items():
                metadata.setdefault(str(key), str(value))
        return metadata

    def _is_allowed_catalog_file(self, path: pathlib.Path) -> bool:
        """Return whether a file path belongs to one configured catalog source."""
        for source in self.config.sources:
            base_dir = (self.repo_root / source.folder).resolve()
            if base_dir.exists() is not True or base_dir.is_dir() is not True:
                continue
            if path.suffix.lower() not in {ext.lower() for ext in source.extensions}:
                continue
            try:
                path.relative_to(base_dir)
            except ValueError:
                continue
            return True
        return False

    def _extract_header_metadata(self, text: str) -> dict[str, str]:
        metadata: dict[str, str] = {}

        for raw_line in text.splitlines():
            if not raw_line.strip():
                if metadata:
                    break
                continue
            header_match = HEADER_LINE_PATTERN.match(raw_line)
            if not header_match:
                break
            comment_text = str(header_match.group(1) or "").strip()
            meta_match = METADATA_PATTERN.match(comment_text)
            if not meta_match:
                continue
            key = str(meta_match.group(1) or "").strip()
            value = str(meta_match.group(2) or "").strip()
            if key:
                metadata[key] = value
        return metadata
