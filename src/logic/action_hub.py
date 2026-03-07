import datetime as dt
import html
import mimetypes
import re
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class ActionItem:
    task: str
    line_number: int
    line_index: str
    line_text: str
    status: str
    owner: str | None
    due_date: dt.date | None
    urgency: str
    kind: str
    priority: str = "Normal"
    effort: str = "Standard"
    project: str | None = None
    workstream: str = "General"
    focus_score: int = 0

    @property
    def due_display(self) -> str:
        if not self.due_date:
            return "-"
        return self.due_date.isoformat()


_RE_CHECKBOX = re.compile(r"^\s*[-*]?\s*\[(?P<mark>[ xX])\]\s+(?P<task>.+?)\s*$")
_RE_PREFIX_OPEN = re.compile(r"^\s*(?:todo|action|ai)\s*[:\-]\s*(?P<task>.+?)\s*$", re.IGNORECASE)
_RE_PREFIX_DONE = re.compile(r"^\s*(?:done|completed|complete)\s*[:\-]\s*(?P<task>.+?)\s*$", re.IGNORECASE)
_RE_TASK_FIELD = re.compile(r"\btask\s*:\s*(?P<task>[^|]+)", re.IGNORECASE)
_RE_OWNER_FIELD = re.compile(r"\bowner\s*:\s*(?P<owner>[^|,]+)", re.IGNORECASE)
_RE_OWNER_TAG = re.compile(r"@([A-Za-z0-9_.-]+)")
_RE_DUE_FIELD = re.compile(r"\bdue\s*:\s*(?P<due>[^|,]+)", re.IGNORECASE)
_RE_PRIORITY_FIELD = re.compile(r"\bpriority\s*:\s*(?P<priority>[^|,]+)", re.IGNORECASE)
_RE_EFFORT_FIELD = re.compile(r"\beffort\s*:\s*(?P<effort>[^|,]+)", re.IGNORECASE)
_RE_PROJECT_FIELD = re.compile(r"\b(?:project|client)\s*:\s*(?P<project>[^|,]+)", re.IGNORECASE)
_RE_DATE_ISO = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_RE_DATE_US = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_RE_TRAILING_OWNER_TOKEN = re.compile(r"(?i)(?:\s*\|\s*|\s+)owner\s*:\s*[^|,]+$")
_RE_TRAILING_DUE_TOKEN = re.compile(r"(?i)(?:\s*\|\s*|\s+)due\s*:\s*[^|,]+$")
_RE_TRAILING_PRIORITY_TOKEN = re.compile(r"(?i)(?:\s*\|\s*|\s+)priority\s*:\s*[^|,]+$")
_RE_TRAILING_EFFORT_TOKEN = re.compile(r"(?i)(?:\s*\|\s*|\s+)effort\s*:\s*[^|,]+$")
_RE_TRAILING_PROJECT_TOKEN = re.compile(r"(?i)(?:\s*\|\s*|\s+)(?:project|client)\s*:\s*[^|,]+$")
_META_TOKEN_PREFIXES = ("owner:", "due:", "priority:", "effort:", "project:", "client:")
_UNSET = object()


def _parse_due_date(text: str) -> dt.date | None:
    if not text:
        return None

    field = _RE_DUE_FIELD.search(text)
    if field:
        raw = field.group("due").strip()
        parsed = parse_due_input(raw)
        if parsed:
            return parsed
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return dt.datetime.strptime(raw, fmt).date()
            except ValueError:
                pass

    for regex, fmt in ((_RE_DATE_ISO, "%Y-%m-%d"), (_RE_DATE_US, "%m/%d/%Y")):
        m = regex.search(text)
        if not m:
            continue
        try:
            return dt.datetime.strptime(m.group(1), fmt).date()
        except ValueError:
            continue
    return None


def parse_due_input(raw: str) -> dt.date | None:
    value = (raw or "").strip()
    if not value:
        return None
    lowered = value.lower()
    today = dt.date.today()
    if lowered in {"today", "tod"}:
        return today
    if lowered in {"tomorrow", "tmr", "tmrw"}:
        return today + dt.timedelta(days=1)
    if lowered in {"next week", "in 7 days", "+7d"}:
        return today + dt.timedelta(days=7)
    if lowered.startswith("+") and lowered.endswith("d"):
        try:
            days = int(lowered[1:-1])
            if days >= 0:
                return today + dt.timedelta(days=days)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _extract_owner(text: str) -> str | None:
    if not text:
        return None
    field = _RE_OWNER_FIELD.search(text)
    if field:
        owner = field.group("owner").strip()
        return owner or None
    tag = _RE_OWNER_TAG.search(text)
    if tag:
        return f"@{tag.group(1)}"
    return None


def _extract_priority(text: str) -> str:
    if not text:
        return "Normal"
    field = _RE_PRIORITY_FIELD.search(text)
    if not field:
        return "Normal"
    return _normalize_priority(field.group("priority"))


def _extract_effort(text: str) -> str:
    if not text:
        return "Standard"
    field = _RE_EFFORT_FIELD.search(text)
    if not field:
        return "Standard"
    return _normalize_effort(field.group("effort"))


def _extract_project(text: str) -> str | None:
    if not text:
        return None
    field = _RE_PROJECT_FIELD.search(text)
    if not field:
        return None
    project = field.group("project").strip()
    return project or None


def _normalize_priority(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in {"", "normal", "default"}:
        return "Normal"
    if value in {"p0", "critical", "crit", "urgent", "blocker"}:
        return "Critical"
    if value in {"p1", "high", "important"}:
        return "High"
    if value in {"p2", "medium", "med"}:
        return "Medium"
    if value in {"p3", "low", "later"}:
        return "Low"
    return "Normal"


def _normalize_effort(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in {"quick", "small", "short", "15m", "30m"}:
        return "Quick"
    if value in {"deep", "large", "long", "focus", "2h", "4h"}:
        return "Deep"
    if value in {"medium", "std", "standard", "normal", "1h"}:
        return "Standard"
    return "Standard"


def _infer_workstream(task: str, project: str | None) -> str:
    haystack = f"{task} {project or ''}".lower()
    rules = (
        ("Sales", ("proposal", "invoice", "quote", "lead", "contract", "pricing", "close deal")),
        ("Client Delivery", ("client", "deliverable", "revision", "handoff", "onboarding")),
        ("Marketing", ("campaign", "social", "newsletter", "email", "landing page", "ad", "seo", "launch")),
        ("Creative", ("design", "brand", "script", "storyboard", "copy", "illustration", "video", "creative")),
        ("Operations", ("sop", "ops", "bookkeeping", "admin", "process", "finance", "payroll", "qa")),
    )
    for workstream, terms in rules:
        if any(term in haystack for term in terms):
            return workstream
    return "General"


def _compute_focus_score(
    *,
    status: str,
    urgency: str,
    priority: str,
    effort: str,
    workstream: str,
    owner: str | None,
    project: str | None,
) -> int:
    if status == "Done":
        return 0
    urgency_weight = {
        "Overdue": 120,
        "Due today": 96,
        "Due soon": 72,
        "Upcoming": 48,
        "No due date": 30,
    }.get(urgency, 30)
    priority_weight = {
        "Critical": 55,
        "High": 36,
        "Medium": 22,
        "Low": 8,
        "Normal": 16,
    }.get(priority, 16)
    effort_weight = {"Quick": 8, "Standard": 3, "Deep": -2}.get(effort, 3)
    stream_weight = {
        "Sales": 14,
        "Client Delivery": 11,
        "Marketing": 9,
        "Creative": 8,
        "Operations": 6,
        "General": 4,
    }.get(workstream, 4)
    owner_bonus = 4 if owner else 0
    project_bonus = 4 if project else 0
    return urgency_weight + priority_weight + effort_weight + stream_weight + owner_bonus + project_bonus


def _extract_task(text: str) -> tuple[str | None, str, str]:
    raw = text.rstrip()
    if not raw:
        return None, "Open", "none"

    box = _RE_CHECKBOX.match(raw)
    if box:
        status = "Done" if box.group("mark").lower() == "x" else "Open"
        return _clean_task_text(box.group("task")), status, "checkbox"

    done_prefix = _RE_PREFIX_DONE.match(raw)
    if done_prefix:
        return _clean_task_text(done_prefix.group("task")), "Done", "prefix"

    open_prefix = _RE_PREFIX_OPEN.match(raw)
    if open_prefix:
        return _clean_task_text(open_prefix.group("task")), "Open", "prefix"

    field = _RE_TASK_FIELD.search(raw)
    if field:
        return _clean_task_text(field.group("task")), "Open", "task_field"

    if (
        "owner:" in raw.lower()
        or "due:" in raw.lower()
        or "priority:" in raw.lower()
        or "effort:" in raw.lower()
        or "project:" in raw.lower()
        or "client:" in raw.lower()
        or _RE_OWNER_TAG.search(raw)
    ) and len(raw) <= 220:
        return _clean_task_text(raw), "Open", "structured"

    return None, "Open", "none"


def _urgency_for_due(due_date: dt.date | None, status: str) -> str:
    if status == "Done":
        return "Completed"
    if not due_date:
        return "No due date"
    today = dt.date.today()
    days = (due_date - today).days
    if days < 0:
        return "Overdue"
    if days == 0:
        return "Due today"
    if days <= 3:
        return "Due soon"
    return "Upcoming"


def _strip_meta_tokens(line_text: str) -> str:
    line = (line_text or "").strip()
    if "|" in line:
        parts = [segment.strip() for segment in line.split("|")]
        kept: list[str] = []
        for idx, segment in enumerate(parts):
            if not segment:
                continue
            if idx > 0 and segment.lower().startswith(_META_TOKEN_PREFIXES):
                continue
            kept.append(segment)
        line = " | ".join(kept)

    changed = True
    while changed:
        changed = False
        due_match = _RE_TRAILING_DUE_TOKEN.search(line)
        if due_match:
            line = line[: due_match.start()].rstrip()
            changed = True
        owner_match = _RE_TRAILING_OWNER_TOKEN.search(line)
        if owner_match:
            line = line[: owner_match.start()].rstrip()
            changed = True
        priority_match = _RE_TRAILING_PRIORITY_TOKEN.search(line)
        if priority_match:
            line = line[: priority_match.start()].rstrip()
            changed = True
        effort_match = _RE_TRAILING_EFFORT_TOKEN.search(line)
        if effort_match:
            line = line[: effort_match.start()].rstrip()
            changed = True
        project_match = _RE_TRAILING_PROJECT_TOKEN.search(line)
        if project_match:
            line = line[: project_match.start()].rstrip()
            changed = True

    line = re.sub(r"\s+\|\s*$", "", line)
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip()


def _clean_task_text(value: str) -> str:
    cleaned = _strip_meta_tokens(value)
    return cleaned if cleaned else (value or "").strip()


def _rewrite_action_line(
    line_text: str,
    owner=_UNSET,
    due_date=_UNSET,
    priority=_UNSET,
    effort=_UNSET,
    project=_UNSET,
) -> str | None:
    if line_text is None:
        return None
    original = line_text.rstrip("\n")
    task, _, _ = _extract_task(original)
    if not task:
        return None

    current_owner = _extract_owner(original)
    current_due = _parse_due_date(original)
    current_priority = _extract_priority(original)
    current_effort = _extract_effort(original)
    current_project = _extract_project(original)

    next_owner = current_owner if owner is _UNSET else (str(owner).strip() or None)
    next_due = current_due if due_date is _UNSET else due_date
    next_priority = current_priority if priority is _UNSET else _normalize_priority(priority)
    next_effort = current_effort if effort is _UNSET else _normalize_effort(effort)
    next_project = current_project if project is _UNSET else (str(project).strip() or None)

    base = _strip_meta_tokens(original)
    if next_owner:
        base += f" | owner: {next_owner}"
    if next_due:
        base += f" | due: {next_due.isoformat()}"
    if next_priority and next_priority != "Normal":
        base += f" | priority: {next_priority}"
    if next_effort and next_effort != "Standard":
        base += f" | effort: {next_effort}"
    if next_project:
        base += f" | project: {next_project}"
    return base


def parse_action_items(text: str) -> list[ActionItem]:
    if not text:
        return []

    items: list[ActionItem] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        task, status, kind = _extract_task(raw_line)
        if not task:
            continue
        owner = _extract_owner(raw_line)
        due_date = _parse_due_date(raw_line)
        priority = _extract_priority(raw_line)
        effort = _extract_effort(raw_line)
        project = _extract_project(raw_line)
        urgency = _urgency_for_due(due_date, status)
        workstream = _infer_workstream(task, project)
        focus_score = _compute_focus_score(
            status=status,
            urgency=urgency,
            priority=priority,
            effort=effort,
            workstream=workstream,
            owner=owner,
            project=project,
        )
        items.append(
            ActionItem(
                task=task,
                line_number=line_no,
                line_index=f"{line_no}.0",
                line_text=raw_line,
                status=status,
                owner=owner,
                due_date=due_date,
                urgency=urgency,
                kind=kind,
                priority=priority,
                effort=effort,
                project=project,
                workstream=workstream,
                focus_score=focus_score,
            )
        )

    items.sort(
        key=lambda item: (
            item.status == "Done",
            -item.focus_score,
            item.due_date is None,
            item.due_date or dt.date.max,
            item.line_number,
        )
    )
    return items


def toggle_action_line_done(line_text: str) -> str | None:
    if line_text is None:
        return None
    original = line_text.rstrip("\n")

    box = _RE_CHECKBOX.match(original)
    if box:
        mark = "x" if box.group("mark").lower() == " " else " "
        task = box.group("task")
        return re.sub(_RE_CHECKBOX, f"- [{mark}] {task}", original)

    done_prefix = _RE_PREFIX_DONE.match(original)
    if done_prefix:
        return f"TODO: {done_prefix.group('task').strip()}"

    open_prefix = _RE_PREFIX_OPEN.match(original)
    if open_prefix:
        return f"DONE: {open_prefix.group('task').strip()}"

    # For structured but non-checkbox lines, wrap with DONE:/TODO: on toggle.
    if (
        "owner:" in original.lower()
        or "due:" in original.lower()
        or "priority:" in original.lower()
        or "effort:" in original.lower()
        or "project:" in original.lower()
        or "client:" in original.lower()
        or _RE_OWNER_TAG.search(original)
    ):
        if original.strip().lower().startswith("done:"):
            return f"TODO: {original.split(':', 1)[1].strip()}"
        return f"DONE: {original.strip()}"

    return None


def set_action_owner(line_text: str, owner: str | None) -> str | None:
    return _rewrite_action_line(line_text, owner=owner)


def set_action_due_date(line_text: str, due_date: dt.date | None) -> str | None:
    return _rewrite_action_line(line_text, due_date=due_date)


def set_action_priority(line_text: str, priority: str | None) -> str | None:
    return _rewrite_action_line(line_text, priority=priority)


def set_action_effort(line_text: str, effort: str | None) -> str | None:
    return _rewrite_action_line(line_text, effort=effort)


def set_action_project(line_text: str, project: str | None) -> str | None:
    return _rewrite_action_line(line_text, project=project)


def build_action_line(
    task: str,
    owner: str | None = None,
    due_date: dt.date | None = None,
    *,
    priority: str | None = None,
    effort: str | None = None,
    project: str | None = None,
) -> str:
    clean_task = (task or "").strip()
    if not clean_task:
        raise ValueError("Task is required.")
    line = f"- [ ] {clean_task}"
    clean_owner = (owner or "").strip()
    if clean_owner:
        line += f" | owner: {clean_owner}"
    if due_date:
        line += f" | due: {due_date.isoformat()}"
    clean_priority = _normalize_priority(priority)
    if clean_priority != "Normal":
        line += f" | priority: {clean_priority}"
    clean_effort = _normalize_effort(effort)
    if clean_effort != "Standard":
        line += f" | effort: {clean_effort}"
    clean_project = (project or "").strip()
    if clean_project:
        line += f" | project: {clean_project}"
    return line


def _format_item_meta(item: ActionItem) -> str:
    project_text = item.project or "-"
    owner_text = item.owner or "-"
    return (
        f"Owner: {owner_text} | Due: {item.due_display} | "
        f"Priority: {item.priority} | Stream: {item.workstream} | "
        f"Effort: {item.effort} | Project: {project_text} | "
        f"Score: {item.focus_score} | line {item.line_number}"
    )


def build_action_focus_plan(items: list[ActionItem], *, max_items: int = 8) -> str:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## Business-Creative Focus Plan ({stamp})", ""]
    open_items = [item for item in items if item.status == "Open"]
    if not open_items:
        lines.append("- No open action items detected.")
        lines.append("")
        return "\n".join(lines)

    ranked = sorted(
        open_items,
        key=lambda item: (
            -item.focus_score,
            item.due_date or dt.date.max,
            item.line_number,
        ),
    )
    top_items = ranked[: max(1, int(max_items))]
    revenue_moves = [i for i in top_items if i.workstream in {"Sales", "Client Delivery"}]
    creative_moves = [i for i in top_items if i.workstream in {"Creative", "Marketing"}]
    quick_wins = [i for i in top_items if i.effort == "Quick"]

    lines.append("### Priority Queue")
    for item in top_items:
        lines.append(f"- [ ] {item.task}")
        lines.append(f"  - {_format_item_meta(item)}")
    lines.append("")

    if revenue_moves:
        lines.append("### Revenue & Client Moves")
        for item in revenue_moves[:4]:
            lines.append(f"- [ ] {item.task} ({item.urgency}, score {item.focus_score})")
        lines.append("")

    if creative_moves:
        lines.append("### Creative Pipeline")
        for item in creative_moves[:4]:
            lines.append(f"- [ ] {item.task} ({item.workstream}, score {item.focus_score})")
        lines.append("")

    if quick_wins:
        lines.append("### Quick Wins")
        for item in quick_wins[:5]:
            lines.append(f"- [ ] {item.task} ({item.due_display})")
        lines.append("")

    return "\n".join(lines)


def build_action_dashboard(items: list[ActionItem]) -> str:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"## Action Hub Snapshot ({stamp})", ""]
    if not items:
        lines.append("- No action items detected.")
        lines.append("")
        return "\n".join(lines)

    total = len(items)
    open_items = [i for i in items if i.status == "Open"]
    done_items = [i for i in items if i.status == "Done"]
    overdue = [i for i in open_items if i.urgency == "Overdue"]
    due_today = [i for i in open_items if i.urgency == "Due today"]
    due_soon = [i for i in open_items if i.urgency == "Due soon"]

    lines.append(
        f"Summary: {total} total | {len(open_items)} open | {len(done_items)} done | "
        f"{len(overdue)} overdue | {len(due_today)} due today | {len(due_soon)} due soon"
    )
    lines.append("")
    lines.append("### Workstreams")
    workstream_counts: dict[str, int] = {}
    for item in open_items:
        workstream_counts[item.workstream] = workstream_counts.get(item.workstream, 0) + 1
    for stream_name in sorted(workstream_counts.keys()):
        lines.append(f"- {stream_name}: {workstream_counts[stream_name]}")
    lines.append("")

    lines.append(build_action_focus_plan(items, max_items=6))

    owners: dict[str, list[ActionItem]] = {}
    for item in open_items:
        owner_key = item.owner or "Unassigned"
        owners.setdefault(owner_key, []).append(item)

    if owners:
        lines.append("### Open Items By Owner")
        for owner in sorted(owners.keys(), key=lambda x: x.lower()):
            lines.append(f"- {owner}:")
            for item in owners[owner]:
                lines.append(
                    f"  - {item.task} ({_format_item_meta(item)})"
                )
        lines.append("")

    lines.append("### Full Item List")
    for item in items:
        mark = "[x]" if item.status == "Done" else "[ ]"
        lines.append(f"- {mark} {item.task}  ({_format_item_meta(item)} | {item.urgency})")
    lines.append("")
    return "\n".join(lines)


def _logo_data_url(logo_path: str | None) -> str | None:
    path = (logo_path or "").strip()
    if not path:
        return None
    file_path = Path(path).expanduser()
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        raw = file_path.read_bytes()
    except OSError:
        return None
    if not raw:
        return None
    content_type, _ = mimetypes.guess_type(str(file_path))
    if not content_type:
        content_type = "image/png"
    import base64

    payload = base64.b64encode(raw).decode("ascii")
    return f"data:{content_type};base64,{payload}"


def build_action_report_html(
    items: list[ActionItem],
    *,
    title: str = "To-Do Action Report",
    logo_path: str | None = None,
    generated_by: str = "PyWord Pro",
) -> str:
    stamp = dt.datetime.now().strftime("%B %d, %Y %I:%M %p")
    total = len(items)
    open_items = [i for i in items if i.status == "Open"]
    done_items = [i for i in items if i.status == "Done"]
    overdue = [i for i in open_items if i.urgency == "Overdue"]
    due_today = [i for i in open_items if i.urgency == "Due today"]
    due_soon = [i for i in open_items if i.urgency == "Due soon"]
    quick_wins = [i for i in open_items if i.effort == "Quick"]
    deep_work = [i for i in open_items if i.effort == "Deep"]
    ranked_open = sorted(
        open_items,
        key=lambda item: (
            -item.focus_score,
            item.due_date or dt.date.max,
            item.line_number,
        ),
    )
    top_priority_items = ranked_open[:8]

    logo_data = _logo_data_url(logo_path)
    logo_html = ""
    if logo_data:
        logo_html = f'<img class="logo" src="{logo_data}" alt="Logo" />'

    grouped_by_owner: dict[str, list[ActionItem]] = {}
    for item in open_items:
        key = item.owner or "Unassigned"
        grouped_by_owner.setdefault(key, []).append(item)

    owner_sections: list[str] = []
    for owner in sorted(grouped_by_owner.keys(), key=lambda value: value.lower()):
        rows = []
        for item in grouped_by_owner[owner]:
            rows.append(
                "<tr>"
                f"<td>{html.escape(item.task)}</td>"
                f"<td>{html.escape(item.due_display)}</td>"
                f"<td>{html.escape(item.priority)}</td>"
                f"<td>{html.escape(item.workstream)}</td>"
                f"<td>{html.escape(item.urgency)}</td>"
                f"<td>{item.focus_score}</td>"
                f"<td>{item.line_number}</td>"
                "</tr>"
            )
        owner_sections.append(
            "<section class='owner-block'>"
            f"<h3>{html.escape(owner)}</h3>"
            "<table>"
            "<thead><tr><th>Task</th><th>Due</th><th>Priority</th><th>Workstream</th><th>Urgency</th><th>Score</th><th>Line</th></tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table></section>"
        )

    focus_rows = []
    for item in top_priority_items:
        focus_rows.append(
            "<tr>"
            f"<td>{html.escape(item.task)}</td>"
            f"<td>{html.escape(item.workstream)}</td>"
            f"<td>{html.escape(item.priority)}</td>"
            f"<td>{html.escape(item.effort)}</td>"
            f"<td>{html.escape(item.owner or '-')}</td>"
            f"<td>{html.escape(item.due_display)}</td>"
            f"<td>{item.focus_score}</td>"
            "</tr>"
        )
    if not focus_rows:
        focus_rows.append("<tr><td colspan='7'>No open action items.</td></tr>")

    all_rows = []
    for item in items:
        state = "Done" if item.status == "Done" else "Open"
        state_class = "badge-done" if item.status == "Done" else "badge-open"
        all_rows.append(
            "<tr>"
            f"<td><span class='badge {state_class}'>{state}</span></td>"
            f"<td>{html.escape(item.task)}</td>"
            f"<td>{html.escape(item.project or '-')}</td>"
            f"<td>{html.escape(item.owner or '-')}</td>"
            f"<td>{html.escape(item.due_display)}</td>"
            f"<td>{html.escape(item.priority)}</td>"
            f"<td>{html.escape(item.effort)}</td>"
            f"<td>{html.escape(item.workstream)}</td>"
            f"<td>{html.escape(item.urgency)}</td>"
            f"<td>{item.focus_score}</td>"
            f"<td>{item.line_number}</td>"
            "</tr>"
        )

    if not all_rows:
        all_rows.append("<tr><td colspan='11'>No action items detected.</td></tr>")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #eef3fb;
      --card: #ffffff;
      --ink: #1d2a3a;
      --muted: #5a6b83;
      --border: #d0dbeb;
      --accent: #1f5eff;
      --accent-soft: #e8efff;
      --danger: #c23838;
      --ok: #177a47;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      color: var(--ink);
      background: linear-gradient(180deg, #f4f7fd 0%, #edf2fb 100%);
      padding: 28px;
    }}
    .page {{
      max-width: 1040px;
      margin: 0 auto;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 18px 42px rgba(24, 46, 86, 0.14);
      overflow: hidden;
    }}
    .header {{
      padding: 22px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(90deg, #f8fbff 0%, #edf3ff 100%);
      gap: 18px;
    }}
    .header h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0.2px;
    }}
    .header p {{
      margin: 6px 0 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .logo {{
      max-height: 62px;
      max-width: 220px;
      object-fit: contain;
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px 10px;
    }}
    .grid {{
      display: grid;
      gap: 12px;
      padding: 18px 20px 8px;
      grid-template-columns: repeat(4, minmax(120px, 1fr));
    }}
    .metric {{
      border: 1px solid var(--border);
      background: #f9fbff;
      border-radius: 10px;
      padding: 10px 12px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.9);
    }}
    .metric .value {{
      font-weight: 800;
      font-size: 22px;
      color: #10233f;
    }}
    .metric .label {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 2px;
      text-transform: uppercase;
      letter-spacing: .4px;
    }}
    .section {{
      padding: 8px 20px 20px;
    }}
    .section h2 {{
      margin: 10px 0 10px;
      font-size: 17px;
      color: #143972;
    }}
    .owner-block {{
      margin: 0 0 14px;
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow: hidden;
      background: #fff;
    }}
    .owner-block h3 {{
      margin: 0;
      padding: 10px 12px;
      font-size: 14px;
      background: var(--accent-soft);
      border-bottom: 1px solid var(--border);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th, td {{
      border-bottom: 1px solid #e4ecf7;
      text-align: left;
      padding: 9px 10px;
      font-size: 13px;
      vertical-align: top;
    }}
    th {{
      background: #f6f9ff;
      color: #2d4564;
      font-weight: 700;
    }}
    .badge {{
      display: inline-block;
      min-width: 46px;
      text-align: center;
      border-radius: 999px;
      padding: 2px 9px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: .2px;
    }}
    .badge-open {{ background: #eaf1ff; color: #174299; }}
    .badge-done {{ background: #e6f6ee; color: var(--ok); }}
    .footer {{
      padding: 12px 20px 20px;
      color: var(--muted);
      font-size: 12px;
    }}
    @media (max-width: 860px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
      .header {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="header">
      <div>
        <h1>{html.escape(title)}</h1>
        <p>Generated {html.escape(stamp)} · Source: {html.escape(generated_by)}</p>
      </div>
      {logo_html}
    </header>

    <section class="grid">
      <div class="metric"><div class="value">{total}</div><div class="label">Total</div></div>
      <div class="metric"><div class="value">{len(open_items)}</div><div class="label">Open</div></div>
      <div class="metric"><div class="value">{len(done_items)}</div><div class="label">Done</div></div>
      <div class="metric"><div class="value">{len(overdue)}</div><div class="label">Overdue</div></div>
      <div class="metric"><div class="value">{len(due_today)}</div><div class="label">Due Today</div></div>
      <div class="metric"><div class="value">{len(due_soon)}</div><div class="label">Due Soon</div></div>
      <div class="metric"><div class="value">{len(quick_wins)}</div><div class="label">Quick Wins</div></div>
      <div class="metric"><div class="value">{len(deep_work)}</div><div class="label">Deep Work</div></div>
    </section>

    <section class="section">
      <h2>Business-Creative Focus Queue</h2>
      <table>
        <thead>
          <tr>
            <th>Task</th><th>Workstream</th><th>Priority</th><th>Effort</th><th>Owner</th><th>Due</th><th>Score</th>
          </tr>
        </thead>
        <tbody>
          {"".join(focus_rows)}
        </tbody>
      </table>
    </section>

    <section class="section">
      <h2>Open Tasks By Owner</h2>
      {"".join(owner_sections) if owner_sections else "<p>No open items to group.</p>"}
    </section>

    <section class="section">
      <h2>Complete To-Do Register</h2>
      <table>
        <thead>
          <tr>
            <th>Status</th><th>Task</th><th>Project</th><th>Owner</th><th>Due</th><th>Priority</th><th>Effort</th><th>Workstream</th><th>Urgency</th><th>Score</th><th>Line</th>
          </tr>
        </thead>
        <tbody>
          {"".join(all_rows)}
        </tbody>
      </table>
    </section>

    <div class="footer">Exported by {html.escape(generated_by)} · Action Hub fancy report</div>
  </div>
</body>
</html>
"""
