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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

DEFAULT_OUTPUT = "dist/manual/opamp_manual.pdf"
DEFAULT_TITLE = "OpAMP System Manual"

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
            "docs/provider_server_diagrams.md",
            "docs/endpoints.md",
        ),
    ),
    ChapterSpec(
        title="Chapter 2 - Consumer (Agent)",
        markdown_files=(
            "consumer/README.md",
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
        self._title_text = title
        self.addPageTemplates(
            [PageTemplate(id="manual", frames=[frame], onPage=self._on_page)]
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
        firstLineIndent=-10,
        bulletIndent=0,
    )
    styles["code"] = ParagraphStyle(
        "Code",
        parent=styles["body"],
        fontName="Courier",
        fontSize=8.8,
        leading=11,
        leftIndent=8,
        backColor=colors.HexColor("#F5F7FB"),
        borderColor=colors.HexColor("#D7DEEE"),
        borderWidth=0.5,
        borderPadding=6,
        borderRadius=3,
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
    buffer.clear()


def _markdown_to_flowables(markdown_text: str, styles: dict[str, ParagraphStyle]) -> list[object]:
    flowables: list[object] = []
    lines = markdown_text.splitlines()
    paragraph_buffer: list[str] = []
    code_lines: list[str] = []
    in_code = False

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if stripped.startswith("```"):
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            if in_code:
                text = "\n".join(code_lines).strip("\n")
                if text:
                    flowables.append(Preformatted(text, styles["code"]))
                    flowables.append(Spacer(1, 2 * mm))
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not stripped:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            hashes, title = heading_match.groups()
            level = min(len(hashes), 3)
            style_name = "h1" if level == 1 else "h2" if level == 2 else "h3"
            flowables.append(
                _toc_heading(_clean_inline_markdown(title), styles[style_name], level)
            )
            continue

        bullet_match = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet_match:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            bullet_text = _clean_inline_markdown(bullet_match.group(1))
            if bullet_text:
                flowables.append(Paragraph(f"• {escape(bullet_text)}", styles["bullet"]))
            continue

        numbered_match = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if numbered_match:
            _flush_paragraph(flowables, paragraph_buffer, styles["body"])
            number = numbered_match.group(1)
            item_text = _clean_inline_markdown(numbered_match.group(2))
            flowables.append(Paragraph(f"{number}. {escape(item_text)}", styles["bullet"]))
            continue

        paragraph_buffer.append(line)

    _flush_paragraph(flowables, paragraph_buffer, styles["body"])
    if code_lines:
        flowables.append(Preformatted("\n".join(code_lines), styles["code"]))
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
            story.append(Paragraph(f"• {escape(line[4:])}", styles["bullet"]))
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
            story.extend(_markdown_to_flowables(source_text, styles))
            story.append(Spacer(1, 2 * mm))
        story.append(PageBreak())

    story.append(_toc_heading("Appendix A - Apache License 2.0", styles["h1"], 1))
    story.append(Preformatted(APACHE_LICENSE_2_TEXT, styles["code"]))
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
            story.append(Paragraph(f"• {escape(dep)}", styles["bullet"]))
    story.append(Spacer(1, 2 * mm))
    story.append(_toc_heading("B.2 Combined Dependency Index", styles["h2"], 2))
    for dep in all_dependencies:
        story.append(Paragraph(f"• {escape(dep)}", styles["bullet"]))
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
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    story = _build_story(
        repo_root=repo_root,
        title=str(args.title),
        styles=styles,
        generated_at=generated_at,
    )

    doc = ManualDocTemplate(output_path, str(args.title))
    doc.build(story)
    print(f"Manual generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
