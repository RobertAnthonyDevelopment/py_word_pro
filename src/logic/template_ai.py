import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateAIDraft:
    title: str
    description: str
    body: str
    category: str
    preferred_style: str
    source: str


_AI_CATEGORIES = {
    "invoice": "Sales",
    "estimate": "Sales",
    "quote": "Sales",
    "proposal": "Sales",
    "contract": "Legal",
    "agreement": "Legal",
    "brief": "Business",
    "meeting": "Meetings",
    "minutes": "Meetings",
    "press": "Marketing",
    "one pager": "Marketing",
    "sop": "Operations",
    "checklist": "Operations",
    "process": "Operations",
    "social": "Social Media",
    "linkedin": "Social Media",
    "instagram": "Social Media",
    "tiktok": "Social Media",
    "marketing": "Marketing",
}

_CATEGORY_STYLE = {
    "Sales": "Professional Blue",
    "Legal": "Clean Slate",
    "Business": "Professional Blue",
    "Meetings": "Clean Slate",
    "Marketing": "Modern Teal",
    "Operations": "Clean Slate",
    "Social Media": "Modern Teal",
    "General": "Professional Blue",
}


def generate_template_draft(
    prompt: str,
    *,
    category: str | None = None,
    context_text: str | None = None,
) -> TemplateAIDraft:
    clean_prompt = (prompt or "").strip()
    if not clean_prompt:
        context_snippet = _first_context_sentence(context_text)
        clean_prompt = context_snippet or "General business document template"

    remote = _generate_remote_draft(clean_prompt, category=category, context_text=context_text)
    if remote:
        return remote
    return _generate_local_draft(clean_prompt, category=category, context_text=context_text)


def _generate_remote_draft(
    prompt: str,
    *,
    category: str | None = None,
    context_text: str | None = None,
) -> TemplateAIDraft | None:
    api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return None

    user_context = _first_context_sentence(context_text)
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You generate polished markdown document templates for small business owners and creatives. "
                    "Return strict JSON with keys: title, description, category, preferred_style, body. "
                    "body must be markdown with headings and practical placeholders."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Prompt: {prompt}\n"
                    f"Preferred category: {category or 'auto'}\n"
                    f"Context: {user_context or 'none'}\n"
                    "Use one category from: General, Business, Sales, Marketing, Operations, Legal, Meetings, Social Media.\n"
                    "Use one style from: Professional Blue, Clean Slate, Modern Teal."
                ),
            },
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        content = str(
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        ).strip()
        if not content:
            return None
        parsed = _safe_json_extract(content)
        if not parsed:
            return None
        draft = _normalize_draft_payload(parsed, source="openai")
        return draft
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError):
        return None


def _safe_json_extract(text: str) -> dict | None:
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("{") and raw.endswith("}"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


def _normalize_draft_payload(payload: dict, *, source: str) -> TemplateAIDraft:
    title = str(payload.get("title", "")).strip() or "Custom Template"
    description = str(payload.get("description", "")).strip() or "AI-generated markdown template."
    body = str(payload.get("body", "")).replace("\r\n", "\n").replace("\r", "\n")
    if not body.strip():
        body = _default_markdown_for_title(title)
    category = _normalize_category(str(payload.get("category", "")).strip())
    preferred_style = _normalize_style(str(payload.get("preferred_style", "")).strip(), category=category)
    return TemplateAIDraft(
        title=title,
        description=description,
        body=body,
        category=category,
        preferred_style=preferred_style,
        source=source,
    )


def _generate_local_draft(
    prompt: str,
    *,
    category: str | None = None,
    context_text: str | None = None,
) -> TemplateAIDraft:
    inferred_category = _normalize_category(category or _infer_category(prompt))
    title = _suggest_title(prompt)
    description = _suggest_description(prompt)
    style = _normalize_style("", category=inferred_category)
    context_hint = _first_context_sentence(context_text)

    body = _build_markdown_body(
        title=title,
        prompt=prompt,
        category=inferred_category,
        context_hint=context_hint,
    )
    return TemplateAIDraft(
        title=title,
        description=description,
        body=body,
        category=inferred_category,
        preferred_style=style,
        source="local",
    )


def _normalize_category(value: str) -> str:
    candidate = (value or "").strip()
    if candidate in _CATEGORY_STYLE:
        return candidate
    lowered = candidate.casefold()
    for option in _CATEGORY_STYLE.keys():
        if option.casefold() == lowered:
            return option
    return "General"


def _normalize_style(value: str, *, category: str) -> str:
    candidate = (value or "").strip()
    valid = {"Professional Blue", "Clean Slate", "Modern Teal"}
    if candidate in valid:
        return candidate
    lowered = candidate.casefold()
    for option in valid:
        if option.casefold() == lowered:
            return option
    return _CATEGORY_STYLE.get(category, "Professional Blue")


def _infer_category(prompt: str) -> str:
    text = (prompt or "").lower()
    for term, category in _AI_CATEGORIES.items():
        if term in text:
            return category
    return "General"


def _suggest_title(prompt: str) -> str:
    text = re.sub(r"\s+", " ", (prompt or "").strip())
    if not text:
        return "Custom Template"
    match = re.search(r"(invoice|estimate|quote|proposal|contract|brief|meeting|sop|checklist|press|memo)", text, re.IGNORECASE)
    if match:
        keyword = match.group(1).title()
        return f"{keyword} Template"
    words = [word for word in re.split(r"[^A-Za-z0-9]+", text) if word]
    compact = " ".join(words[:6]).strip()
    if not compact:
        return "Custom Template"
    return f"{compact.title()} Template"


def _suggest_description(prompt: str) -> str:
    cleaned = re.sub(r"\s+", " ", (prompt or "").strip())
    if not cleaned:
        return "AI-generated markdown template."
    return f"AI-generated template for: {cleaned[:120]}".strip()


def _first_context_sentence(context_text: str | None) -> str:
    text = (context_text or "").strip()
    if not text:
        return ""
    sentence = re.split(r"[.!?\n]", text, maxsplit=1)[0].strip()
    if not sentence:
        return ""
    return sentence[:220]


def _default_markdown_for_title(title: str) -> str:
    return (
        f"# {title}\n\n"
        "## Overview\n"
        "[Summarize the objective]\n\n"
        "## Key Details\n"
        "- [Detail 1]\n"
        "- [Detail 2]\n\n"
        "## Timeline\n"
        "- Start:\n"
        "- Deadline:\n\n"
        "## Approval\n"
        "Owner:\n"
        "Date:\n"
    )


def _build_markdown_body(title: str, prompt: str, category: str, context_hint: str) -> str:
    overview = context_hint or prompt.strip() or "Document objective"
    if category == "Sales":
        return (
            f"# {title}\n\n"
            "## Client and Opportunity\n"
            "Client Name:\n"
            "Contact:\n"
            "Opportunity:\n\n"
            "## Scope and Deliverables\n"
            "- Deliverable 1\n"
            "- Deliverable 2\n\n"
            "## Pricing\n"
            "| Item | Qty | Rate | Amount |\n"
            "|---|---:|---:|---:|\n"
            "| [Service] | 1 | 0.00 | 0.00 |\n\n"
            "## Terms\n"
            "- Payment schedule:\n"
            "- Valid until:\n\n"
            "## Notes\n"
            f"{overview}\n"
        )
    if category == "Legal":
        return (
            f"# {title}\n\n"
            "## Parties\n"
            "Provider:\n"
            "Client:\n"
            "Effective Date:\n\n"
            "## Agreement Scope\n"
            "[Define services and boundaries]\n\n"
            "## Compensation and Payment\n"
            "- Fee:\n"
            "- Payment terms:\n\n"
            "## Confidentiality and IP\n"
            "- Confidential information handling:\n"
            "- Ownership terms:\n\n"
            "## Termination\n"
            "[Conditions and notice period]\n\n"
            "## Signatures\n"
            "Provider Signature:\n"
            "Client Signature:\n"
        )
    if category == "Meetings":
        return (
            f"# {title}\n\n"
            "Date:\n"
            "Attendees:\n"
            "Facilitator:\n\n"
            "## Agenda\n"
            "1. \n"
            "2. \n"
            "3. \n\n"
            "## Notes\n"
            "- \n"
            "- \n\n"
            "## Decisions\n"
            "- \n\n"
            "## Action Items\n"
            "- [ ] Task | owner: [Name] | due: [YYYY-MM-DD] | priority: [High]\n"
            "- [ ] Task | owner: [Name] | due: [YYYY-MM-DD]\n"
        )
    if category == "Social Media":
        return (
            f"# {title}\n\n"
            "## Campaign Goal\n"
            f"{overview}\n\n"
            "## Audience\n"
            "- Primary:\n"
            "- Secondary:\n\n"
            "## Content Plan\n"
            "| Platform | Angle | CTA | Owner | Publish Date |\n"
            "|---|---|---|---|---|\n"
            "| LinkedIn | | | | |\n"
            "| Instagram | | | | |\n"
            "| X / Thread | | | | |\n\n"
            "## Assets Checklist\n"
            "- [ ] Copy draft\n"
            "- [ ] Visual assets\n"
            "- [ ] Hashtags and links\n"
        )
    if category == "Marketing":
        return (
            f"# {title}\n\n"
            "## Objective\n"
            f"{overview}\n\n"
            "## Messaging\n"
            "- Core value proposition:\n"
            "- Supporting points:\n\n"
            "## Deliverables\n"
            "- Flyer copy\n"
            "- Email draft\n"
            "- Social post set\n\n"
            "## Timeline\n"
            "| Milestone | Owner | Due |\n"
            "|---|---|---|\n"
            "| Draft | | |\n"
            "| Review | | |\n"
            "| Publish | | |\n"
        )
    if category == "Operations":
        return (
            f"# {title}\n\n"
            "## Purpose\n"
            f"{overview}\n\n"
            "## Scope\n"
            "[Where this process applies]\n\n"
            "## Procedure\n"
            "1. Step 1\n"
            "2. Step 2\n"
            "3. Step 3\n\n"
            "## Quality Checklist\n"
            "- [ ] Verification 1\n"
            "- [ ] Verification 2\n\n"
            "## Ownership\n"
            "Process Owner:\n"
            "Review Cadence:\n"
        )
    if category == "Business":
        return (
            f"# {title}\n\n"
            "## Brief Overview\n"
            f"{overview}\n\n"
            "## Goals\n"
            "- Goal 1\n"
            "- Goal 2\n\n"
            "## Requirements\n"
            "- Requirement 1\n"
            "- Requirement 2\n\n"
            "## Deliverables\n"
            "- \n"
            "- \n\n"
            "## Approval and Next Steps\n"
            "Owner:\n"
            "Deadline:\n"
        )
    return _default_markdown_for_title(title)
