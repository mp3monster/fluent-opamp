#!/usr/bin/env python3
"""Build a consolidated OpAMP PDF manual.

The manual is generated from repository documentation and includes:
- Cover page with provider logo
- Table of contents
- Index section
- Component chapters
- Development/build process chapter
- Appendix with Apache 2.0 license text
- Appendix with dependency declarations
"""

from __future__ import annotations

import argparse
import re
import urllib.parse
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

DEFAULT_OUTPUT = "dist/manual/opamp_manual.pdf"
DEFAULT_TITLE = "OpAMP System Manual"
MANUAL_CONTENT_WIDTH = A4[0] - (32 * mm)
MANUAL_IMAGE_MAX_HEIGHT = 120 * mm
CODE_BLOCK_PADDING = 5

APACHE_LICENSE_2_TEXT = """Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

"License" shall mean the terms and conditions for use, reproduction, and
distribution as defined by Sections 1 through 9 of this document.

"Licensor" shall mean the copyright owner or entity authorized by the
copyright owner that is granting the License.

"Legal Entity" shall mean the union of the acting entity and all other
entities that control, are controlled by, or are under common control with
that entity. For the purposes of this definition, "control" means (i) the
power, direct or indirect, to cause the direction or management of such
entity, whether by contract or otherwise, or (ii) ownership of fifty percent
(50%) or more of the outstanding shares, or (iii) beneficial ownership of
such entity.

"You" (or "Your") shall mean an individual or Legal Entity exercising
permissions granted by this License.

"Source" form shall mean the preferred form for making modifications,
including but not limited to software source code, documentation source, and
configuration files.

"Object" form shall mean any form resulting from mechanical transformation or
translation of a Source form, including but not limited to compiled object
code, generated documentation, and conversions to other media types.

"Work" shall mean the work of authorship, whether in Source or Object form,
made available under the License, as indicated by a copyright notice that is
included in or attached to the work (an example is provided in the Appendix
below).

"Derivative Works" shall mean any work, whether in Source or Object form,
that is based on (or derived from) the Work and for which the editorial
revisions, annotations, elaborations, or other modifications represent, as a
whole, an original work of authorship. For the purposes of this License,
Derivative Works shall not include works that remain separable from, or
merely link (or bind by name) to the interfaces of, the Work and Derivative
Works thereof.

"Contribution" shall mean any work of authorship, including the original
version of the Work and any modifications or additions to that Work or
Derivative Works thereof, that is intentionally submitted to Licensor for
inclusion in the Work by the copyright owner or by an individual or Legal
Entity authorized to submit on behalf of the copyright owner. For the
purposes of this definition, "submitted" means any form of electronic, verbal,
or written communication sent to the Licensor or its representatives,
including but not limited to communication on electronic mailing lists, source
code control systems, and issue tracking systems that are managed by, or on
behalf of, the Licensor for the purpose of discussing and improving the Work,
but excluding communication that is conspicuously marked or otherwise
designated in writing by the copyright owner as "Not a Contribution."

"Contributor" shall mean Licensor and any individual or Legal Entity on
behalf of whom a Contribution has been received by Licensor and subsequently
incorporated within the Work.

2. Grant of Copyright License. Subject to the terms and conditions of this
License, each Contributor hereby grants to You a perpetual, worldwide,
non-exclusive, no-charge, royalty-free, irrevocable copyright license to
reproduce, prepare Derivative Works of, publicly display, publicly perform,
sublicense, and distribute the Work and such Derivative Works in Source or
Object form.

3. Grant of Patent License. Subject to the terms and conditions of this
License, each Contributor hereby grants to You a perpetual, worldwide,
non-exclusive, no-charge, royalty-free, irrevocable (except as stated in this
section) patent license to make, have made, use, offer to sell, sell, import,
and otherwise transfer the Work, where such license applies only to those
patent claims licensable by such Contributor that are necessarily infringed by
their Contribution(s) alone or by combination of their Contribution(s) with
the Work to which such Contribution(s) was submitted. If You institute patent
litigation against any entity (including a cross-claim or counterclaim in a
lawsuit) alleging that the Work or a Contribution incorporated within the Work
constitutes direct or contributory patent infringement, then any patent
licenses granted to You under this License for that Work shall terminate as of
the date such litigation is filed.

4. Redistribution. You may reproduce and distribute copies of the Work or
Derivative Works thereof in any medium, with or without modifications, and in
Source or Object form, provided that You meet the following conditions:

(a) You must give any other recipients of the Work or Derivative Works a copy
of this License; and

(b) You must cause any modified files to carry prominent notices stating that
You changed the files; and

(c) You must retain, in the Source form of any Derivative Works that You
distribute, all copyright, patent, trademark, and attribution notices from
the Source form of the Work, excluding those notices that do not pertain to
any part of the Derivative Works; and

(d) If the Work includes a "NOTICE" text file as part of its distribution,
then any Derivative Works that You distribute must include a readable copy of
the attribution notices contained within such NOTICE file, excluding those
notices that do not pertain to any part of the Derivative Works, in at least
one of the following places: within a NOTICE text file distributed as part of
the Derivative Works; within the Source form or documentation, if provided
along with the Derivative Works; or, within a display generated by the
Derivative Works, if and wherever such third-party notices normally appear.
The contents of the NOTICE file are for informational purposes only and do not
modify the License. You may add Your own attribution notices within Derivative
Works that You distribute, alongside or as an addendum to the NOTICE text from
the Work, provided that such additional attribution notices cannot be
construed as modifying the License.

You may add Your own copyright statement to Your modifications and may provide
additional or different license terms and conditions for use, reproduction, or
distribution of Your modifications, or for any such Derivative Works as a
whole, provided Your use, reproduction, and distribution of the Work otherwise
complies with the conditions stated in this License.

5. Submission of Contributions. Unless You explicitly state otherwise, any
Contribution intentionally submitted for inclusion in the Work by You to the
Licensor shall be under the terms and conditions of this License, without any
additional terms or conditions. Notwithstanding the above, nothing herein
shall supersede or modify the terms of any separate license agreement you may
have executed with Licensor regarding such Contributions.

6. Trademarks. This License does not grant permission to use the trade names,
trademarks, service marks, or product names of the Licensor, except as
required for reasonable and customary use in describing the origin of the Work
and reproducing the content of the NOTICE file.

7. Disclaimer of Warranty. Unless required by applicable law or agreed to in
writing, Licensor provides the Work (and each Contributor provides its
Contributions) on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied, including, without limitation, any warranties
or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
PARTICULAR PURPOSE. You are solely responsible for determining the
appropriateness of using or redistributing the Work and assume any risks
associated with Your exercise of permissions under this License.

8. Limitation of Liability. In no event and under no legal theory, whether in
tort (including negligence), contract, or otherwise, unless required by
applicable law (such as deliberate and grossly negligent acts) or agreed to in
writing, shall any Contributor be liable to You for damages, including any
direct, indirect, special, incidental, or consequential damages of any
character arising as a result of this License or out of the use or inability
to use the Work (including but not limited to damages for loss of goodwill,
work stoppage, computer failure or malfunction, or any and all other
commercial damages or losses), even if such Contributor has been advised of
the possibility of such damages.

9. Accepting Warranty or Additional Liability. While redistributing the Work
or Derivative Works thereof, You may choose to offer, and charge a fee for,
acceptance of support, warranty, indemnity, or other liability obligations
and/or rights consistent with this License. However, in accepting such
obligations, You may act only on Your own behalf and on Your sole
responsibility, not on behalf of any other Contributor, and only if You agree
to indemnify, defend, and hold each Contributor harmless for any liability
incurred by, or claims asserted against, such Contributor by reason of your
accepting any such warranty or additional liability.
"""


@dataclass(frozen=True)
class ChapterSpec:
    """One manual chapter definition."""

    title: str
    markdown_files: tuple[str, ...]


MANUAL_CHAPTERS: tuple[ChapterSpec, ...] = (
    ChapterSpec(
        title="Chapter 1 - Provider (Server)",
        markdown_files=(
            "provider/README.md",
            "docs/screenshots.md",
            "docs/provider_server_diagrams.md",
            "docs/endpoints.md",
        ),
    ),
    ChapterSpec(
        title="Chapter 2 - Consumer (Agent)",
        markdown_files=(
            "consumer/README.md",
            "docs/consumer_client_diagrams.md",
            "docs/consumer_custom_handlers.md",
            "docs/consumer_update_controllers.md",
            "docs/consumer_mixins.md",
        ),
    ),
    ChapterSpec(
        title="Chapter 3 - Consumer Simulator",
        markdown_files=(
            "consumer-sim/README.md",
        ),
    ),
    ChapterSpec(
        title="Chapter 4 - Agent Broker",
        markdown_files=(
            "agent_broker/README.md",
            "agent_broker/docs/README.md",
            "agent_broker/docs/broker_startup_and_shutdown.md",
            "agent_broker/docs/broker_code_structure.md",
            "agent_broker/docs/broker_graph_state_transitions.md",
            "agent_broker/docs/broker_runtime_graph.md",
        ),
    ),
    ChapterSpec(
        title="Chapter 5 - Security and Authentication",
        markdown_files=(
            "docs/authentication.md",
            "docs/api_gateway_requirements.md",
        ),
    ),
    ChapterSpec(
        title="Chapter 6 - Development and Build Processes",
        markdown_files=(
            "docs/scripts.md",
            "docs/component_versioning.md",
            "docs/service_daemon_setup.md",
        ),
    ),
)

DEPENDENCY_SOURCES: tuple[str, ...] = (
    "requirements.txt",
    "provider/requirements.txt",
    "consumer/requirements.txt",
    "agent_broker/requirements.txt",
)
PYPROJECT_DEPENDENCY_SOURCES: tuple[str, ...] = (
    "provider/pyproject.toml",
    "consumer/pyproject.toml",
    "agent_broker/pyproject.toml",
)

INDEX_TERMS: tuple[str, ...] = (
    "agent broker",
    "api endpoints",
    "authentication",
    "build artifacts",
    "component versioning",
    "consumer custom handlers",
    "consumer update controllers",
    "mcp",
    "provider web ui",
    "scripts",
    "security",
    "state persistence",
)


class ManualDocTemplate(BaseDocTemplate):
    """ReportLab template that tracks heading flowables for table of contents."""

    def __init__(self, output_path: Path, title: str) -> None:
        super().__init__(
            str(output_path),
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=title,
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="normal",
        )
        column_gap = 8 * mm
        column_width = (self.width - column_gap) / 2
        left_column = Frame(
            self.leftMargin,
            self.bottomMargin,
            column_width,
            self.height,
            id="appendixB-left",
        )
        right_column = Frame(
            self.leftMargin + column_width + column_gap,
            self.bottomMargin,
            column_width,
            self.height,
            id="appendixB-right",
        )
        self._title_text = title
        self.addPageTemplates(
            [
                PageTemplate(id="manual", frames=[frame], onPage=self._on_page),
                PageTemplate(
                    id="appendix_b_two_col",
                    frames=[left_column, right_column],
                    onPage=self._on_page,
                ),
            ]
        )

    def _on_page(self, canvas: object, doc: object) -> None:
        """Render page footer on every page."""
        _add_footer(canvas, doc, self._title_text)

    def afterFlowable(self, flowable: object) -> None:  # noqa: N802 - ReportLab hook.
        """Register headings with the TOC when a heading flowable is added."""
        if not isinstance(flowable, Paragraph):
            return
        level = getattr(flowable, "_toc_level", None)
        if level is None:
            return
        title = flowable.getPlainText()
        page_number = self.page
        self.notify("TOCEntry", (int(level), title, page_number))


def _build_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}
    styles["title"] = ParagraphStyle(
        "ManualTitle",
        parent=sample["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=34,
        spaceAfter=10,
        textColor=colors.HexColor("#1B1F24"),
        alignment=1,
    )
    styles["subtitle"] = ParagraphStyle(
        "ManualSubtitle",
        parent=sample["Heading2"],
        fontName="Helvetica",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#4C5563"),
        alignment=1,
    )
    styles["h1"] = ParagraphStyle(
        "H1",
        parent=sample["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1B1F24"),
        spaceBefore=12,
        spaceAfter=8,
    )
    styles["h2"] = ParagraphStyle(
        "H2",
        parent=sample["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1B1F24"),
        spaceBefore=10,
        spaceAfter=6,
    )
    styles["h3"] = ParagraphStyle(
        "H3",
        parent=sample["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1B1F24"),
        spaceBefore=8,
        spaceAfter=4,
    )
    styles["body"] = ParagraphStyle(
        "Body",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1B1F24"),
        spaceAfter=5,
    )
    styles["bullet"] = ParagraphStyle(
        "Bullet",
        parent=styles["body"],
        leftIndent=12,
        firstLineIndent=0,
        bulletIndent=0,
    )
    styles["numbered"] = ParagraphStyle(
        "Numbered",
        parent=styles["body"],
        leftIndent=16,
        firstLineIndent=0,
        bulletIndent=0,
    )
    styles["code"] = ParagraphStyle(
        "Code",
        parent=styles["body"],
        fontName="Courier",
        fontSize=8.8,
        leading=11,
        leftIndent=CODE_BLOCK_PADDING,
        spaceAfter=0,
    )
    styles["table_cell"] = ParagraphStyle(
        "TableCell",
        parent=styles["body"],
        fontName="Helvetica",
        fontSize=9.2,
        leading=11.5,
        spaceAfter=0,
    )
    styles["table_header"] = ParagraphStyle(
        "TableHeader",
        parent=styles["table_cell"],
        fontName="Helvetica-Bold",
    )
    styles["caption"] = ParagraphStyle(
        "Caption",
        parent=styles["body"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#4C5563"),
        alignment=1,
        spaceAfter=4,
    )
    return styles


def _toc_heading(text: str, style: ParagraphStyle, level: int) -> Paragraph:
    heading = Paragraph(escape(text), style)
    setattr(heading, "_toc_level", level)
    return heading


def _clean_inline_markdown(text: str) -> str:
    updated = text
    updated = re.sub(r"`([^`]+)`", r"\1", updated)
    updated = re.sub(r"\*\*([^*]+)\*\*", r"\1", updated)
    updated = re.sub(r"\*([^*]+)\*", r"\1", updated)
    updated = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", updated)
    updated = re.sub(r"^>\s*", "", updated)
    return updated.strip()


def _flush_paragraph(
    paragraphs: list[object],
    buffer: list[str],
    body_style: ParagraphStyle,
) -> None:
    if not buffer:
        return
    text = _clean_inline_markdown(" ".join(part.strip() for part in buffer if part.strip()))
    if text:
        paragraphs.append(Paragraph(escape(text), body_style))
        # Add one extra visual line break between markdown paragraph blocks.
        paragraphs.append(Spacer(1, 2 * mm))
    buffer.clear()


def _list_paragraph(text: str, style: ParagraphStyle, marker: str) -> Paragraph:
    """Create a list paragraph with hanging indent aligned by marker."""
    return Paragraph(escape(text), style, bulletText=escape(marker))


def _heading_is_numbered(text: str) -> bool:
    """Return True when heading text already starts with numeric section prefix."""
    cleaned = text.strip()
    return bool(re.match(r"^\d+(?:[.)]|\.\d+)+\s+", cleaned))


def _next_heading_number(level: int, counters: list[int]) -> str:
    """Increment heading counters and return dotted numbering for one level."""
    for idx in range(0, max(level - 1, 0)):
        if counters[idx] == 0:
            counters[idx] = 1
    counters[level - 1] += 1
    for idx in range(level, len(counters)):
        counters[idx] = 0
    parts = [str(value) for value in counters[:level] if value > 0]
    return ".".join(parts)


class CodeBlockPreformatted(Preformatted):
    """Preformatted code block that paints a pale-grey background."""

    def __init__(
        self,
        text: str,
        style: ParagraphStyle,
        *,
        max_line_length: int,
    ) -> None:
        self._max_line_length = max_line_length
        super().__init__(text, style, maxLineLength=max_line_length)

    def draw(self) -> None:
        self.canv.saveState()
        self.canv.setFillColor(colors.HexColor("#F2F2F2"))
        self.canv.setStrokeColor(colors.HexColor("#D0D0D0"))
        self.canv.setLineWidth(0.5)
        self.canv.rect(0, 0, self.width, self.height, stroke=1, fill=1)
        self.canv.restoreState()
        super().draw()

    def split(self, availWidth: float, availHeight: float) -> list["CodeBlockPreformatted"]:
        """Split large code blocks across pages while retaining block styling."""
        if availHeight < self.style.leading:
            return []

        lines_that_fit = int(availHeight * 1.0 / self.style.leading)
        text1 = "\n".join(self.lines[0:lines_that_fit])
        text2 = "\n".join(self.lines[lines_that_fit:])
        style = self.style
        if style.firstLineIndent != 0:
            style = deepcopy(style)
            style.firstLineIndent = 0
        return [
            CodeBlockPreformatted(
                text1,
                self.style,
                max_line_length=self._max_line_length,
            ),
            CodeBlockPreformatted(
                text2,
                style,
                max_line_length=self._max_line_length,
            ),
        ]


def _code_block_flowables(text: str, styles: dict[str, ParagraphStyle]) -> list[object]:
    """Render code text with wrapping and pale-grey background."""
    code_style = styles["code"]
    safe_char_width = max(stringWidth("M", code_style.fontName, code_style.fontSize), 1.0)
    usable_width = MANUAL_CONTENT_WIDTH - code_style.leftIndent - CODE_BLOCK_PADDING
    max_chars = max(
        20,
        int(usable_width / safe_char_width),
    )
    block = CodeBlockPreformatted(
        text,
        code_style,
        max_line_length=max_chars,
    )
    return [block, Spacer(1, 2 * mm)]


def _split_markdown_table_row(row_text: str) -> list[str]:
    """Split one markdown table row into cell values (supports escaped pipes)."""
    row = row_text.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]

    cells: list[str] = []
    buffer: list[str] = []
    escaped = False
    for char in row:
        if escaped:
            buffer.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append("".join(buffer).strip())
            buffer = []
            continue
        buffer.append(char)
    cells.append("".join(buffer).strip())
    return cells


def _is_markdown_separator_row(cells: list[str], expected_columns: int) -> bool:
    """Return True when cells represent a markdown table separator row."""
    if len(cells) != expected_columns or expected_columns == 0:
        return False
    for cell in cells:
        cleaned = cell.replace(" ", "")
        if not re.fullmatch(r":?-{3,}:?", cleaned):
            return False
    return True


def _extract_markdown_table(
    lines: list[str],
    start_index: int,
) -> tuple[list[list[str]], int] | None:
    """Extract a markdown table block from lines[start_index:] when present."""
    if start_index + 1 >= len(lines):
        return None

    header_text = lines[start_index].strip()
    separator_text = lines[start_index + 1].strip()
    if "|" not in header_text or "|" not in separator_text:
        return None

    header_cells = _split_markdown_table_row(header_text)
    separator_cells = _split_markdown_table_row(separator_text)
    if not _is_markdown_separator_row(separator_cells, len(header_cells)):
        return None

    table_rows: list[list[str]] = [header_cells]
    row_index = start_index + 2
    while row_index < len(lines):
        row_text = lines[row_index].strip()
        if not row_text or "|" not in row_text:
            break
        row_cells = _split_markdown_table_row(row_text)
        if len(row_cells) != len(header_cells):
            break
        table_rows.append(row_cells)
        row_index += 1

    return table_rows, row_index


def _table_flowable(
    table_rows: list[list[str]],
    styles: dict[str, ParagraphStyle],
) -> Table:
    """Build a ReportLab Table flowable from parsed markdown table rows."""
    row_count = len(table_rows)
    col_count = len(table_rows[0]) if table_rows else 0
    rendered_rows: list[list[Paragraph]] = []
    for row_idx, row in enumerate(table_rows):
        rendered_row: list[Paragraph] = []
        cell_style = styles["table_header"] if row_idx == 0 else styles["table_cell"]
        for col_idx in range(col_count):
            value = row[col_idx] if col_idx < len(row) else ""
            rendered_row.append(Paragraph(escape(_clean_inline_markdown(value)), cell_style))
        rendered_rows.append(rendered_row)

    col_width = MANUAL_CONTENT_WIDTH / max(col_count, 1)
    table = Table(
        rendered_rows,
        colWidths=[col_width] * col_count,
        repeatRows=1 if row_count > 1 else 0,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7DEEE")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FA")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _extract_markdown_images_from_line(line: str) -> list[tuple[str, str]] | None:
    """Extract markdown image tuples from a line if the line only contains image tags."""
    matches = list(re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", line))
    if not matches:
        return None
    non_image_text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line).strip()
    if non_image_text:
        return None
    return [(match.group(1).strip(), match.group(2).strip()) for match in matches]


def _parse_markdown_image_target(target: str) -> str:
    """Parse markdown image target text and return the path/URL portion."""
    cleaned = target.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return cleaned[1:-1].strip()
    title_match = re.match(r'^(.*?)(?:\s+["\'][^"\']*["\'])\s*$', cleaned)
    if title_match:
        cleaned = title_match.group(1).strip()
    return cleaned


def _resolve_markdown_image_path(
    *,
    target: str,
    source_path: Path,
    repo_root: Path,
) -> Path | None:
    """Resolve a markdown image target to a local file path when possible."""
    normalized_target = urllib.parse.unquote(_parse_markdown_image_target(target))
    lower_target = normalized_target.lower()
    if lower_target.startswith(("http://", "https://", "data:")):
        return None
    if not normalized_target:
        return None
    if normalized_target.startswith("/"):
        return (repo_root / normalized_target.lstrip("/")).resolve()
    return (source_path.parent / normalized_target).resolve()


def _image_flowables(
    *,
    alt_text: str,
    target: str,
    source_path: Path,
    repo_root: Path,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    """Render one markdown image reference into PDF flowables."""
    resolved_path = _resolve_markdown_image_path(
        target=target,
        source_path=source_path,
        repo_root=repo_root,
    )
    if resolved_path is None:
        return [
            Paragraph(
                escape(f"[Image skipped: unsupported target `{target}`]"),
                styles["body"],
            )
        ]
    if not resolved_path.exists():
        return [
            Paragraph(
                escape(f"[Image not found: {target}]"),
                styles["body"],
            )
        ]

    try:
        image = Image(str(resolved_path))
        image._restrictSize(MANUAL_CONTENT_WIDTH, MANUAL_IMAGE_MAX_HEIGHT)  # pylint: disable=protected-access
        image.hAlign = "CENTER"
        flowables: list[object] = [image]
    except OSError:
        return [
            Paragraph(
                escape(f"[Image could not be loaded: {target}]"),
                styles["body"],
            )
        ]

    caption = _clean_inline_markdown(alt_text)
    if caption:
        flowables.append(Paragraph(escape(caption), styles["caption"]))
    flowables.append(Spacer(1, 2 * mm))
    return flowables


def _markdown_to_flowables(
    markdown_text: str,
    styles: dict[str, ParagraphStyle],
    *,
    source_path: Path,
    repo_root: Path,
) -> list[object]:
    flowables: list[object] = []
    lines = markdown_text.splitlines()
    paragraph_buffer: list[str] = []
    code_lines: list[str] = []
    heading_counters = [0, 0, 0]
    in_code = False

    line_index = 0
    while line_index < len(lines):
        raw_line = lines[line_index]
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if stripped.startswith("```"):
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            if in_code:
                text = "\n".join(code_lines).strip("\n")
                if text:
                    flowables.extend(_code_block_flowables(text, styles))
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            line_index += 1
            continue

        if in_code:
            code_lines.append(line)
            line_index += 1
            continue

        if not stripped:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            line_index += 1
            continue

        image_matches = _extract_markdown_images_from_line(stripped)
        if image_matches is not None:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            for alt_text, target in image_matches:
                flowables.extend(
                    _image_flowables(
                        alt_text=alt_text,
                        target=target,
                        source_path=source_path,
                        repo_root=repo_root,
                        styles=styles,
                    )
                )
            line_index += 1
            continue

        table_match = _extract_markdown_table(lines, line_index)
        if table_match is not None:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            table_rows, next_line_index = table_match
            flowables.append(_table_flowable(table_rows, styles))
            flowables.append(Spacer(1, 2 * mm))
            line_index = next_line_index
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            hashes, title = heading_match.groups()
            level = min(len(hashes), 3)
            style_name = "h1" if level == 1 else "h2" if level == 2 else "h3"
            heading_text = _clean_inline_markdown(title)
            section_number = _next_heading_number(level, heading_counters)
            if not _heading_is_numbered(heading_text):
                heading_text = f"{section_number} {heading_text}"
            flowables.append(
                _toc_heading(heading_text, styles[style_name], level)
            )
            line_index += 1
            continue

        bullet_match = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet_match:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            bullet_text = _clean_inline_markdown(bullet_match.group(1))
            if bullet_text:
                flowables.append(_list_paragraph(bullet_text, styles["bullet"], "•"))
            line_index += 1
            continue

        numbered_match = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if numbered_match:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            number = numbered_match.group(1)
            item_text = _clean_inline_markdown(numbered_match.group(2))
            flowables.append(_list_paragraph(item_text, styles["numbered"], f"{number}."))
            line_index += 1
            continue

        paragraph_buffer.append(line)
        line_index += 1

    _flush_paragraph(flowables, paragraph_buffer, styles["body"])
    if code_lines:
        flowables.extend(_code_block_flowables("\n".join(code_lines), styles))
    return flowables


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_requirements(requirements_path: Path) -> list[str]:
    entries: list[str] = []
    if not requirements_path.exists():
        return entries
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def _parse_pyproject_dependencies(pyproject_path: Path) -> list[str]:
    """Parse dependency arrays from selected pyproject sections.

    Parsed sections:
    - [build-system] -> requires
    - [project] -> dependencies
    - [project.optional-dependencies] -> all arrays
    """
    if not pyproject_path.exists():
        return []

    lines = pyproject_path.read_text(encoding="utf-8", errors="replace").splitlines()
    section = ""
    collecting = False
    current_key = ""
    buffer: list[str] = []
    dependencies: list[str] = []

    def _consume_buffer() -> None:
        nonlocal buffer
        blob = "\n".join(buffer)
        for match in re.findall(r'"([^"]+)"', blob):
            cleaned = match.strip()
            if cleaned:
                dependencies.append(cleaned)
        buffer = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            if collecting:
                _consume_buffer()
                collecting = False
                current_key = ""
            section = stripped.strip("[]").strip()
            continue

        if not collecting:
            if "=" not in stripped:
                continue
            key, raw_value = stripped.split("=", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if section == "build-system" and key != "requires":
                continue
            if section == "project" and key != "dependencies":
                continue
            if section == "project.optional-dependencies":
                pass
            elif section not in {"build-system", "project"}:
                continue

            if "[" not in raw_value:
                continue
            current_key = key
            after_bracket = raw_value.split("[", 1)[1]
            buffer = [after_bracket]
            collecting = "]" not in after_bracket
            if not collecting:
                _consume_buffer()
                current_key = ""
            continue

        if collecting and current_key:
            buffer.append(stripped)
            if "]" in stripped:
                _consume_buffer()
                collecting = False
                current_key = ""

    if collecting:
        _consume_buffer()

    return sorted(set(dependencies), key=lambda item: item.lower())


def _collect_dependencies(repo_root: Path) -> tuple[dict[str, list[str]], list[str]]:
    per_source: dict[str, list[str]] = {}
    combined: set[str] = set()
    for rel_path in DEPENDENCY_SOURCES:
        source_path = repo_root / rel_path
        deps = _parse_requirements(source_path)
        per_source[rel_path] = deps
        combined.update(deps)
    for rel_path in PYPROJECT_DEPENDENCY_SOURCES:
        source_path = repo_root / rel_path
        deps = _parse_pyproject_dependencies(source_path)
        per_source[rel_path] = deps
        combined.update(deps)
    # Build/document dependencies used by wheel/manual refresh workflow.
    combined.add("build")
    combined.add("reportlab")
    return per_source, sorted(combined, key=lambda item: item.lower())


def _build_index_lines(chapters: Iterable[ChapterSpec]) -> list[str]:
    lines: list[str] = ["Manual chapter index:"]
    for chapter in chapters:
        lines.append(chapter.title)
        for rel_path in chapter.markdown_files:
            lines.append(f"  - Source: {rel_path}")
    lines.append("")
    lines.append("Topic index:")
    for term in sorted(INDEX_TERMS):
        lines.append(f"  - {term}")
    return lines


def _add_footer(canvas: object, _doc: object, title: str) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#4C5563"))
    canvas.drawString(16 * mm, 10 * mm, title)
    canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def _build_story(
    *,
    repo_root: Path,
    title: str,
    styles: dict[str, ParagraphStyle],
    generated_at: str,
) -> list[object]:
    story: list[object] = []

    logo_path = repo_root / "provider" / "src" / "opamp_provider" / "html" / "OpAmpSvr.png"
    story.append(Spacer(1, 20 * mm))
    if logo_path.exists():
        logo = Image(str(logo_path))
        logo._restrictSize(120 * mm, 60 * mm)  # pylint: disable=protected-access
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(escape(title), styles["title"]))
    story.append(
        Paragraph(
            "Provider, Consumer, Simulator, Broker, Development, and Build Reference",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Generated: {escape(generated_at)}", styles["subtitle"]))
    story.append(PageBreak())

    story.append(_toc_heading("Table Of Contents", styles["h1"], 1))
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOCLevel1",
            parent=styles["body"],
            fontName="Helvetica-Bold",
            leftIndent=10,
            firstLineIndent=-10,
            spaceBefore=2,
        ),
        ParagraphStyle(
            "TOCLevel2",
            parent=styles["body"],
            leftIndent=24,
            firstLineIndent=-10,
            spaceBefore=1,
        ),
        ParagraphStyle(
            "TOCLevel3",
            parent=styles["body"],
            leftIndent=36,
            firstLineIndent=-10,
            spaceBefore=1,
        ),
    ]
    story.append(toc)
    story.append(PageBreak())

    story.append(_toc_heading("Index", styles["h1"], 1))
    for line in _build_index_lines(MANUAL_CHAPTERS):
        if line.startswith("  - "):
            story.append(_list_paragraph(line[4:], styles["bullet"], "•"))
        else:
            story.append(Paragraph(escape(line), styles["body"]))
    story.append(PageBreak())

    for chapter in MANUAL_CHAPTERS:
        story.append(_toc_heading(chapter.title, styles["h1"], 1))
        for rel_path in chapter.markdown_files:
            full_path = repo_root / rel_path
            story.append(_toc_heading(f"Source: {rel_path}", styles["h2"], 2))
            if not full_path.exists():
                story.append(
                    Paragraph(
                        escape(f"Source file not found: {rel_path}"),
                        styles["body"],
                    )
                )
                continue
            source_text = _load_text(full_path)
            story.extend(
                _markdown_to_flowables(
                    source_text,
                    styles,
                    source_path=full_path,
                    repo_root=repo_root,
                )
            )
            story.append(Spacer(1, 2 * mm))
        story.append(PageBreak())

    story.append(_toc_heading("Appendix A - Apache License 2.0", styles["h1"], 1))
    story.extend(_code_block_flowables(APACHE_LICENSE_2_TEXT, styles))
    story.append(NextPageTemplate("appendix_b_two_col"))
    story.append(PageBreak())

    dependency_by_file, all_dependencies = _collect_dependencies(repo_root)
    story.append(_toc_heading("Appendix B - Dependency Declarations", styles["h1"], 1))
    story.append(
        Paragraph(
            (
                "Dependency lists below are consolidated from repository requirements "
                "files and pyproject dependency declarations."
            ),
            styles["body"],
        )
    )
    story.append(_toc_heading("B.1 Declared By File", styles["h2"], 2))
    for rel_path in [*DEPENDENCY_SOURCES, *PYPROJECT_DEPENDENCY_SOURCES]:
        story.append(_toc_heading(rel_path, styles["h3"], 3))
        deps = dependency_by_file.get(rel_path, [])
        if not deps:
            story.append(Paragraph("No entries found.", styles["body"]))
            continue
        for dep in deps:
            story.append(_list_paragraph(dep, styles["bullet"], "•"))
    story.append(Spacer(1, 2 * mm))
    story.append(_toc_heading("B.2 Combined Dependency Index", styles["h2"], 2))
    for dep in all_dependencies:
        story.append(_list_paragraph(dep, styles["bullet"], "•"))
    return story


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the consolidated OpAMP PDF manual from repository docs.",
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        help="Repository root path (default: parent of scripts folder).",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output PDF path relative to repo root (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--title",
        default=DEFAULT_TITLE,
        help=f"Manual title text (default: {DEFAULT_TITLE}).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_path = (repo_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _build_styles()
    now_utc = datetime.now(timezone.utc)
    generated_at = f"{now_utc.day} {now_utc.strftime('%B %Y')}"
    story = _build_story(
        repo_root=repo_root,
        title=str(args.title),
        styles=styles,
        generated_at=generated_at,
    )

    doc = ManualDocTemplate(output_path, str(args.title))
    # TOC entries are discovered in afterFlowable, so ReportLab needs multipass
    # rendering to replace the placeholder with resolved heading/page entries.
    doc.multiBuild(story)
    print(f"Manual generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
