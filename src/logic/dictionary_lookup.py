import difflib
import re
from typing import Iterable

try:
    from spellchecker import SpellChecker

    HAS_SPELL = True
except Exception:
    HAS_SPELL = False


class DictionaryService:
    """Local dictionary lookup with optional spell-based suggestions."""

    BUILTIN_ENTRIES = {
        "invoice": {
            "part_of_speech": "noun",
            "definition": "A document that itemizes goods or services and requests payment.",
            "synonyms": ["bill", "statement"],
            "example": "Send the final invoice after project sign-off.",
        },
        "estimate": {
            "part_of_speech": "noun",
            "definition": "An approximate calculation of expected cost, effort, or duration.",
            "synonyms": ["projection", "approximation"],
            "example": "The estimate includes design and revisions.",
        },
        "quote": {
            "part_of_speech": "noun",
            "definition": "A stated price offer for a specific scope of work.",
            "synonyms": ["bid", "price offer"],
            "example": "The quote is valid for 30 days.",
        },
        "proposal": {
            "part_of_speech": "noun",
            "definition": "A structured plan or offer describing approach, timeline, and pricing.",
            "synonyms": ["pitch", "plan"],
            "example": "The proposal highlights deliverables and milestones.",
        },
        "contract": {
            "part_of_speech": "noun",
            "definition": "A legally binding agreement between parties.",
            "synonyms": ["agreement", "terms"],
            "example": "Both parties signed the contract.",
        },
        "brief": {
            "part_of_speech": "noun",
            "definition": "A concise document summarizing objectives, audience, and constraints.",
            "synonyms": ["summary", "outline"],
            "example": "The creative brief defines the campaign goals.",
        },
        "memo": {
            "part_of_speech": "noun",
            "definition": "A short internal communication document.",
            "synonyms": ["note", "memorandum"],
            "example": "Publish a memo to share the policy update.",
        },
        "sop": {
            "part_of_speech": "noun",
            "definition": "Standard Operating Procedure; a repeatable step-by-step process document.",
            "synonyms": ["procedure", "playbook"],
            "example": "Follow the SOP before deployment.",
        },
        "checklist": {
            "part_of_speech": "noun",
            "definition": "A list of required tasks or checks to complete.",
            "synonyms": ["task list", "tick list"],
            "example": "Use the checklist during QA.",
        },
        "stakeholder": {
            "part_of_speech": "noun",
            "definition": "A person or group with interest in a project outcome.",
            "synonyms": ["sponsor", "interested party"],
            "example": "Share weekly updates with key stakeholders.",
        },
        "scope": {
            "part_of_speech": "noun",
            "definition": "The defined boundaries and deliverables of work.",
            "synonyms": ["coverage", "extent"],
            "example": "Out-of-scope work requires approval.",
        },
        "deliverable": {
            "part_of_speech": "noun",
            "definition": "A tangible output that must be provided.",
            "synonyms": ["output", "artifact"],
            "example": "The final deliverable is a launch-ready document.",
        },
        "milestone": {
            "part_of_speech": "noun",
            "definition": "A significant checkpoint in a timeline.",
            "synonyms": ["checkpoint", "target date"],
            "example": "The draft review is the next milestone.",
        },
        "action": {
            "part_of_speech": "noun",
            "definition": "A task that requires execution.",
            "synonyms": ["task", "step"],
            "example": "Capture each action with owner and due date.",
        },
        "priority": {
            "part_of_speech": "noun",
            "definition": "The relative importance or urgency of work.",
            "synonyms": ["importance", "precedence"],
            "example": "Mark blocking items as high priority.",
        },
        "dependency": {
            "part_of_speech": "noun",
            "definition": "A task or condition that another task relies on.",
            "synonyms": ["prerequisite", "blocker"],
            "example": "Design approval is a dependency for copy finalization.",
        },
        "risk": {
            "part_of_speech": "noun",
            "definition": "A potential event that can negatively affect outcomes.",
            "synonyms": ["exposure", "hazard"],
            "example": "Late feedback is a delivery risk.",
        },
        "cadence": {
            "part_of_speech": "noun",
            "definition": "The regular frequency of recurring work or communication.",
            "synonyms": ["rhythm", "frequency"],
            "example": "Set a weekly reporting cadence.",
        },
        "typography": {
            "part_of_speech": "noun",
            "definition": "The design and arrangement of text for readability and style.",
            "synonyms": ["type design", "text styling"],
            "example": "Typography choices shape visual hierarchy.",
        },
        "kerning": {
            "part_of_speech": "noun",
            "definition": "Adjustment of spacing between individual letter pairs.",
            "synonyms": ["letter spacing adjustment"],
            "example": "Tighten kerning for the headline pair.",
        },
        "leading": {
            "part_of_speech": "noun",
            "definition": "Vertical spacing between lines of text.",
            "synonyms": ["line spacing"],
            "example": "Increase leading for long-form readability.",
        },
        "baseline": {
            "part_of_speech": "noun",
            "definition": "The imaginary line where most text characters sit.",
            "synonyms": ["text line"],
            "example": "Align captions to a shared baseline.",
        },
        "vector": {
            "part_of_speech": "noun",
            "definition": "Resolution-independent graphics represented by paths.",
            "synonyms": ["path graphic"],
            "example": "Export logo marks as vector files.",
        },
        "raster": {
            "part_of_speech": "noun",
            "definition": "Pixel-based graphics with fixed resolution.",
            "synonyms": ["bitmap"],
            "example": "High-resolution raster images are best for photos.",
        },
        "hierarchy": {
            "part_of_speech": "noun",
            "definition": "Visual ordering that guides reading priority.",
            "synonyms": ["structure", "ordering"],
            "example": "Use size and weight to establish hierarchy.",
        },
        "outline": {
            "part_of_speech": "noun",
            "definition": "A structured summary of document sections.",
            "synonyms": ["structure", "framework"],
            "example": "Build an outline before drafting.",
        },
        "agenda": {
            "part_of_speech": "noun",
            "definition": "A planned list of discussion topics for a meeting.",
            "synonyms": ["schedule", "plan"],
            "example": "Share the agenda before the call.",
        },
        "owner": {
            "part_of_speech": "noun",
            "definition": "The person accountable for completing a task.",
            "synonyms": ["assignee", "responsible party"],
            "example": "Every action item should have an owner.",
        },
        "revision": {
            "part_of_speech": "noun",
            "definition": "A modified version after review or edits.",
            "synonyms": ["edit", "update"],
            "example": "Client comments were addressed in revision two.",
        },
        "template": {
            "part_of_speech": "noun",
            "definition": "A reusable document starter with predefined structure.",
            "synonyms": ["starter", "pattern"],
            "example": "Save the document as a template for reuse.",
        },
    }
    _WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{0,63}")
    _POS_ALLOWED = {"noun", "verb", "adjective", "adverb", "phrase"}

    def __init__(self, custom_entries: dict | None = None):
        self._custom_entries: dict[str, dict] = {}
        self._spell = SpellChecker() if HAS_SPELL else None
        self.load_custom_entries(custom_entries or {})

    @classmethod
    def normalize_word(cls, raw: str) -> str:
        text = str(raw or "").strip().lower()
        if not text:
            return ""
        match = cls._WORD_RE.search(text)
        if not match:
            return ""
        value = match.group(0).strip("'-")
        if not value or len(value) > 64:
            return ""
        return value

    def load_custom_entries(self, raw_entries: dict) -> None:
        self._custom_entries = {}
        if not isinstance(raw_entries, dict):
            return
        for key, payload in raw_entries.items():
            word = self.normalize_word(key)
            if not word or word in self.BUILTIN_ENTRIES:
                continue
            entry = self._sanitize_entry_payload(word, payload, source="custom")
            if entry is not None:
                self._custom_entries[word] = entry

    def export_custom_entries(self) -> dict[str, dict]:
        return {word: dict(payload) for word, payload in sorted(self._custom_entries.items())}

    def add_custom_entry(
        self,
        word: str,
        definition: str,
        *,
        part_of_speech: str = "noun",
        synonyms: str | Iterable[str] | None = None,
        example: str = "",
    ) -> bool:
        key = self.normalize_word(word)
        if not key:
            return False
        payload = {
            "definition": str(definition or "").strip(),
            "part_of_speech": str(part_of_speech or "noun").strip().lower(),
            "synonyms": synonyms,
            "example": str(example or "").strip(),
        }
        entry = self._sanitize_entry_payload(key, payload, source="custom")
        if entry is None:
            return False
        self._custom_entries[key] = entry
        return True

    def lookup(self, word: str) -> dict | None:
        key = self.normalize_word(word)
        if not key:
            return None

        hit = self._lookup_exact(key)
        if hit:
            return hit

        for variant in self._variants(key):
            hit = self._lookup_exact(variant)
            if hit:
                return hit
        return None

    def suggest(self, word: str, limit: int = 8) -> list[str]:
        try:
            cap = max(1, min(20, int(limit)))
        except (TypeError, ValueError):
            cap = 8

        key = self.normalize_word(word)
        lexicon = sorted(set(self.BUILTIN_ENTRIES.keys()) | set(self._custom_entries.keys()))
        if not key:
            return lexicon[:cap]

        ranked: list[str] = []
        seen = set()

        def _add(candidate: str):
            c = self.normalize_word(candidate)
            if not c or c == key or c in seen:
                return
            seen.add(c)
            ranked.append(c)

        if self._spell is not None:
            try:
                for candidate in list(self._spell.candidates(key) or []):
                    if candidate in self.BUILTIN_ENTRIES or candidate in self._custom_entries:
                        _add(candidate)
            except Exception:
                pass

        for candidate in difflib.get_close_matches(key, lexicon, n=max(cap * 2, 10), cutoff=0.68):
            _add(candidate)

        return ranked[:cap]

    def _lookup_exact(self, key: str) -> dict | None:
        payload = self._custom_entries.get(key)
        if payload:
            return dict(payload)
        built_in = self.BUILTIN_ENTRIES.get(key)
        if not built_in:
            return None
        return self._sanitize_entry_payload(key, built_in, source="built-in")

    def _sanitize_entry_payload(self, word: str, payload, *, source: str) -> dict | None:
        if isinstance(payload, str):
            value = {"definition": payload}
        elif isinstance(payload, dict):
            value = dict(payload)
        else:
            return None

        definition = str(value.get("definition", "") or "").strip()
        if not definition:
            return None
        part = str(value.get("part_of_speech", "noun") or "noun").strip().lower()
        if part not in self._POS_ALLOWED:
            part = "noun"
        synonyms = self._sanitize_synonyms(value.get("synonyms"))
        example = str(value.get("example", "") or "").strip()
        return {
            "word": word,
            "part_of_speech": part,
            "definition": definition,
            "synonyms": synonyms,
            "example": example,
            "source": source,
        }

    def _sanitize_synonyms(self, value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            raw_items = [chunk.strip() for chunk in value.split(",")]
        elif isinstance(value, (list, tuple, set)):
            raw_items = [str(item or "").strip() for item in value]
        else:
            return []

        cleaned = []
        seen = set()
        for item in raw_items:
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(item[:48])
        return cleaned[:8]

    def _variants(self, key: str) -> list[str]:
        variants = []
        if key.endswith("ies") and len(key) > 4:
            variants.append(key[:-3] + "y")
        if key.endswith("es") and len(key) > 3:
            variants.append(key[:-2])
        if key.endswith("s") and len(key) > 2:
            variants.append(key[:-1])
        if key.endswith("ing") and len(key) > 5:
            variants.append(key[:-3])
            variants.append(key[:-3] + "e")
        if key.endswith("ed") and len(key) > 4:
            variants.append(key[:-2])
            variants.append(key[:-1])
        if key.endswith("ly") and len(key) > 4:
            variants.append(key[:-2])

        unique = []
        seen = {key}
        for candidate in variants:
            normalized = self.normalize_word(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(normalized)
        return unique
