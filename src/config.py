import copy
import json
import os
import re
import sys
import tempfile

from src.ui.theme.tokens import get_theme_tokens

APP_NAME = "PyWord Pro"
VERSION = "5.0 Modular"
CONFIG_FILE = "pyword_config.json"


def _default_app_data_dir():
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        return os.path.join(base, APP_NAME)

    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)

    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "pyword_pro")


def _resolve_persistent_file_path(file_name: str):
    raw_name = str(file_name or "").strip() or "pyword_config.json"
    if os.path.isabs(raw_name):
        return raw_name

    legacy_path = os.path.abspath(raw_name)
    if os.path.exists(legacy_path):
        return legacy_path
    return os.path.join(_default_app_data_dir(), raw_name)

THEME = {
    "light": get_theme_tokens("light"),
    "dark": get_theme_tokens("dark"),
}


class ConfigManager:
    def __init__(self):
        self.config_path = _resolve_persistent_file_path(CONFIG_FILE)
        self.defaults = {
            "ui_schema_version": 2,
            "security_schema_version": 1,
            "release_schema_version": 1,
            "theme": "light",
            "recents": [],
            "geometry": "1600x1000",
            "zoom": 100,
            "sidebar_visible": False,
            "focus_mode": False,
            "paper_color": None,
            "brand_logo_path": "",
            "ui": {
                "left_panel_width": 264,
                "right_panel_width": 320,
                "right_panel_visible": False,
                "show_console": False,
                "show_rulers": True,
                "density": "comfortable",
                "main_sash_left": 0,
                "main_sash_right": 0,
                "command_bar_collapsed": False,
                "command_bar_height": 132,
                "dictionary_custom_entries": {},
                "custom_font_files": [],
                "custom_font_families": [],
                "toolbar_visible_tools": [],
                "icon_bar_visible": True,
                "icon_bar_visible_commands": [],
            },
            "security": {
                "strict_mode": True,
                "max_input_mb": 16,
                "max_docx_entries": 2500,
                "max_docx_uncompressed_mb": 48,
                "max_docx_compression_ratio": 200,
                "block_encrypted_office": True,
                "require_oletools": False,
                "require_msoffcrypto": False,
                "require_yara_rules": False,
                "require_clamav": False,
                "quarantine_enabled": True,
                "quarantine_dir": "pyword_quarantine",
                "audit_log_path": "pyword_security_audit.log",
            },
            "recovery": {
                "enabled": True,
                "interval_seconds": 30,
                "max_snapshots": 20,
                "recovery_dir": "pyword_recovery",
            },
        }
        self.data = self.load()

    _GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)([+-]\d+[+-]\d+)?$")

    def _safe_int(self, value, fallback, minimum=None, maximum=None):
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = int(fallback)
        if minimum is not None:
            numeric = max(int(minimum), numeric)
        if maximum is not None:
            numeric = min(int(maximum), numeric)
        return int(numeric)

    def _safe_bool(self, value, fallback=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return bool(fallback)
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
        if text == "":
            return bool(fallback)
        return bool(fallback)

    def _safe_geometry(self, value, fallback, minimum_width=640, minimum_height=420):
        fallback_text = str(fallback or "")
        text = str(value or "").strip()
        match = self._GEOMETRY_RE.match(text)
        if not match:
            return fallback_text
        width = self._safe_int(match.group(1), minimum_width, minimum=minimum_width)
        height = self._safe_int(match.group(2), minimum_height, minimum=minimum_height)
        offset = match.group(3) or ""
        return f"{width}x{height}{offset}"

    def _safe_left_panel_width(self, value):
        return self._safe_int(value, self.defaults["ui"]["left_panel_width"], minimum=220)

    def _safe_right_panel_width(self, value):
        return self._safe_int(value, self.defaults["ui"]["right_panel_width"], minimum=280)

    def _safe_sash_position(self, value):
        return self._safe_int(value, 0, minimum=0, maximum=20000)

    def _safe_command_bar_height(self, value):
        return self._safe_int(value, self.defaults["ui"]["command_bar_height"], minimum=84, maximum=420)

    def _safe_recovery_interval(self, value):
        return self._safe_int(value, self.defaults["recovery"]["interval_seconds"], minimum=5, maximum=900)

    def _safe_recovery_snapshot_cap(self, value):
        return self._safe_int(value, self.defaults["recovery"]["max_snapshots"], minimum=1, maximum=500)

    def _safe_path(self, value, fallback):
        text = str(value or "").strip()
        return text or str(fallback)

    def _safe_recents(self, value):
        if not isinstance(value, list):
            return []
        cleaned = []
        seen = set()
        for item in value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)
            if len(cleaned) >= 8:
                break
        return cleaned

    def _safe_string_list(self, value, limit=200):
        if not isinstance(value, list):
            return []
        cleaned = []
        seen = set()
        for item in value:
            text = str(item or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
            if len(cleaned) >= int(limit):
                break
        return cleaned

    def _normalize(self, loaded: dict | None):
        merged = copy.deepcopy(self.defaults)
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                if key in {"ui", "security", "recovery"}:
                    continue
                merged[key] = value

            loaded_ui = loaded.get("ui")
            if isinstance(loaded_ui, dict):
                merged["ui"].update(loaded_ui)

            loaded_security = loaded.get("security")
            if isinstance(loaded_security, dict):
                merged["security"].update(loaded_security)

            loaded_recovery = loaded.get("recovery")
            if isinstance(loaded_recovery, dict):
                merged["recovery"].update(loaded_recovery)

            # Backward compatibility for earlier flat keys.
            if "show_console" in loaded:
                merged["ui"]["show_console"] = self._safe_bool(loaded.get("show_console"), fallback=False)
            if "left_panel_width" in loaded:
                merged["ui"]["left_panel_width"] = self._safe_left_panel_width(loaded.get("left_panel_width"))
            if "right_panel_width" in loaded:
                merged["ui"]["right_panel_width"] = self._safe_right_panel_width(loaded.get("right_panel_width"))
            if "right_panel_visible" in loaded:
                merged["ui"]["right_panel_visible"] = self._safe_bool(loaded.get("right_panel_visible"), fallback=False)
            if "show_rulers" in loaded:
                merged["ui"]["show_rulers"] = self._safe_bool(loaded.get("show_rulers"), fallback=True)
            if "density" in loaded and loaded.get("density") in {"comfortable", "compact"}:
                merged["ui"]["density"] = loaded.get("density")
            if "command_bar_height" in loaded:
                merged["ui"]["command_bar_height"] = self._safe_command_bar_height(loaded.get("command_bar_height"))
            if "dictionary_custom_entries" in loaded and isinstance(loaded.get("dictionary_custom_entries"), dict):
                merged["ui"]["dictionary_custom_entries"] = loaded.get("dictionary_custom_entries")
            if "custom_font_files" in loaded:
                merged["ui"]["custom_font_files"] = self._safe_string_list(loaded.get("custom_font_files"))
            if "custom_font_families" in loaded:
                merged["ui"]["custom_font_families"] = self._safe_string_list(loaded.get("custom_font_families"))
            if "toolbar_visible_tools" in loaded:
                merged["ui"]["toolbar_visible_tools"] = self._safe_string_list(loaded.get("toolbar_visible_tools"), limit=64)
            if "icon_bar_visible" in loaded:
                merged["ui"]["icon_bar_visible"] = self._safe_bool(loaded.get("icon_bar_visible"), fallback=True)
            if "icon_bar_visible_commands" in loaded:
                merged["ui"]["icon_bar_visible_commands"] = self._safe_string_list(loaded.get("icon_bar_visible_commands"), limit=256)

        merged["geometry"] = self._safe_geometry(
            merged.get("geometry"),
            self.defaults["geometry"],
            minimum_width=1024,
            minimum_height=680,
        )
        merged["recents"] = self._safe_recents(merged.get("recents"))
        merged["zoom"] = self._safe_int(merged.get("zoom"), self.defaults["zoom"], minimum=50, maximum=200)
        merged["sidebar_visible"] = self._safe_bool(
            merged.get("sidebar_visible"),
            fallback=self.defaults["sidebar_visible"],
        )
        merged["focus_mode"] = self._safe_bool(
            merged.get("focus_mode"),
            fallback=self.defaults["focus_mode"],
        )
        merged["theme"] = merged.get("theme") if merged.get("theme") in THEME else self.defaults["theme"]
        merged["paper_color"] = merged.get("paper_color")
        merged["brand_logo_path"] = self._safe_path(merged.get("brand_logo_path"), "")

        merged["ui"]["left_panel_width"] = self._safe_left_panel_width(merged["ui"].get("left_panel_width"))
        merged["ui"]["right_panel_width"] = self._safe_right_panel_width(merged["ui"].get("right_panel_width"))
        merged["ui"]["main_sash_left"] = self._safe_sash_position(merged["ui"].get("main_sash_left"))
        merged["ui"]["main_sash_right"] = self._safe_sash_position(merged["ui"].get("main_sash_right"))
        merged["ui"]["show_console"] = self._safe_bool(merged["ui"].get("show_console"), fallback=False)
        merged["ui"]["right_panel_visible"] = self._safe_bool(merged["ui"].get("right_panel_visible"), fallback=False)
        merged["ui"]["show_rulers"] = self._safe_bool(merged["ui"].get("show_rulers"), fallback=True)
        merged["ui"]["command_bar_height"] = self._safe_command_bar_height(merged["ui"].get("command_bar_height"))
        merged["ui"]["command_bar_collapsed"] = self._safe_bool(
            merged["ui"].get("command_bar_collapsed"),
            fallback=self.defaults["ui"]["command_bar_collapsed"],
        )
        if merged["ui"].get("density") not in {"comfortable", "compact"}:
            merged["ui"]["density"] = self.defaults["ui"]["density"]
        if not isinstance(merged["ui"].get("dictionary_custom_entries"), dict):
            merged["ui"]["dictionary_custom_entries"] = {}
        merged["ui"]["custom_font_files"] = self._safe_string_list(merged["ui"].get("custom_font_files"))
        merged["ui"]["custom_font_families"] = self._safe_string_list(merged["ui"].get("custom_font_families"))
        merged["ui"]["toolbar_visible_tools"] = self._safe_string_list(merged["ui"].get("toolbar_visible_tools"), limit=64)
        merged["ui"]["icon_bar_visible"] = self._safe_bool(
            merged["ui"].get("icon_bar_visible"),
            fallback=self.defaults["ui"]["icon_bar_visible"],
        )
        merged["ui"]["icon_bar_visible_commands"] = self._safe_string_list(
            merged["ui"].get("icon_bar_visible_commands"),
            limit=256,
        )

        merged["security"]["strict_mode"] = self._safe_bool(merged["security"].get("strict_mode"), fallback=True)
        merged["security"]["max_input_mb"] = self._safe_int(merged["security"].get("max_input_mb"), 16, minimum=1, maximum=512)
        merged["security"]["max_docx_entries"] = self._safe_int(merged["security"].get("max_docx_entries"), 2500, minimum=100, maximum=50000)
        merged["security"]["max_docx_uncompressed_mb"] = self._safe_int(
            merged["security"].get("max_docx_uncompressed_mb"),
            48,
            minimum=8,
            maximum=2048,
        )
        merged["security"]["max_docx_compression_ratio"] = self._safe_int(
            merged["security"].get("max_docx_compression_ratio"),
            200,
            minimum=10,
            maximum=2000,
        )
        for key in ("block_encrypted_office", "require_oletools", "require_msoffcrypto", "require_yara_rules", "require_clamav", "quarantine_enabled"):
            fallback = bool(self.defaults["security"].get(key))
            merged["security"][key] = self._safe_bool(merged["security"].get(key), fallback=fallback)
        merged["security"]["quarantine_dir"] = self._safe_path(
            merged["security"].get("quarantine_dir"),
            self.defaults["security"]["quarantine_dir"],
        )
        merged["security"]["audit_log_path"] = self._safe_path(
            merged["security"].get("audit_log_path"),
            self.defaults["security"]["audit_log_path"],
        )
        if merged["security"].get("yara_rules_path") is not None:
            merged["security"]["yara_rules_path"] = self._safe_path(merged["security"].get("yara_rules_path"), "")

        merged["recovery"]["enabled"] = self._safe_bool(
            merged["recovery"].get("enabled"),
            fallback=self.defaults["recovery"]["enabled"],
        )
        merged["recovery"]["interval_seconds"] = self._safe_recovery_interval(merged["recovery"].get("interval_seconds"))
        merged["recovery"]["max_snapshots"] = self._safe_recovery_snapshot_cap(merged["recovery"].get("max_snapshots"))
        merged["recovery"]["recovery_dir"] = self._safe_path(
            merged["recovery"].get("recovery_dir"),
            self.defaults["recovery"]["recovery_dir"],
        )

        merged["ui_schema_version"] = 2
        merged["security_schema_version"] = 1
        merged["release_schema_version"] = 1
        return merged

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    return self._normalize(loaded if isinstance(loaded, dict) else None)
            except (OSError, json.JSONDecodeError):
                return copy.deepcopy(self.defaults)
        return copy.deepcopy(self.defaults)

    def save(self):
        self.data = self._normalize(self.data if isinstance(self.data, dict) else None)
        directory = os.path.dirname(os.path.abspath(self.config_path)) or "."
        try:
            os.makedirs(directory, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix=".pyword_cfg_", suffix=".json", dir=directory)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.config_path)
        except OSError:
            return

    def add_recent(self, path):
        normalized = str(path or "").strip()
        if not normalized:
            return
        recents = self.data.get("recents")
        if not isinstance(recents, list):
            recents = []
        recents = [str(item).strip() for item in recents if str(item or "").strip()]
        if normalized in recents:
            recents.remove(normalized)
        recents.insert(0, normalized)
        self.data["recents"] = recents[:8]
        self.save()
