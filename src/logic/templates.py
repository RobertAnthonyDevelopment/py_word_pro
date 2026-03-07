import copy
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass


CUSTOM_TEMPLATE_FILE = "pyword_templates.json"
DEFAULT_TEMPLATE_STYLE = "Professional Blue"
DEFAULT_TEMPLATE_CATEGORY = "General"

TEMPLATE_CATEGORIES = [
    "General",
    "Business",
    "Sales",
    "Marketing",
    "Operations",
    "Legal",
    "Meetings",
    "Social Media",
]


def _default_app_data_dir():
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        return os.path.join(base, "PyWord Pro")

    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "PyWord Pro")

    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "pyword_pro")


def _can_write_directory(directory: str) -> bool:
    target_dir = str(directory or "").strip() or "."
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError:
        return False
    tmp_path = ""
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".pyword_templates_probe_", suffix=".tmp", dir=target_dir)
        os.close(fd)
        return True
    except OSError:
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _template_storage_paths():
    raw_name = str(CUSTOM_TEMPLATE_FILE or "").strip() or "pyword_templates.json"
    if os.path.isabs(raw_name):
        return raw_name, raw_name

    legacy_path = os.path.abspath(raw_name)
    app_path = os.path.join(_default_app_data_dir(), raw_name)
    return legacy_path, app_path


def _custom_template_file_path(for_write: bool = False):
    legacy_path, app_path = _template_storage_paths()
    if legacy_path == app_path:
        return legacy_path

    legacy_exists = os.path.exists(legacy_path)
    app_exists = os.path.exists(app_path)

    if for_write:
        if app_exists:
            return app_path
        if legacy_exists:
            legacy_dir = os.path.dirname(os.path.abspath(legacy_path)) or "."
            if _can_write_directory(legacy_dir):
                return legacy_path
        return app_path

    if app_exists:
        return app_path
    if legacy_exists:
        return legacy_path
    return app_path


def _candidate_template_paths(preferred_path: str | None = None) -> list[str]:
    legacy_path, app_path = _template_storage_paths()
    ordered: list[str] = []
    for candidate in (preferred_path, app_path, legacy_path):
        text = str(candidate or "").strip()
        if not text or text in ordered:
            continue
        ordered.append(text)
    return ordered


@dataclass(frozen=True)
class DocumentTemplate:
    template_id: str
    title: str
    description: str
    body: str
    built_in: bool = True
    category: str = DEFAULT_TEMPLATE_CATEGORY
    preferred_style: str = DEFAULT_TEMPLATE_STYLE


@dataclass(frozen=True)
class MarkdownTemplateProfile:
    headings: int
    list_items: int
    checklist_items: int
    table_rows: int
    words: int
    characters: int

TEMPLATE_STYLE_PRESETS: dict[str, dict[str, str | int]] = {
    "Professional Blue": {
        "body_font": "Calibri",
        "body_size": 11,
        "body_fg": "#1f2b3d",
        "muted_fg": "#4d5f7a",
        "accent": "#1f5eff",
        "h1_fg": "#0f2b66",
        "h2_fg": "#174899",
        "h3_fg": "#2158a9",
        "callout_bg": "#eef4ff",
        "table_bg": "#f7f9fd",
        "placeholder_fg": "#445b80",
    },
    "Clean Slate": {
        "body_font": "Segoe UI",
        "body_size": 11,
        "body_fg": "#1c2430",
        "muted_fg": "#5b6572",
        "accent": "#425b76",
        "h1_fg": "#202b37",
        "h2_fg": "#324556",
        "h3_fg": "#41586f",
        "callout_bg": "#f3f5f7",
        "table_bg": "#f7f8fa",
        "placeholder_fg": "#4e6a85",
    },
    "Modern Teal": {
        "body_font": "Calibri",
        "body_size": 11,
        "body_fg": "#123034",
        "muted_fg": "#2d5a61",
        "accent": "#0f8a8a",
        "h1_fg": "#0d4f57",
        "h2_fg": "#0f6b76",
        "h3_fg": "#10808d",
        "callout_bg": "#e8f8f8",
        "table_bg": "#eefafa",
        "placeholder_fg": "#1f6f7a",
    },
}

TODO_LIST_TABLE_BLOCK = (
    "## To-Do List Table\n"
    "| Task | Owner | Priority | Due Date | Status |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| [Task 1] | [Name] | [High] | [YYYY-MM-DD] | [Not Started] |\n"
    "| [Task 2] | [Name] | [Medium] | [YYYY-MM-DD] | [In Progress] |\n"
    "| [Task 3] | [Name] | [Low] | [YYYY-MM-DD] | [Done] |\n"
)


def _with_todo_list_table(body: str) -> str:
    content = str(body or "").rstrip()
    if not content:
        return TODO_LIST_TABLE_BLOCK
    if "## To-Do List Table" in content:
        return content + "\n"
    return f"{content}\n\n{TODO_LIST_TABLE_BLOCK}"


BUILT_IN_TEMPLATES: list[DocumentTemplate] = [
    DocumentTemplate(
        template_id="invoice_estimate_quote",
        title="Invoice / Estimate / Quote",
        description="Billing-ready structure with line items, terms, and payment details.",
        category="Sales",
        body=(
            "# Invoice / Estimate / Quote\n\n"
            "Document Type: [Invoice | Estimate | Quote]\n"
            "Document Number: [###]\n"
            "Issue Date: [YYYY-MM-DD]\n"
            "Due Date: [YYYY-MM-DD]\n\n"
            "## From\n"
            "Business Name:\n"
            "Address:\n"
            "Email:\n"
            "Phone:\n\n"
            "## Bill To\n"
            "Client Name:\n"
            "Company:\n"
            "Address:\n"
            "Email:\n\n"
            "## Line Items\n"
            "1. [Service or Item] - Qty: [ ] - Rate: [ ] - Amount: [ ]\n"
            "2. [Service or Item] - Qty: [ ] - Rate: [ ] - Amount: [ ]\n\n"
            "Subtotal: [ ]\n"
            "Tax: [ ]\n"
            "Total: [ ]\n\n"
            "## Terms\n"
            "- Payment terms:\n"
            "- Late fee policy:\n"
            "- Notes:\n"
        ),
    ),
    DocumentTemplate(
        template_id="proposal",
        title="Proposal",
        description="Client-facing proposal with scope, timeline, and pricing sections.",
        category="Sales",
        body=(
            "# Proposal\n\n"
            "Prepared For: [Client Name]\n"
            "Prepared By: [Your Name / Company]\n"
            "Date: [YYYY-MM-DD]\n\n"
            "## Executive Summary\n"
            "[Brief overview of goals and outcomes]\n\n"
            "## Objectives\n"
            "-\n"
            "-\n\n"
            "## Scope of Work\n"
            "### Included\n"
            "-\n"
            "### Not Included\n"
            "-\n\n"
            "## Timeline\n"
            "- Milestone 1:\n"
            "- Milestone 2:\n"
            "- Delivery date:\n\n"
            "## Investment\n"
            "- Project fee:\n"
            "- Payment schedule:\n\n"
            "## Acceptance\n"
            "Client Name:\n"
            "Signature:\n"
            "Date:\n"
        ),
    ),
    DocumentTemplate(
        template_id="contract_basic",
        title="Contract (Basic)",
        description="Simple agreement outline with deliverables, payment, and termination.",
        category="Legal",
        body=(
            "# Service Agreement (Basic)\n\n"
            "This Agreement is made on [YYYY-MM-DD] between [Provider Name] and [Client Name].\n\n"
            "## 1. Services\n"
            "[Describe the services]\n\n"
            "## 2. Deliverables and Timeline\n"
            "- Deliverable 1:\n"
            "- Deliverable 2:\n"
            "- Final delivery date:\n\n"
            "## 3. Fees and Payment Terms\n"
            "- Total fee:\n"
            "- Payment schedule:\n"
            "- Payment method:\n\n"
            "## 4. Revisions\n"
            "[Number of revisions and process]\n\n"
            "## 5. Confidentiality\n"
            "Both parties agree to keep confidential information private.\n\n"
            "## 6. Termination\n"
            "[Notice period and termination conditions]\n\n"
            "## 7. Signatures\n"
            "Provider Signature: ____________________\n"
            "Client Signature: ______________________\n"
            "Date: _________________________________\n"
        ),
    ),
    DocumentTemplate(
        template_id="client_brief",
        title="Client / Creative Brief",
        description="Structured brief for goals, audience, messaging, and deliverables.",
        category="Business",
        body=(
            "# Client / Creative Brief\n\n"
            "Project Name:\n"
            "Client:\n"
            "Owner:\n"
            "Date:\n\n"
            "## Project Background\n"
            "[Context and problem statement]\n\n"
            "## Goals\n"
            "-\n"
            "-\n\n"
            "## Target Audience\n"
            "- Primary:\n"
            "- Secondary:\n\n"
            "## Core Message\n"
            "[Main value proposition]\n\n"
            "## Deliverables\n"
            "-\n"
            "-\n\n"
            "## Brand and Tone Requirements\n"
            "-\n"
            "-\n\n"
            "## Timeline and Deadlines\n"
            "- Draft due:\n"
            "- Final due:\n\n"
            "## Approval Stakeholders\n"
            "-\n"
            "-\n"
        ),
    ),
    DocumentTemplate(
        template_id="meeting_notes",
        title="Meeting Notes + Action Items",
        description="Meeting agenda, notes, decisions, and assigned actions.",
        category="Meetings",
        body=(
            "# Meeting Notes\n\n"
            "Meeting Title:\n"
            "Date:\n"
            "Time:\n"
            "Attendees:\n\n"
            "## Agenda\n"
            "1.\n"
            "2.\n"
            "3.\n\n"
            "## Discussion Notes\n"
            "-\n"
            "-\n\n"
            "## Decisions\n"
            "-\n"
            "-\n\n"
            "## Action Items\n"
            "1. Task: [ ] | Owner: [ ] | Due: [ ]\n"
            "2. Task: [ ] | Owner: [ ] | Due: [ ]\n\n"
            "## Next Meeting\n"
            "Date:\n"
            "Topics:\n"
        ),
    ),
    DocumentTemplate(
        template_id="press_kit_one_pager",
        title="Press Kit / One-Pager",
        description="Compact media summary with company info and contact details.",
        category="Marketing",
        body=(
            "# Press Kit / One-Pager\n\n"
            "Company / Product Name:\n"
            "Tagline:\n"
            "Website:\n\n"
            "## Elevator Pitch\n"
            "[Two to three sentences]\n\n"
            "## Key Facts\n"
            "- Founded:\n"
            "- Headquarters:\n"
            "- Team size:\n"
            "- Core offering:\n\n"
            "## Product / Service Highlights\n"
            "-\n"
            "-\n\n"
            "## Recent Milestones\n"
            "-\n"
            "-\n\n"
            "## Media Assets\n"
            "- Logo:\n"
            "- Founder photos:\n"
            "- Product screenshots:\n\n"
            "## Press Contact\n"
            "Name:\n"
            "Email:\n"
            "Phone:\n"
        ),
    ),
    DocumentTemplate(
        template_id="sop_checklist",
        title="SOP / Checklist",
        description="Process document with prerequisites, steps, QA, and sign-off.",
        category="Operations",
        body=(
            "# Standard Operating Procedure (SOP)\n\n"
            "Process Name:\n"
            "Owner:\n"
            "Version:\n"
            "Effective Date:\n\n"
            "## Purpose\n"
            "[Why this process exists]\n\n"
            "## Scope\n"
            "[Where and when this SOP applies]\n\n"
            "## Prerequisites\n"
            "-\n"
            "-\n\n"
            "## Procedure Steps\n"
            "1.\n"
            "2.\n"
            "3.\n\n"
            "## Quality Checks\n"
            "-\n"
            "-\n\n"
            "## Checklist\n"
            "- [ ] Step 1 completed\n"
            "- [ ] Step 2 completed\n"
            "- [ ] Step 3 completed\n\n"
            "## Sign-Off\n"
            "Completed By:\n"
            "Date:\n"
        ),
    ),
    DocumentTemplate(
        template_id="marketing_doc_pack",
        title="Marketing Doc Pack",
        description="Flyer copy, email draft, and social post plan in one template.",
        category="Marketing",
        body=(
            "# Marketing Document Pack\n\n"
            "Campaign Name:\n"
            "Audience:\n"
            "Launch Date:\n\n"
            "## Flyer Copy\n"
            "Headline:\n"
            "Subheadline:\n"
            "Body Copy:\n"
            "Call To Action:\n\n"
            "## Email Draft\n"
            "Subject Line:\n"
            "Preview Text:\n"
            "Email Body:\n"
            "Call To Action:\n\n"
            "## Social Post Plan\n"
            "Platform: [LinkedIn | Instagram | X | Facebook]\n"
            "Post Copy:\n"
            "Hashtags:\n"
            "Asset Needed:\n"
            "Publish Date:\n"
        ),
    ),
    DocumentTemplate(
        template_id="task_tracker_worklist",
        title="Task Tracker + Worklist",
        description="Prioritized task planner with backlog, sprint, blockers, and follow-ups.",
        category="Operations",
        body=(
            "# Task Tracker + Worklist\n\n"
            "Project / Client:\n"
            "Owner:\n"
            "Reporting Week:\n\n"
            "## Priority Goals\n"
            "1.\n"
            "2.\n"
            "3.\n\n"
            "## Backlog\n"
            "- [ ]\n"
            "- [ ]\n"
            "- [ ]\n\n"
            "## This Week\n"
            "- [ ] Must Do\n"
            "- [ ] Should Do\n"
            "- [ ] Nice To Have\n\n"
            "## Blockers / Dependencies\n"
            "- Blocker:\n"
            "- Dependency:\n\n"
            "## Notes and Decisions\n"
            "-\n"
            "-\n\n"
            "## Follow-Up\n"
            "Next Review Date:\n"
            "Escalations:\n"
        ),
    ),
    DocumentTemplate(
        template_id="social_linkedin_post",
        title="Social: LinkedIn Post",
        description="Professional LinkedIn post with hook, insight, CTA, and hashtags.",
        category="Social Media",
        body=(
            "# LinkedIn Post Template\n\n"
            "Goal: [Thought leadership | Lead gen | Hiring | Product update]\n"
            "Audience:\n\n"
            "## Hook\n"
            "[1-2 lines to stop the scroll]\n\n"
            "## Main Insight\n"
            "[Core point, lesson, or announcement]\n\n"
            "## Value Points\n"
            "-\n"
            "-\n"
            "-\n\n"
            "## CTA\n"
            "[Comment, DM, click, sign up, etc.]\n\n"
            "## Hashtags\n"
            "# # #\n"
        ),
    ),
    DocumentTemplate(
        template_id="social_instagram_caption",
        title="Social: Instagram Caption",
        description="Instagram caption framework with hook, story, CTA, and hashtags.",
        category="Social Media",
        body=(
            "# Instagram Caption Template\n\n"
            "Post Type: [Carousel | Reel | Photo]\n"
            "Objective: [Awareness | Engagement | Conversion]\n\n"
            "## Hook Line\n"
            "[Attention-grabbing opener]\n\n"
            "## Caption Body\n"
            "[Story/value in short paragraphs]\n\n"
            "## CTA\n"
            "[Save this, share, comment, link in bio]\n\n"
            "## Hashtags\n"
            "# # # # #\n"
        ),
    ),
    DocumentTemplate(
        template_id="social_x_thread",
        title="Social: X Thread",
        description="Thread format with opening claim and numbered tweet flow.",
        category="Social Media",
        body=(
            "# X Thread Template\n\n"
            "Topic:\n"
            "Audience:\n\n"
            "## Tweet 1 (Hook)\n"
            "[Bold claim, question, or insight]\n\n"
            "## Tweet 2-6 (Body)\n"
            "2. \n"
            "3. \n"
            "4. \n"
            "5. \n"
            "6. \n\n"
            "## Final Tweet (CTA)\n"
            "[Follow, reply, visit link]\n"
        ),
    ),
    DocumentTemplate(
        template_id="social_tiktok_reel_script",
        title="Social: TikTok / Reel Script",
        description="Short-form video script with hook, beats, and on-screen text.",
        category="Social Media",
        body=(
            "# TikTok / Reel Script\n\n"
            "Video Goal:\n"
            "Target Length: [15s | 30s | 60s]\n\n"
            "## Hook (0-3s)\n"
            "[Immediate attention statement]\n\n"
            "## Script Beats\n"
            "1. [ ]\n"
            "2. [ ]\n"
            "3. [ ]\n\n"
            "## On-Screen Text\n"
            "-\n"
            "-\n\n"
            "## CTA\n"
            "[Follow for more, comment keyword, etc.]\n"
        ),
    ),
    DocumentTemplate(
        template_id="social_content_calendar_week",
        title="Social: Weekly Content Calendar",
        description="Simple 7-day content planning grid with channels and owners.",
        category="Social Media",
        body=(
            "# Weekly Social Content Calendar\n\n"
            "Week of:\n"
            "Campaign:\n\n"
            "## Plan\n"
            "Monday: Platform [ ] | Topic [ ] | Owner [ ]\n"
            "Tuesday: Platform [ ] | Topic [ ] | Owner [ ]\n"
            "Wednesday: Platform [ ] | Topic [ ] | Owner [ ]\n"
            "Thursday: Platform [ ] | Topic [ ] | Owner [ ]\n"
            "Friday: Platform [ ] | Topic [ ] | Owner [ ]\n"
            "Saturday: Platform [ ] | Topic [ ] | Owner [ ]\n"
            "Sunday: Platform [ ] | Topic [ ] | Owner [ ]\n\n"
            "## Notes\n"
            "-\n"
        ),
    ),
]


def _inject_builtin_todo_tables(templates: list[DocumentTemplate]) -> list[DocumentTemplate]:
    enriched: list[DocumentTemplate] = []
    for template in templates:
        enriched.append(
            DocumentTemplate(
                template_id=template.template_id,
                title=template.title,
                description=template.description,
                body=_with_todo_list_table(template.body),
                built_in=template.built_in,
                category=template.category,
                preferred_style=template.preferred_style,
            )
        )
    return enriched


BUILT_IN_TEMPLATES = _inject_builtin_todo_tables(BUILT_IN_TEMPLATES)


def _read_custom_payload() -> list[dict]:
    preferred_path = _custom_template_file_path(for_write=False)
    for path in _candidate_template_paths(preferred_path):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                entries = data.get("templates", [])
            elif isinstance(data, list):
                entries = data
            else:
                continue
            if not isinstance(entries, list):
                continue
            return entries
        except (OSError, json.JSONDecodeError):
            continue
    return []


def _write_custom_payload(entries: list[dict]) -> None:
    preferred_path = _custom_template_file_path(for_write=True)
    last_error = None
    for out_path in _candidate_template_paths(preferred_path):
        directory = os.path.dirname(os.path.abspath(out_path)) or "."
        tmp_path = ""
        try:
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix=".pyword_templates_", suffix=".json", dir=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"templates": entries}, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, out_path)
            return
        except OSError as exc:
            last_error = exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    if last_error is not None:
        raise last_error


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return cleaned or "template"


def _normalize_template_id(value: str | None, fallback_title: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        candidate = f"custom_{_slug(fallback_title)}"
    if not candidate.startswith("custom_"):
        candidate = f"custom_{candidate}"
    return candidate


def _next_available_id(base_id: str, used_ids: set[str]) -> str:
    template_id = base_id
    suffix = 2
    while template_id in used_ids:
        template_id = f"{base_id}_{suffix}"
        suffix += 1
    return template_id


def _normalize_category(value: str | None) -> str:
    candidate = str(value or "").strip()
    if candidate in TEMPLATE_CATEGORIES:
        return candidate
    lowered = candidate.casefold()
    for option in TEMPLATE_CATEGORIES:
        if option.casefold() == lowered:
            return option
    return DEFAULT_TEMPLATE_CATEGORY


def _normalize_style(value: str | None) -> str:
    candidate = str(value or "").strip()
    if candidate in TEMPLATE_STYLE_PRESETS:
        return candidate
    lowered = candidate.casefold()
    for option in TEMPLATE_STYLE_PRESETS.keys():
        if option.casefold() == lowered:
            return option
    return DEFAULT_TEMPLATE_STYLE


def _extract_markdown_front_matter(markdown_text: str) -> tuple[dict[str, str], str]:
    text = str(markdown_text or "")
    if not text.startswith("---\n"):
        return {}, text

    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    closing_idx = -1
    for idx in range(1, min(len(lines), 120)):
        marker = lines[idx].strip()
        if marker in {"---", "..."}:
            closing_idx = idx
            break
    if closing_idx < 0:
        return {}, text

    front_matter: dict[str, str] = {}
    for raw in lines[1:closing_idx]:
        line = str(raw or "").strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        clean_key = str(key or "").strip().casefold()
        clean_value = str(value or "").strip().strip("\"'")
        if clean_key:
            front_matter[clean_key] = clean_value

    body = "\n".join(lines[closing_idx + 1 :])
    return front_matter, body


def _derive_title_from_markdown(body: str, source_name: str = "") -> str:
    text = str(body or "")
    heading_match = re.search(r"(?m)^\s{0,3}#\s+(.+?)\s*$", text)
    if heading_match:
        title = str(heading_match.group(1) or "").strip().strip("#").strip()
        if title:
            return title

    for line in text.splitlines():
        candidate = str(line or "").strip()
        if not candidate:
            continue
        candidate = re.sub(r"^[>\-\*\d\.\)\s\[\]xX]+", "", candidate).strip()
        if candidate:
            return candidate[:120]

    source_base = os.path.splitext(os.path.basename(str(source_name or "").strip()))[0].strip()
    if source_base:
        return source_base.replace("_", " ").replace("-", " ").strip().title()
    return "Imported Template"


def _derive_description_from_markdown(body: str) -> str:
    text = str(body or "")
    for line in text.splitlines():
        candidate = str(line or "").strip()
        if not candidate:
            continue
        if candidate.startswith("#"):
            continue
        candidate = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", candidate)
        candidate = candidate.strip()
        if candidate:
            if len(candidate) > 140:
                return candidate[:137].rstrip() + "..."
            return candidate
    return "Imported markdown template"


def _normalize_imported_markdown_body(body: str, title: str) -> str:
    normalized = str(body or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.strip("\n")
    if not normalized.strip():
        raise ValueError("Markdown file content is empty.")
    if not re.search(r"(?m)^\s{0,3}#\s+\S", normalized):
        heading = (title or "Imported Template").strip() or "Imported Template"
        normalized = f"# {heading}\n\n{normalized}"
    return normalized + "\n"


def parse_markdown_template_content(
    markdown_text: str,
    *,
    source_name: str = "",
    fallback_category: str | None = None,
    fallback_style: str | None = None,
) -> dict[str, str]:
    text = str(markdown_text or "")
    text = text.replace("\ufeff", "")
    front_matter, body_block = _extract_markdown_front_matter(text)
    title = (
        str(front_matter.get("title", "")).strip()
        or _derive_title_from_markdown(body_block, source_name=source_name)
    )
    body = _normalize_imported_markdown_body(body_block, title=title)
    description = str(front_matter.get("description", "")).strip() or _derive_description_from_markdown(body)
    category_value = (
        str(front_matter.get("category", "")).strip()
        or str(fallback_category or "").strip()
        or DEFAULT_TEMPLATE_CATEGORY
    )
    style_value = (
        str(front_matter.get("preferred_style", "")).strip()
        or str(front_matter.get("style", "")).strip()
        or str(fallback_style or "").strip()
        or DEFAULT_TEMPLATE_STYLE
    )

    return {
        "title": title,
        "description": description,
        "body": body,
        "category": _normalize_category(category_value),
        "preferred_style": _normalize_style(style_value),
    }


def import_markdown_template_file(
    path: str,
    *,
    overwrite_existing: bool = False,
    fallback_category: str | None = None,
    fallback_style: str | None = None,
) -> DocumentTemplate:
    source_path = str(path or "").strip()
    if not source_path:
        raise ValueError("Markdown file path is required.")
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)

    try:
        with open(source_path, "r", encoding="utf-8-sig") as handle:
            content = handle.read()
    except UnicodeDecodeError:
        with open(source_path, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.read()

    payload = parse_markdown_template_content(
        content,
        source_name=os.path.basename(source_path),
        fallback_category=fallback_category,
        fallback_style=fallback_style,
    )
    return save_custom_template(
        title=payload["title"],
        description=payload["description"],
        body=payload["body"],
        category=payload["category"],
        preferred_style=payload["preferred_style"],
        overwrite_existing=overwrite_existing,
    )


def summarize_template_markdown(body: str) -> MarkdownTemplateProfile:
    text = str(body or "")
    lines = text.splitlines()
    heading_count = sum(1 for line in lines if re.match(r"^\s{0,3}#{1,6}\s+\S", str(line or "")))
    list_count = sum(1 for line in lines if re.match(r"^\s*(?:[-*+]|\d+\.)\s+\S", str(line or "")))
    checklist_count = sum(1 for line in lines if re.match(r"^\s*[-*+]\s+\[[ xX]\]\s+\S", str(line or "")))
    table_count = sum(1 for line in lines if "|" in str(line or "") and re.search(r"\S", str(line or "")))
    words = len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))
    return MarkdownTemplateProfile(
        headings=heading_count,
        list_items=list_count,
        checklist_items=checklist_count,
        table_rows=table_count,
        words=words,
        characters=len(text),
    )


def _normalize_custom(entries: list[dict]) -> list[DocumentTemplate]:
    templates: list[DocumentTemplate] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        template_id = _normalize_template_id(item.get("template_id"), str(item.get("title", "")))
        title = str(item.get("title", "")).strip()
        body_raw = item.get("body", "")
        if body_raw is None:
            body = ""
        elif isinstance(body_raw, str):
            body = body_raw
        else:
            body = str(body_raw)
        description = str(item.get("description", "")).strip() or "Custom template"
        category = _normalize_category(item.get("category"))
        preferred_style = _normalize_style(item.get("preferred_style"))
        if not title or not body.strip():
            continue
        templates.append(
            DocumentTemplate(
                template_id=template_id,
                title=title,
                description=description,
                body=body,
                built_in=False,
                category=category,
                preferred_style=preferred_style,
            )
        )
    return templates


def list_builtin_templates() -> list[DocumentTemplate]:
    return copy.deepcopy(BUILT_IN_TEMPLATES)


def list_custom_templates() -> list[DocumentTemplate]:
    return _normalize_custom(_read_custom_payload())


def list_templates() -> list[DocumentTemplate]:
    return list_builtin_templates() + list_custom_templates()


def list_template_style_presets() -> list[str]:
    return list(TEMPLATE_STYLE_PRESETS.keys())


def list_template_categories() -> list[str]:
    return list(TEMPLATE_CATEGORIES)


def get_template_style_preset(style_name: str | None) -> dict[str, str | int]:
    candidate = (style_name or "").strip()
    if candidate in TEMPLATE_STYLE_PRESETS:
        return copy.deepcopy(TEMPLATE_STYLE_PRESETS[candidate])
    return copy.deepcopy(TEMPLATE_STYLE_PRESETS[DEFAULT_TEMPLATE_STYLE])


def get_template_by_id(template_id: str) -> DocumentTemplate | None:
    if not template_id:
        return None
    for template in list_templates():
        if template.template_id == template_id:
            return template
    return None


def save_custom_template(
    title: str,
    description: str,
    body: str,
    *,
    category: str | None = None,
    preferred_style: str | None = None,
    overwrite_existing: bool = False,
) -> DocumentTemplate:
    clean_title = (title or "").strip()
    body_text = "" if body is None else str(body)
    clean_desc = (description or "").strip() or "Custom template"
    clean_category = _normalize_category(category)
    clean_style = _normalize_style(preferred_style)
    if not clean_title:
        raise ValueError("Template title is required.")
    if not body_text.strip():
        raise ValueError("Template content is empty.")

    current_entries = [asdict(t) for t in list_custom_templates()]
    template_id = ""

    def _entry_with_id(value: str) -> dict:
        return {
            "template_id": value,
            "title": clean_title,
            "description": clean_desc,
            "body": body_text,
            "built_in": False,
            "category": clean_category,
            "preferred_style": clean_style,
        }

    if overwrite_existing:
        title_key = clean_title.casefold()
        matching_indices = [
            idx
            for idx, item in enumerate(current_entries)
            if str(item.get("title", "")).strip().casefold() == title_key
        ]
        if matching_indices:
            first_match = current_entries[matching_indices[0]]
            base_existing_id = _normalize_template_id(first_match.get("template_id"), clean_title)
            used_ids = {
                str(item.get("template_id", "")).strip()
                for idx, item in enumerate(current_entries)
                if idx not in matching_indices
            }
            template_id = _next_available_id(base_existing_id, used_ids)
            replacement = _entry_with_id(template_id)

            deduped_entries: list[dict] = []
            inserted = False
            for idx, item in enumerate(current_entries):
                if idx in matching_indices:
                    if not inserted:
                        deduped_entries.append(replacement)
                        inserted = True
                    continue
                deduped_entries.append(item)

            _write_custom_payload(deduped_entries)
            return DocumentTemplate(
                template_id=template_id,
                title=clean_title,
                description=clean_desc,
                body=body_text,
                built_in=False,
                category=clean_category,
                preferred_style=clean_style,
            )

    used_ids = {str(item.get("template_id", "")) for item in current_entries}
    base_id = _normalize_template_id(None, clean_title)
    template_id = _next_available_id(base_id, used_ids)

    new_template = DocumentTemplate(
        template_id=template_id,
        title=clean_title,
        description=clean_desc,
        body=body_text,
        built_in=False,
        category=clean_category,
        preferred_style=clean_style,
    )
    current_entries.append(asdict(new_template))
    _write_custom_payload(current_entries)
    return new_template
