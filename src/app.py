import os
import re
import shutil
import subprocess
import sys
import json
import hashlib
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
from tkinter import font as tkfont

from src.config import APP_NAME, THEME, VERSION, ConfigManager
from src.logic.document_security import DocumentSecurityScanner
from src.logic.file_manager import FileManager
from src.logic.formatting import FormatManager
from src.logic.io_utils import atomic_write_json, normalize_output_path
from src.logic.processor import TextProcessor
from src.logic.recovery_manager import RecoveryManager
from src.logic.syntax import SyntaxHighlighter
from src.logic.template_ai import generate_template_draft
from src.logic.templates import (
    get_template_by_id,
    list_template_categories,
    list_template_style_presets,
    parse_markdown_template_content,
    save_custom_template,
)
from src.logic.tools import ToolManager
from src.ui.contracts import UiCommandId, UiCommandRequest, UiViewState
from src.ui.shell.command_palette import CommandPalette
from src.ui.shell.editor_shell import EditorShell


class App:
    _ALLOWED_FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
    _ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
    _SEARCH_MATCH_TAG = "search_match"
    _SEARCH_ACTIVE_MATCH_TAG = "search_match_active"

    def __init__(self, root):
        self.root = root
        self.config_mgr = ConfigManager()
        self.settings = self.config_mgr.data

        self.root.geometry(self.settings.get("geometry", "1400x900"))
        self.root.minsize(1280, 760)

        self.is_dirty = False
        self.current_theme = self.settings.get("theme", "light")
        self.paper_color = self.settings.get("paper_color")
        self.brand_logo_path = self._sanitize_logo_path(self.settings.get("brand_logo_path", ""))
        if self._ensure_logo_asset_managed():
            self.settings["brand_logo_path"] = self.brand_logo_path
            self.config_mgr.save()
        self.settings["brand_logo_path"] = self.brand_logo_path
        self.sidebar_visible = bool(self.settings.get("sidebar_visible", False))
        self.settings["sidebar_visible"] = self.sidebar_visible
        self.focus_mode = bool(self.settings.get("focus_mode", False))
        self._autosave_after_id = None
        self.command_palette = None

        security_settings = self.settings.get("security")
        if not isinstance(security_settings, dict):
            security_settings = {}
            self.settings["security"] = security_settings
        self.security_settings = security_settings

        recovery_settings = self.settings.get("recovery")
        if not isinstance(recovery_settings, dict):
            recovery_settings = {}
            self.settings["recovery"] = recovery_settings
        recovery_dir = str(recovery_settings.get("recovery_dir", "") or "").strip()
        if recovery_dir and not os.path.isabs(recovery_dir):
            recovery_settings["recovery_dir"] = os.path.join(self._app_data_dir(), recovery_dir)
        self.recovery_settings = recovery_settings
        self.recovery_mgr = RecoveryManager.from_settings(self.recovery_settings)

        ui_settings = self.settings.get("ui")
        if not isinstance(ui_settings, dict):
            ui_settings = {}
            self.settings["ui"] = ui_settings
        self.ui_settings = ui_settings
        self.custom_font_files = self._sanitize_string_list(self.ui_settings.get("custom_font_files"), limit=200)
        self.custom_font_families = self._sanitize_string_list(self.ui_settings.get("custom_font_families"), limit=200)
        if not self.custom_font_families:
            self.custom_font_families = self._derive_font_families_from_files(self.custom_font_files)
        self.ui_settings["custom_font_files"] = list(self.custom_font_files)
        self.ui_settings["custom_font_families"] = list(self.custom_font_families)
        self.show_console = bool(self.ui_settings.get("show_console", False))
        self.right_panel_visible = bool(self.ui_settings.get("right_panel_visible", False))
        self.show_rulers = bool(self.ui_settings.get("show_rulers", True))
        self.icon_bar_visible = bool(self.ui_settings.get("icon_bar_visible", True))
        self.ui_settings["icon_bar_visible"] = self.icon_bar_visible
        self.command_bar_collapsed = bool(self.ui_settings.get("command_bar_collapsed", False))
        self.ui_settings["command_bar_collapsed"] = self.command_bar_collapsed

        self.colors = THEME[self.current_theme]
        self.view_state = UiViewState(
            theme=self.current_theme,
            zoom=int(self.settings.get("zoom", 100)),
            dirty=False,
            sidebar_visible=self.sidebar_visible,
            focus_mode=self.focus_mode,
            show_console=self.show_console,
        )
        self.shell = EditorShell(self.root, self, self.colors, self.view_state)
        self.shell.pack(fill=tk.BOTH, expand=True)
        self.shell.set_right_panel_visible(self.right_panel_visible)
        self.shell.set_rulers_visible(self.show_rulers)
        self.shell.set_command_bar_collapsed(self.command_bar_collapsed)
        self._refresh_font_picker_values()

        self.editor = self.shell.get_editor()
        self._init_document_search_state()

        # Logic modules
        self.file_mgr = FileManager(
            self.editor,
            self.root,
            security_scanner=self._build_security_scanner(),
        )
        self._security_warning_shown = False
        self.security_runtime_issues = self.file_mgr.security_scanner.runtime_issues(refresh=True)
        self.formatter = FormatManager(self.editor, self.root)
        self.tools = ToolManager(self.editor, self.root)
        self.tools.set_default_logo_path(self.brand_logo_path)
        self.tools.set_logo_callbacks(self.set_default_logo, self.clear_default_logo)
        custom_dictionary_entries = self.ui_settings.get("dictionary_custom_entries")
        if not isinstance(custom_dictionary_entries, dict):
            custom_dictionary_entries = {}
            self.ui_settings["dictionary_custom_entries"] = {}
        self.tools.set_custom_dictionary_entries(custom_dictionary_entries)
        self.tools.set_dictionary_persist_callback(self._persist_custom_dictionary_entries)
        self.processor = TextProcessor(self.editor)
        self._refresh_processor_dictionary_words()
        self.syntax = SyntaxHighlighter(self.editor, self.colors)

        if self.paper_color:
            try:
                self.editor.config(bg=self.paper_color)
            except Exception:
                pass

        self.shell.bind_commands(self.execute_ui_command)
        self._configure_toolbar_preferences()
        self._build_menubar()

        self._bind_shortcuts()
        self._build_editor_context_menu()
        self.update_zoom(0, absolute=self.settings.get("zoom", 100))

        self.refresh_navigation()
        self.syntax.highlight()
        self.shell.set_recent_files(self.settings.get("recents", []))
        self.log("Application started")
        self._update_window_title()
        self._sync_view_state()
        self._maybe_restore_recovery_snapshot()
        self._schedule_autosave()
        self._bring_to_front()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # -----------------------------
    # Command Dispatch
    # -----------------------------

    def execute_ui_command(self, request: UiCommandRequest) -> bool:
        payload = request.payload or {}
        cid = request.command_id

        if cid == UiCommandId.OPEN:
            return self.open_file()
        if cid == UiCommandId.OPEN_RECENT:
            path = payload.get("path")
            if path == "__latest_recent__":
                recents = self.settings.get("recents", []) if isinstance(self.settings, dict) else []
                if isinstance(recents, list) and recents:
                    path = recents[0]
                else:
                    return self.open_file()
            return self.open_recent(path)
        if cid == UiCommandId.NEW_FROM_TEMPLATE:
            return self.new_from_template()
        if cid == UiCommandId.SAVE_AS_TEMPLATE:
            return self.save_current_as_template()
        if cid == UiCommandId.SAVE:
            return self.save_file()
        if cid == UiCommandId.CUT:
            return self._execute_and_refresh(self._cut_selection, "Cut selection", mark_dirty=True)
        if cid == UiCommandId.COPY:
            return self._execute_and_refresh(self._copy_selection, "Copied selection", refresh=False)
        if cid == UiCommandId.PASTE:
            return self._execute_and_refresh(self._paste_selection, "Pasted content", mark_dirty=True)
        if cid == UiCommandId.PASTE_PLAIN:
            return self._execute_and_refresh(self._paste_plain_text, "Pasted plain text", mark_dirty=True)
        if cid == UiCommandId.DELETE_SELECTION:
            return self._execute_and_refresh(self._delete_selection, "Deleted selection", mark_dirty=True)

        if cid == UiCommandId.UNDO:
            return self.safe_undo()
        if cid == UiCommandId.REDO:
            return self.safe_redo()
        if cid == UiCommandId.DUPLICATE_SELECTION:
            return self._execute_and_refresh(self.tools.duplicate_selection_or_line, "Duplicated line/selection", mark_dirty=True)
        if cid == UiCommandId.SORT_LINES_ASC:
            return self._execute_and_refresh(lambda: self.tools.sort_selected_lines(reverse=False), "Sorted lines A-Z", mark_dirty=True)
        if cid == UiCommandId.SORT_LINES_DESC:
            return self._execute_and_refresh(lambda: self.tools.sort_selected_lines(reverse=True), "Sorted lines Z-A", mark_dirty=True)
        if cid == UiCommandId.TRIM_TRAILING_SPACES:
            return self._execute_and_refresh(self.tools.clean_trailing_whitespace, "Removed trailing spaces", mark_dirty=True)
        if cid == UiCommandId.CHANGE_CASE_UPPER:
            return self._execute_and_refresh(lambda: self.tools.convert_case("upper"), "Applied uppercase", mark_dirty=True)
        if cid == UiCommandId.CHANGE_CASE_LOWER:
            return self._execute_and_refresh(lambda: self.tools.convert_case("lower"), "Applied lowercase", mark_dirty=True)
        if cid == UiCommandId.CHANGE_CASE_TITLE:
            return self._execute_and_refresh(lambda: self.tools.convert_case("title"), "Applied title case", mark_dirty=True)
        if cid == UiCommandId.CHANGE_CASE_SENTENCE:
            return self._execute_and_refresh(lambda: self.tools.convert_case("sentence"), "Applied sentence case", mark_dirty=True)

        if cid == UiCommandId.BOLD:
            return self._execute_and_refresh(lambda: self.formatter.toggle_format("bold"), "Toggled bold", mark_dirty=True)
        if cid == UiCommandId.ITALIC:
            return self._execute_and_refresh(lambda: self.formatter.toggle_format("italic"), "Toggled italic", mark_dirty=True)
        if cid == UiCommandId.UNDERLINE:
            return self._execute_and_refresh(lambda: self.formatter.toggle_format("underline"), "Toggled underline", mark_dirty=True)
        if cid == UiCommandId.STRIKE:
            return self._execute_and_refresh(lambda: self.formatter.toggle_format("overstrike"), "Toggled strike", mark_dirty=True)

        if cid == UiCommandId.ALIGN_LEFT:
            return self._execute_and_refresh(lambda: self.formatter.set_alignment("left"), "Aligned left", mark_dirty=True)
        if cid == UiCommandId.ALIGN_CENTER:
            return self._execute_and_refresh(lambda: self.formatter.set_alignment("center"), "Aligned center", mark_dirty=True)
        if cid == UiCommandId.ALIGN_RIGHT:
            return self._execute_and_refresh(lambda: self.formatter.set_alignment("right"), "Aligned right", mark_dirty=True)

        if cid == UiCommandId.BULLET_LIST:
            return self._execute_and_refresh(self.formatter.toggle_list, "Toggled bullet list", mark_dirty=True)
        if cid == UiCommandId.NUMBERED_LIST:
            return self._execute_and_refresh(self.formatter.toggle_numbered_list, "Toggled numbered list", mark_dirty=True)

        if cid == UiCommandId.TEXT_COLOR:
            return self._execute_and_refresh(self.formatter.pick_text_color, "Applied text color", mark_dirty=True)
        if cid == UiCommandId.HIGHLIGHT:
            return self._execute_and_refresh(self.formatter.apply_highlight, "Applied highlight", mark_dirty=True)
        if cid == UiCommandId.CLEAR_FORMATTING:
            return self._execute_and_refresh(self.formatter.clear_formatting, "Cleared formatting", mark_dirty=True)

        if cid == UiCommandId.LINE_SPACING:
            value = payload.get("value", 1.0)
            return self._execute_and_refresh(lambda: self.formatter.set_line_spacing(value), "Updated line spacing", mark_dirty=True)

        if cid == UiCommandId.FONT_FAMILY:
            family = payload.get("value")
            if not family:
                return False
            return self._execute_and_refresh(lambda: self.formatter.apply_font_family(family), "Changed font family", mark_dirty=True)

        if cid == UiCommandId.FONT_SIZE:
            size = payload.get("value")
            if size is None:
                return False
            return self._execute_and_refresh(lambda: self.formatter.apply_font_size(size), "Changed font size", mark_dirty=True)
        if cid == UiCommandId.FONT_SIZE_INCREASE:
            return self._execute_and_refresh(lambda: self.formatter.adjust_font_size(1), "Increased font size", mark_dirty=True)
        if cid == UiCommandId.FONT_SIZE_DECREASE:
            return self._execute_and_refresh(lambda: self.formatter.adjust_font_size(-1), "Decreased font size", mark_dirty=True)
        if cid == UiCommandId.APPLY_TEXT_STYLE:
            style_name = str(payload.get("value", "Body") or "Body").strip() or "Body"
            return self._execute_and_refresh(
                lambda: self.formatter.apply_text_style(style_name),
                f"Applied text style: {style_name}",
                mark_dirty=True,
            )
        if cid == UiCommandId.UPLOAD_FONT:
            return self.upload_font()

        if cid == UiCommandId.ZOOM_IN:
            return bool(self.update_zoom(10))
        if cid == UiCommandId.ZOOM_OUT:
            return bool(self.update_zoom(-10))
        if cid == UiCommandId.ZOOM_SET:
            value = payload.get("value")
            if value is None:
                return False
            try:
                zoom_value = int(float(value))
            except (TypeError, ValueError):
                return False
            return bool(self.update_zoom(absolute=zoom_value))

        if cid == UiCommandId.INSERT_IMAGE:
            return self._execute_and_refresh(self.tools.insert_image, "Inserted image", mark_dirty=True)
        if cid == UiCommandId.INSERT_HORIZONTAL_LINE:
            return self._execute_and_refresh(self.tools.insert_horizontal_line, "Inserted horizontal line", mark_dirty=True)
        if cid == UiCommandId.INSERT_DATE_TIME:
            return self._execute_and_refresh(self.tools.insert_date_time, "Inserted date/time", mark_dirty=True)
        if cid == UiCommandId.INSERT_SYMBOL:
            return self._execute_and_refresh(self.tools.open_symbol_picker, "Opened symbol picker")
        if cid == UiCommandId.INSERT_TABLE:
            return self._execute_and_refresh(self.tools.insert_table_prompt, "Inserted table", mark_dirty=True)
        if cid == UiCommandId.INSERT_CHECKLIST:
            return self._execute_and_refresh(self.tools.insert_checklist_prompt, "Inserted checklist", mark_dirty=True)
        if cid == UiCommandId.INSERT_PAGE_BREAK:
            return self._execute_and_refresh(self.tools.insert_page_break, "Inserted page break marker", mark_dirty=True)
        if cid == UiCommandId.OPEN_MEMO_BUILDER:
            return self._execute_and_refresh(self.tools.open_memo_builder, "Opened memo builder", refresh=False)

        if cid == UiCommandId.FIND_REPLACE:
            return self._execute_and_refresh(self.tools.open_find_replace, "Opened find/replace")
        if cid == UiCommandId.DOCUMENT_SEARCH:
            return self.update_document_search(payload.get("query"), navigate=False)
        if cid == UiCommandId.DOCUMENT_SEARCH_NEXT:
            return self.update_document_search(payload.get("query"), navigate=True, direction=1)
        if cid == UiCommandId.DOCUMENT_SEARCH_PREV:
            return self.update_document_search(payload.get("query"), navigate=True, direction=-1)
        if cid == UiCommandId.DOCUMENT_SEARCH_CLEAR:
            return self.clear_document_search(clear_field=False)
        if cid == UiCommandId.ACTION_HUB:
            return self._execute_and_refresh(self.tools.open_action_hub, "Opened Action Hub", refresh=False)
        if cid == UiCommandId.EXPORT_TODO_REPORT:
            return self._execute_and_refresh(
                self.tools.export_fancy_todo_report,
                "Exported fancy to-do report",
                refresh=False,
            )
        if cid == UiCommandId.SHOW_STATS:
            return self.show_stats()
        if cid == UiCommandId.SELECT_ALL:
            return self._execute_and_refresh(self.tools.select_all, "Selected all text", refresh=False)
        if cid == UiCommandId.EXPORT_PDF:
            return self._execute_and_refresh(self.file_mgr.export_pdf, "Exported PDF", refresh=False)

        if cid == UiCommandId.SPELL_CHECK:
            return self.run_spell_check()
        if cid == UiCommandId.READ_ALOUD:
            return self.read_aloud()
        if cid == UiCommandId.DICTIONARY_LOOKUP:
            return self.open_dictionary_lookup()
        if cid == UiCommandId.WIKI_LOOKUP:
            return self.open_wiki_lookup()

        if cid == UiCommandId.PICK_PAPER_COLOR:
            return self.pick_paper_color()
        if cid == UiCommandId.TOGGLE_THEME:
            return self.toggle_theme()
        if cid == UiCommandId.TOGGLE_FOCUS:
            return self.toggle_focus_mode()
        if cid == UiCommandId.TOGGLE_SIDEBAR:
            return self.toggle_sidebar()
        if cid == UiCommandId.TOGGLE_CONSOLE:
            return self.toggle_console()
        if cid == UiCommandId.TOGGLE_RULERS:
            return self.toggle_rulers()
        if cid == UiCommandId.OPEN_COMMAND_PALETTE:
            return self.open_command_palette()
        if cid == UiCommandId.SET_DEFAULT_LOGO:
            return self.set_default_logo()
        if cid == UiCommandId.CLEAR_DEFAULT_LOGO:
            return self.clear_default_logo()

        if cid == UiCommandId.NAVIGATE_TO_INDEX:
            return self.navigate_to_index(payload.get("index"))

        return False

    def _build_menubar(self):
        try:
            windowing_system = self.root.tk.call("tk", "windowingsystem")
        except Exception:
            windowing_system = ""

        builders = []
        if self._prefer_core_native_menu(windowing_system):
            builders.append(self._populate_core_menubar)
        else:
            builders.append(self._populate_full_menubar)
        if windowing_system == "aqua" and self._populate_core_menubar not in builders:
            builders.append(self._populate_core_menubar)

        for build in builders:
            try:
                menubar = tk.Menu(self.root)
                build(menubar)
                self.root.config(menu=menubar)
                return
            except tk.TclError:
                continue

    def _prefer_core_native_menu(self, windowing_system: str) -> bool:
        # Keep native menu enabled on macOS by default, but use a smaller core
        # menu profile unless full menu is explicitly requested.
        if str(windowing_system or "").lower() != "aqua":
            return False
        return os.environ.get("PYWORD_FULL_NATIVE_MENU") != "1"

    def _populate_core_menubar(self, menubar: tk.Menu):
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="New From Template...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.NEW_FROM_TEMPLATE)))
        file_menu.add_command(label="Save Current As Template...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SAVE_AS_TEMPLATE)))
        file_menu.add_separator()
        file_menu.add_command(label="Open...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN)))
        file_menu.add_command(label="Save", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SAVE)))
        file_menu.add_command(label="Export PDF", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.EXPORT_PDF)))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Undo", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.UNDO)))
        edit_menu.add_command(label="Redo", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.REDO)))
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CUT)))
        edit_menu.add_command(label="Copy", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.COPY)))
        edit_menu.add_command(label="Paste", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.PASTE)))
        edit_menu.add_command(label="Find / Replace", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.FIND_REPLACE)))
        edit_menu.add_command(label="Select All", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SELECT_ALL)))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        review_menu = tk.Menu(menubar, tearoff=False)
        review_menu.add_command(label="Spell Check", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SPELL_CHECK)))
        review_menu.add_command(label="Action Hub", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ACTION_HUB)))
        review_menu.add_command(label="Export Fancy To-Do Report", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.EXPORT_TODO_REPORT)))
        menubar.add_cascade(label="Review", menu=review_menu)

        view_menu = tk.Menu(menubar, tearoff=False)
        view_menu.add_command(
            label="Command Palette",
            command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN_COMMAND_PALETTE)),
        )
        view_menu.add_separator()
        view_menu.add_command(label="Export Toolbar Layout...", command=self.export_toolbar_layout)
        view_menu.add_command(label="Import Toolbar Layout...", command=self.import_toolbar_layout)
        view_menu.add_separator()
        view_menu.add_command(label="Toggle Theme", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_THEME)))
        view_menu.add_command(label="Focus Mode", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_FOCUS)))
        view_menu.add_command(label="Toggle Sidebar", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_SIDEBAR)))
        view_menu.add_command(label="Toggle Rulers", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_RULERS)))
        menubar.add_cascade(label="View", menu=view_menu)

    def _populate_full_menubar(self, menubar: tk.Menu):
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="New From Template...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.NEW_FROM_TEMPLATE)))
        file_menu.add_command(label="Save Current As Template...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SAVE_AS_TEMPLATE)))
        file_menu.add_separator()
        file_menu.add_command(label="Open...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN)))
        file_menu.add_command(label="Save", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SAVE)))
        file_menu.add_command(label="Export PDF", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.EXPORT_PDF)))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Undo", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.UNDO)))
        edit_menu.add_command(label="Redo", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.REDO)))
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CUT)))
        edit_menu.add_command(label="Copy", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.COPY)))
        edit_menu.add_command(label="Paste", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.PASTE)))
        edit_menu.add_command(label="Paste Plain Text", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.PASTE_PLAIN)))
        edit_menu.add_command(label="Delete", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.DELETE_SELECTION)))
        edit_menu.add_separator()
        edit_menu.add_command(label="Find / Replace", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.FIND_REPLACE)))
        edit_menu.add_command(label="Select All", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SELECT_ALL)))
        edit_menu.add_separator()
        edit_menu.add_command(label="Duplicate Line/Selection", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.DUPLICATE_SELECTION)))
        edit_menu.add_command(label="Sort Lines A-Z", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SORT_LINES_ASC)))
        edit_menu.add_command(label="Sort Lines Z-A", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SORT_LINES_DESC)))
        edit_menu.add_command(label="Trim Trailing Spaces", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TRIM_TRAILING_SPACES)))
        edit_menu.add_separator()
        edit_menu.add_command(label="UPPERCASE", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CHANGE_CASE_UPPER)))
        edit_menu.add_command(label="lowercase", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CHANGE_CASE_LOWER)))
        edit_menu.add_command(label="Title Case", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CHANGE_CASE_TITLE)))
        edit_menu.add_command(label="Sentence case", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CHANGE_CASE_SENTENCE)))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        format_menu = tk.Menu(menubar, tearoff=False)
        format_menu.add_command(label="Bold", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.BOLD)))
        format_menu.add_command(label="Italic", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ITALIC)))
        format_menu.add_command(label="Underline", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.UNDERLINE)))
        format_menu.add_command(label="Strike", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.STRIKE)))
        format_menu.add_separator()
        format_menu.add_command(label="Increase Font Size", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.FONT_SIZE_INCREASE)))
        format_menu.add_command(label="Decrease Font Size", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.FONT_SIZE_DECREASE)))
        format_menu.add_separator()
        format_menu.add_command(label="Body", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Body"})))
        format_menu.add_command(label="Title", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Title"})))
        format_menu.add_command(label="Heading 1", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Heading 1"})))
        format_menu.add_command(label="Heading 2", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Heading 2"})))
        format_menu.add_command(label="Heading 3", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Heading 3"})))
        format_menu.add_command(label="Quote", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Quote"})))
        format_menu.add_command(label="Code", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Code"})))
        format_menu.add_command(label="Caption", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Caption"})))
        format_menu.add_separator()
        format_menu.add_command(label="Line Spacing 1.0", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.LINE_SPACING, {"value": 1.0})))
        format_menu.add_command(label="Line Spacing 1.5", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.LINE_SPACING, {"value": 1.5})))
        format_menu.add_command(label="Line Spacing 2.0", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.LINE_SPACING, {"value": 2.0})))
        format_menu.add_separator()
        format_menu.add_command(label="Text Color", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TEXT_COLOR)))
        format_menu.add_command(label="Highlight", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.HIGHLIGHT)))
        format_menu.add_command(label="Clear Formatting", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CLEAR_FORMATTING)))
        menubar.add_cascade(label="Format", menu=format_menu)

        insert_menu = tk.Menu(menubar, tearoff=False)
        insert_menu.add_command(label="Image", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_IMAGE)))
        insert_menu.add_command(label="Horizontal Line", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_HORIZONTAL_LINE)))
        insert_menu.add_command(label="Date and Time", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_DATE_TIME)))
        insert_menu.add_command(label="Symbols", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_SYMBOL)))
        insert_menu.add_separator()
        insert_menu.add_command(label="Table...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_TABLE)))
        insert_menu.add_command(label="Checklist...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_CHECKLIST)))
        insert_menu.add_command(label="Page Break", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_PAGE_BREAK)))
        insert_menu.add_command(label="Memo Builder...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN_MEMO_BUILDER)))
        menubar.add_cascade(label="Insert", menu=insert_menu)

        review_menu = tk.Menu(menubar, tearoff=False)
        review_menu.add_command(label="Spell Check", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SPELL_CHECK)))
        review_menu.add_command(label="Dictionary Lookup", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.DICTIONARY_LOOKUP)))
        review_menu.add_command(label="Wikipedia Lookup", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.WIKI_LOOKUP)))
        review_menu.add_command(label="Document Stats", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SHOW_STATS)))
        review_menu.add_command(label="Read Aloud", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.READ_ALOUD)))
        review_menu.add_command(label="Action Hub", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ACTION_HUB)))
        review_menu.add_command(label="Export Fancy To-Do Report", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.EXPORT_TODO_REPORT)))
        menubar.add_cascade(label="Review", menu=review_menu)

        view_menu = tk.Menu(menubar, tearoff=False)
        view_menu.add_command(
            label="Command Palette",
            command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN_COMMAND_PALETTE)),
        )
        view_menu.add_separator()
        view_menu.add_command(label="Export Toolbar Layout...", command=self.export_toolbar_layout)
        view_menu.add_command(label="Import Toolbar Layout...", command=self.import_toolbar_layout)
        view_menu.add_separator()
        view_menu.add_command(label="Toggle Theme", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_THEME)))
        view_menu.add_command(label="Focus Mode", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_FOCUS)))
        view_menu.add_command(label="Toggle Sidebar", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_SIDEBAR)))
        view_menu.add_command(label="Toggle Console", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_CONSOLE)))
        view_menu.add_command(label="Toggle Rulers", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.TOGGLE_RULERS)))
        view_menu.add_command(label="Upload Font...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.UPLOAD_FONT)))
        view_menu.add_separator()
        view_menu.add_command(label="Set Default Logo...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SET_DEFAULT_LOGO)))
        view_menu.add_command(label="Clear Default Logo", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CLEAR_DEFAULT_LOGO)))
        menubar.add_cascade(label="View", menu=view_menu)

    def _bring_to_front(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.root.after(450, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass

    def _palette_entry(self, label: str, command_id: str, group: str, shortcut: str = "", keywords=None, payload=None):
        return {
            "label": str(label),
            "command_id": str(command_id),
            "group": str(group),
            "shortcut": str(shortcut),
            "keywords": list(keywords or []),
            "payload": dict(payload or {}) if isinstance(payload, dict) else None,
        }

    def _command_palette_catalog(self):
        return [
            self._palette_entry("Open File", UiCommandId.OPEN, "File", "Ctrl+O"),
            self._palette_entry("Save Document", UiCommandId.SAVE, "File", "Ctrl+S"),
            self._palette_entry("Export PDF", UiCommandId.EXPORT_PDF, "File", "", keywords=["pdf", "export"]),
            self._palette_entry("New From Template", UiCommandId.NEW_FROM_TEMPLATE, "File", "Ctrl+Shift+N"),
            self._palette_entry("Save As Template", UiCommandId.SAVE_AS_TEMPLATE, "File", "Ctrl+Alt+T"),
            self._palette_entry("Undo", UiCommandId.UNDO, "Edit", "Ctrl+Z"),
            self._palette_entry("Redo", UiCommandId.REDO, "Edit", "Ctrl+Y"),
            self._palette_entry("Cut", UiCommandId.CUT, "Edit"),
            self._palette_entry("Copy", UiCommandId.COPY, "Edit"),
            self._palette_entry("Paste", UiCommandId.PASTE, "Edit"),
            self._palette_entry("Paste Plain Text", UiCommandId.PASTE_PLAIN, "Edit"),
            self._palette_entry("Find and Replace", UiCommandId.FIND_REPLACE, "Edit", "Ctrl+F", keywords=["search"]),
            self._palette_entry("Select All", UiCommandId.SELECT_ALL, "Edit"),
            self._palette_entry("Bold", UiCommandId.BOLD, "Format"),
            self._palette_entry("Italic", UiCommandId.ITALIC, "Format"),
            self._palette_entry("Underline", UiCommandId.UNDERLINE, "Format"),
            self._palette_entry("Strike", UiCommandId.STRIKE, "Format"),
            self._palette_entry("Align Left", UiCommandId.ALIGN_LEFT, "Format"),
            self._palette_entry("Align Center", UiCommandId.ALIGN_CENTER, "Format"),
            self._palette_entry("Align Right", UiCommandId.ALIGN_RIGHT, "Format"),
            self._palette_entry("Bulleted List", UiCommandId.BULLET_LIST, "Format", keywords=["list"]),
            self._palette_entry("Numbered List", UiCommandId.NUMBERED_LIST, "Format", keywords=["list"]),
            self._palette_entry("Clear Formatting", UiCommandId.CLEAR_FORMATTING, "Format"),
            self._palette_entry("Line Spacing 1.0", UiCommandId.LINE_SPACING, "Format", payload={"value": 1.0}),
            self._palette_entry("Line Spacing 1.5", UiCommandId.LINE_SPACING, "Format", payload={"value": 1.5}),
            self._palette_entry("Line Spacing 2.0", UiCommandId.LINE_SPACING, "Format", payload={"value": 2.0}),
            self._palette_entry("Apply Heading 1", UiCommandId.APPLY_TEXT_STYLE, "Format", payload={"value": "Heading 1"}),
            self._palette_entry("Apply Heading 2", UiCommandId.APPLY_TEXT_STYLE, "Format", payload={"value": "Heading 2"}),
            self._palette_entry("Apply Body Style", UiCommandId.APPLY_TEXT_STYLE, "Format", payload={"value": "Body"}),
            self._palette_entry("Insert Image", UiCommandId.INSERT_IMAGE, "Insert"),
            self._palette_entry("Insert Date and Time", UiCommandId.INSERT_DATE_TIME, "Insert"),
            self._palette_entry("Insert Horizontal Line", UiCommandId.INSERT_HORIZONTAL_LINE, "Insert"),
            self._palette_entry("Insert Symbol", UiCommandId.INSERT_SYMBOL, "Insert"),
            self._palette_entry("Insert Table", UiCommandId.INSERT_TABLE, "Insert"),
            self._palette_entry("Insert Checklist", UiCommandId.INSERT_CHECKLIST, "Insert"),
            self._palette_entry("Open Memo Builder", UiCommandId.OPEN_MEMO_BUILDER, "Tools", keywords=["memo"]),
            self._palette_entry("Open Action Hub", UiCommandId.ACTION_HUB, "Tools", "Ctrl+Shift+A", keywords=["tasks", "todo"]),
            self._palette_entry("Export Fancy To-Do Report", UiCommandId.EXPORT_TODO_REPORT, "Tools", keywords=["todo", "report"]),
            self._palette_entry("Dictionary Lookup", UiCommandId.DICTIONARY_LOOKUP, "Review", "Ctrl+Shift+D"),
            self._palette_entry("Wikipedia Lookup", UiCommandId.WIKI_LOOKUP, "Review", "Ctrl+Shift+W", keywords=["wiki"]),
            self._palette_entry("Read Aloud", UiCommandId.READ_ALOUD, "Review", "Ctrl+Shift+L", keywords=["tts"]),
            self._palette_entry("Spell Check", UiCommandId.SPELL_CHECK, "Review"),
            self._palette_entry("Document Stats", UiCommandId.SHOW_STATS, "Review"),
            self._palette_entry("Toggle Focus Mode", UiCommandId.TOGGLE_FOCUS, "View", "Ctrl+Shift+F"),
            self._palette_entry("Toggle Sidebar", UiCommandId.TOGGLE_SIDEBAR, "View"),
            self._palette_entry("Toggle Console", UiCommandId.TOGGLE_CONSOLE, "View", "Ctrl+Shift+C"),
            self._palette_entry("Toggle Rulers", UiCommandId.TOGGLE_RULERS, "View", "Ctrl+Shift+R"),
            self._palette_entry("Toggle Theme", UiCommandId.TOGGLE_THEME, "View"),
            self._palette_entry("Zoom In", UiCommandId.ZOOM_IN, "View"),
            self._palette_entry("Zoom Out", UiCommandId.ZOOM_OUT, "View"),
            self._palette_entry("Set Paper Color", UiCommandId.PICK_PAPER_COLOR, "View"),
            self._palette_entry("Upload Font", UiCommandId.UPLOAD_FONT, "View"),
            self._palette_entry("Set Default Logo", UiCommandId.SET_DEFAULT_LOGO, "View"),
            self._palette_entry("Clear Default Logo", UiCommandId.CLEAR_DEFAULT_LOGO, "View"),
        ]

    def open_command_palette(self):
        if self.command_palette is None:
            self.command_palette = CommandPalette(self.root, self.execute_ui_command)
        self.command_palette.open(self._command_palette_catalog(), self.colors)
        return True

    def _configure_toolbar_preferences(self):
        top_strip = getattr(self.shell, "top_strip", None)
        if top_strip is None:
            return

        if hasattr(top_strip, "bind_toolbar_layout_actions"):
            top_strip.bind_toolbar_layout_actions(
                on_tools_changed=self._on_toolbar_tools_changed,
                on_icon_tools_changed=self._on_icon_tools_changed,
                on_icon_bar_toggle=self._on_icon_bar_visibility_changed,
                on_command_bar_toggle=self._on_command_bar_visibility_changed,
                on_export=self.export_toolbar_layout,
                on_import=self.import_toolbar_layout,
                on_reset=lambda: self.log("Toolbar reset to default tools"),
            )

        changed = False

        stored_tools = self._sanitize_toolbar_tool_ids(self.ui_settings.get("toolbar_visible_tools"))
        if stored_tools:
            top_strip.set_visible_tools(stored_tools, notify=False)
        elif hasattr(top_strip, "default_tool_ids"):
            defaults = top_strip.default_tool_ids()
            if isinstance(defaults, list) and defaults:
                top_strip.set_visible_tools(defaults, notify=False)
                self.ui_settings["toolbar_visible_tools"] = list(defaults)
                changed = True

        raw_icon_settings = self.ui_settings.get("icon_bar_visible_commands")
        if isinstance(raw_icon_settings, list) and hasattr(top_strip, "set_visible_icons"):
            stored_icons = self._sanitize_icon_command_ids(raw_icon_settings)
            top_strip.set_visible_icons(stored_icons, notify=False)
            if stored_icons != raw_icon_settings:
                self.ui_settings["icon_bar_visible_commands"] = list(stored_icons)
                changed = True
        elif hasattr(top_strip, "default_icon_ids") and hasattr(top_strip, "set_visible_icons"):
            icon_defaults = top_strip.default_icon_ids()
            top_strip.set_visible_icons(icon_defaults, notify=False)
            self.ui_settings["icon_bar_visible_commands"] = list(icon_defaults)
            changed = True

        if hasattr(top_strip, "set_icon_bar_visible"):
            top_strip.set_icon_bar_visible(self.icon_bar_visible, notify=False)

        if hasattr(top_strip, "set_command_bar_visible"):
            top_strip.set_command_bar_visible(not self.command_bar_collapsed, notify=False)

        if changed:
            self.config_mgr.save()

    def _available_toolbar_tool_ids(self):
        top_strip = getattr(self.shell, "top_strip", None)
        if top_strip and hasattr(top_strip, "get_available_tool_ids"):
            values = top_strip.get_available_tool_ids()
            return [str(value).strip() for value in values if str(value or "").strip()]
        return []

    def _available_icon_command_ids(self):
        top_strip = getattr(self.shell, "top_strip", None)
        if top_strip and hasattr(top_strip, "get_available_icon_ids"):
            values = top_strip.get_available_icon_ids()
            return [str(value).strip() for value in values if str(value or "").strip()]
        return []

    def _sanitize_toolbar_tool_ids(self, values):
        if not isinstance(values, list):
            return []
        allowed = set(self._available_toolbar_tool_ids())
        cleaned = []
        seen = set()
        for item in values:
            tool_id = str(item or "").strip()
            if not tool_id or tool_id in seen:
                continue
            if allowed and tool_id not in allowed:
                continue
            seen.add(tool_id)
            cleaned.append(tool_id)
            if len(cleaned) >= 64:
                break
        return cleaned

    def _sanitize_icon_command_ids(self, values):
        if not isinstance(values, list):
            return []
        allowed = set(self._available_icon_command_ids())
        cleaned = []
        seen = set()
        for item in values:
            icon_id = str(item or "").strip()
            if not icon_id or icon_id in seen:
                continue
            if allowed and icon_id not in allowed:
                continue
            seen.add(icon_id)
            cleaned.append(icon_id)
            if len(cleaned) >= 256:
                break
        return cleaned

    def _coerce_bool(self, value, fallback=False):
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
        return bool(fallback)

    def _on_toolbar_tools_changed(self, tool_ids):
        cleaned = self._sanitize_toolbar_tool_ids(tool_ids)
        if not cleaned:
            top_strip = getattr(self.shell, "top_strip", None)
            if top_strip and hasattr(top_strip, "default_tool_ids"):
                cleaned = top_strip.default_tool_ids()
        if not cleaned:
            return False
        self.ui_settings["toolbar_visible_tools"] = list(cleaned)
        self.config_mgr.save()
        self.log(f"Toolbar updated ({len(cleaned)} tools shown)")
        return True

    def _on_icon_tools_changed(self, icon_ids):
        cleaned = self._sanitize_icon_command_ids(icon_ids)
        self.ui_settings["icon_bar_visible_commands"] = list(cleaned)
        self.config_mgr.save()
        self.log(f"Icon bar updated ({len(cleaned)} icons shown)")
        return True

    def _on_icon_bar_visibility_changed(self, visible):
        self.icon_bar_visible = bool(visible)
        self.ui_settings["icon_bar_visible"] = self.icon_bar_visible
        self.config_mgr.save()
        self.log("Icon bar shown" if self.icon_bar_visible else "Icon bar hidden")
        return True

    def _on_command_bar_visibility_changed(self, visible):
        should_show = bool(visible)
        self.command_bar_collapsed = not should_show
        self.ui_settings["command_bar_collapsed"] = self.command_bar_collapsed
        shell = getattr(self, "shell", None)
        if shell and hasattr(shell, "set_command_bar_collapsed"):
            shell.set_command_bar_collapsed(self.command_bar_collapsed)
        top_strip = getattr(shell, "top_strip", None)
        if top_strip and hasattr(top_strip, "set_command_bar_visible"):
            top_strip.set_command_bar_visible(should_show, notify=False)
        self.config_mgr.save()
        self.log("Command bar shown" if should_show else "Command bar hidden")
        return True

    def export_toolbar_layout(self):
        top_strip = getattr(self.shell, "top_strip", None)
        if top_strip is None or not hasattr(top_strip, "get_visible_tools"):
            return False
        path = filedialog.asksaveasfilename(
            title="Export Toolbar Layout",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            parent=self.root,
        )
        if not path:
            return False
        payload = {
            "schema_version": 2,
            "toolbar_visible_tools": top_strip.get_visible_tools(),
            "command_bar_visible": not self.command_bar_collapsed,
        }
        if hasattr(top_strip, "get_visible_icons"):
            payload["icon_bar_visible_commands"] = top_strip.get_visible_icons()
        if hasattr(top_strip, "is_icon_bar_visible"):
            payload["icon_bar_visible"] = bool(top_strip.is_icon_bar_visible())
        try:
            target_path = normalize_output_path(path, default_extension=".json")
            atomic_write_json(target_path, payload, default_extension=".json")
        except OSError as exc:
            messagebox.showerror("Toolbar Layout", f"Could not export layout:\n{exc}")
            return False
        self.log(f"Exported toolbar layout: {os.path.basename(target_path)}")
        return True

    def import_toolbar_layout(self):
        top_strip = getattr(self.shell, "top_strip", None)
        if top_strip is None or not hasattr(top_strip, "set_visible_tools"):
            return False
        path = filedialog.askopenfilename(
            title="Import Toolbar Layout",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            parent=self.root,
        )
        if not path:
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Toolbar Layout", f"Could not import layout:\n{exc}")
            return False

        if not isinstance(payload, dict):
            messagebox.showerror("Toolbar Layout", "Layout file is invalid.")
            return False
        cleaned = self._sanitize_toolbar_tool_ids(payload.get("toolbar_visible_tools"))
        if not cleaned:
            messagebox.showerror("Toolbar Layout", "No valid toolbar tools were found in the file.")
            return False
        top_strip.set_visible_tools(cleaned, notify=False)
        self.ui_settings["toolbar_visible_tools"] = list(cleaned)

        if "icon_bar_visible_commands" in payload and hasattr(top_strip, "set_visible_icons"):
            icons = self._sanitize_icon_command_ids(payload.get("icon_bar_visible_commands"))
            top_strip.set_visible_icons(icons, notify=False)
            self.ui_settings["icon_bar_visible_commands"] = list(icons)

        if "icon_bar_visible" in payload and hasattr(top_strip, "set_icon_bar_visible"):
            icon_bar_visible = self._coerce_bool(payload.get("icon_bar_visible"), fallback=True)
            self.icon_bar_visible = icon_bar_visible
            self.ui_settings["icon_bar_visible"] = icon_bar_visible
            top_strip.set_icon_bar_visible(icon_bar_visible, notify=False)

        if "command_bar_visible" in payload:
            command_bar_visible = self._coerce_bool(payload.get("command_bar_visible"), fallback=not self.command_bar_collapsed)
            self.command_bar_collapsed = not command_bar_visible
            self.ui_settings["command_bar_collapsed"] = self.command_bar_collapsed
            self.shell.set_command_bar_collapsed(self.command_bar_collapsed)
            if hasattr(top_strip, "set_command_bar_visible"):
                top_strip.set_command_bar_visible(command_bar_visible, notify=False)

        self.config_mgr.save()
        self.log(f"Imported toolbar layout: {os.path.basename(path)}")
        return True

    # -----------------------------
    # Document Search
    # -----------------------------

    def _init_document_search_state(self):
        self._search_query = ""
        self._search_matches = []
        self._search_active_index = -1
        self._configure_search_tags()

    def _configure_search_tags(self):
        is_dark = self.current_theme == "dark"
        match_bg = "#5C4B1E" if is_dark else "#FFF2A8"
        active_bg = "#B87700" if is_dark else "#FFD166"
        text_color = self.colors.get("text", "#152033")
        try:
            self.editor.tag_configure(self._SEARCH_MATCH_TAG, background=match_bg, foreground=text_color)
            self.editor.tag_configure(self._SEARCH_ACTIVE_MATCH_TAG, background=active_bg, foreground=text_color)
            self.editor.tag_raise(self._SEARCH_ACTIVE_MATCH_TAG)
        except Exception:
            pass

    def _get_top_strip_search_query(self):
        shell = getattr(self, "shell", None)
        top_strip = getattr(shell, "top_strip", None)
        if top_strip and hasattr(top_strip, "get_search_query"):
            return str(top_strip.get_search_query() or "")
        return ""

    def _set_top_strip_search_query(self, value: str):
        shell = getattr(self, "shell", None)
        top_strip = getattr(shell, "top_strip", None)
        if top_strip and hasattr(top_strip, "set_search_query"):
            top_strip.set_search_query(value)

    def clear_document_search(self, clear_field=False):
        self._search_query = ""
        self._search_matches = []
        self._search_active_index = -1
        try:
            self.editor.tag_remove(self._SEARCH_MATCH_TAG, "1.0", tk.END)
            self.editor.tag_remove(self._SEARCH_ACTIVE_MATCH_TAG, "1.0", tk.END)
        except Exception:
            pass
        if clear_field:
            self._set_top_strip_search_query("")
        return True

    def _collect_document_search_matches(self, query: str):
        matches = []
        try:
            self.editor.tag_remove(self._SEARCH_MATCH_TAG, "1.0", tk.END)
            self.editor.tag_remove(self._SEARCH_ACTIVE_MATCH_TAG, "1.0", tk.END)
        except Exception:
            pass
        if not query:
            return matches

        start = "1.0"
        query_len = len(query)
        while True:
            try:
                pos = self.editor.search(query, start, stopindex="end-1c", nocase=True)
            except Exception:
                break
            if not pos:
                break
            end = f"{pos}+{query_len}c"
            matches.append((pos, end))
            try:
                self.editor.tag_add(self._SEARCH_MATCH_TAG, pos, end)
            except Exception:
                pass
            start = end
            try:
                if self.editor.compare(start, ">=", "end-1c"):
                    break
            except Exception:
                continue
        return matches

    def _render_document_search_active_match(self, scroll=True):
        try:
            self.editor.tag_remove(self._SEARCH_ACTIVE_MATCH_TAG, "1.0", tk.END)
        except Exception:
            pass
        if not self._search_matches:
            return False
        if self._search_active_index < 0 or self._search_active_index >= len(self._search_matches):
            return False

        start, end = self._search_matches[self._search_active_index]
        try:
            self.editor.tag_add(self._SEARCH_ACTIVE_MATCH_TAG, start, end)
            self.editor.mark_set(tk.INSERT, end)
            if scroll:
                self.editor.see(start)
            return True
        except Exception:
            return False

    def update_document_search(self, query=None, *, navigate=False, direction=1, refresh=False):
        raw_query = self._get_top_strip_search_query() if query is None else str(query or "")
        clean_query = raw_query.strip()
        if not clean_query:
            return self.clear_document_search(clear_field=False)

        if refresh:
            self._search_matches = []
            self._search_active_index = -1

        query_changed = clean_query != self._search_query
        if query_changed or not self._search_matches:
            self._search_query = clean_query
            self._search_matches = self._collect_document_search_matches(clean_query)
            self._search_active_index = -1

        if not self._search_matches:
            if navigate:
                self.shell.set_status(f'No matches for "{clean_query}"')
            return False

        if navigate:
            step = 1 if direction >= 0 else -1
            if self._search_active_index < 0:
                self._search_active_index = 0 if step > 0 else len(self._search_matches) - 1
            else:
                self._search_active_index = (self._search_active_index + step) % len(self._search_matches)
        elif self._search_active_index < 0 or query_changed:
            self._search_active_index = 0

        self._render_document_search_active_match(scroll=navigate)
        position = self._search_active_index + 1
        total = len(self._search_matches)
        self.shell.set_status(f'Search: {position}/{total} for "{clean_query}"')
        return True

    # -----------------------------
    # View Controls
    # -----------------------------

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.colors = THEME[self.current_theme]
        self.settings["theme"] = self.current_theme
        self.config_mgr.save()
        self.apply_theme()
        self.log(f"Theme switched to {self.current_theme}")
        return True

    def pick_paper_color(self):
        _, hex_color = colorchooser.askcolor(title="Choose Paper Color")
        if not hex_color:
            return False

        self.paper_color = hex_color
        self.settings["paper_color"] = hex_color
        self.config_mgr.save()

        try:
            self.editor.config(bg=hex_color)
        except Exception:
            pass
        try:
            self.tools.refresh_template_tags()
        except Exception:
            pass
        self.log("Applied paper color")
        return True

    def upload_font(self):
        selections = filedialog.askopenfilenames(
            title="Upload Fonts",
            filetypes=[
                ("Font Files", ("*.ttf", "*.otf", "*.ttc")),
                ("All Files", "*.*"),
            ],
            parent=self.root,
        )
        if not selections:
            return False

        before = self._system_font_families()
        imported_paths = []
        failed_paths = []
        storage_dir = self._font_storage_dir()
        try:
            os.makedirs(storage_dir, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Upload Font", f"Could not prepare font storage folder:\n{exc}")
            return False

        for source in selections:
            src = str(source or "").strip()
            if not src or not os.path.isfile(src):
                failed_paths.append(src or "(missing path)")
                continue
            ext = os.path.splitext(src)[1].lower()
            if ext not in self._ALLOWED_FONT_EXTENSIONS:
                failed_paths.append(src)
                continue

            target = self._next_unique_path(os.path.join(storage_dir, os.path.basename(src)))
            try:
                shutil.copy2(src, target)
                imported_paths.append(target)
                self._install_font_for_user(target)
            except OSError:
                failed_paths.append(src)

        if not imported_paths:
            messagebox.showerror("Upload Font", "No font files were imported.")
            return False

        merged_paths = self._sanitize_string_list(self.custom_font_files + imported_paths, limit=200)
        self.custom_font_files = merged_paths
        self.custom_font_families = self._collect_custom_font_families(before_system_families=before)
        self.ui_settings["custom_font_files"] = list(self.custom_font_files)
        self.ui_settings["custom_font_families"] = list(self.custom_font_families)
        self.config_mgr.save()
        self._refresh_font_picker_values()

        success_count = len(imported_paths)
        fail_count = len(failed_paths)
        self.log(f"Imported {success_count} font file(s)")
        message = f"Imported {success_count} font file(s)."
        if fail_count:
            message += f"\nSkipped {fail_count} unsupported/invalid file(s)."
        message += "\nIf a font does not appear immediately, restart the app."
        messagebox.showinfo("Upload Font", message)
        return True

    def set_default_logo(self):
        path = filedialog.askopenfilename(
            title="Select Default Logo",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("All Files", "*.*"),
            ],
            parent=self.root,
        )
        if not path:
            return False
        selected = self._sanitize_logo_path(path)
        if not selected:
            messagebox.showerror("Logo", "Select a supported image file (png/jpg/jpeg/gif/bmp).")
            return False
        try:
            stored_path = self._persist_logo_asset(selected)
        except OSError as exc:
            messagebox.showerror("Logo", f"Could not save logo asset:\n{exc}")
            return False

        self.brand_logo_path = stored_path
        self.settings["brand_logo_path"] = stored_path
        self.config_mgr.save()
        self.tools.set_default_logo_path(stored_path)
        self.log(f"Default logo set: {os.path.basename(stored_path)}")
        return True

    def clear_default_logo(self):
        if not self.brand_logo_path:
            return False
        self.brand_logo_path = ""
        self.settings["brand_logo_path"] = ""
        self.config_mgr.save()
        self.tools.set_default_logo_path("")
        self.log("Default logo cleared")
        return True

    def _sanitize_string_list(self, values, limit=200):
        if not isinstance(values, list):
            return []
        cleaned = []
        seen = set()
        for item in values:
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

    def _font_storage_dir(self):
        return os.path.join(self._app_data_dir(), "user_fonts")

    def _logo_storage_dir(self):
        return os.path.join(self._app_data_dir(), "brand_assets")

    def _sanitize_logo_path(self, value):
        candidate = str(value or "").strip()
        if not candidate:
            return ""
        expanded = os.path.abspath(os.path.expanduser(candidate))
        ext = os.path.splitext(expanded)[1].lower()
        if ext not in self._ALLOWED_LOGO_EXTENSIONS:
            return ""
        if not os.path.isfile(expanded):
            return ""
        return expanded

    def _file_sha256(self, path: str):
        hasher = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _is_path_within_dir(self, file_path: str, dir_path: str):
        try:
            file_abs = os.path.abspath(file_path)
            dir_abs = os.path.abspath(dir_path)
            return os.path.commonpath([file_abs, dir_abs]) == dir_abs
        except Exception:
            return False

    def _persist_logo_asset(self, source_path: str):
        source = self._sanitize_logo_path(source_path)
        if not source:
            raise OSError("Unsupported or missing logo file.")

        storage_dir = self._logo_storage_dir()
        os.makedirs(storage_dir, exist_ok=True)

        stem = os.path.splitext(os.path.basename(source))[0]
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "logo"
        ext = os.path.splitext(source)[1].lower()
        digest = self._file_sha256(source)[:12]
        target = os.path.join(storage_dir, f"{safe_stem}_{digest}{ext}")

        if os.path.exists(target):
            return target

        shutil.copy2(source, target)
        return target

    def _ensure_logo_asset_managed(self):
        if not self.brand_logo_path:
            return False
        storage_dir = self._logo_storage_dir()
        if self._is_path_within_dir(self.brand_logo_path, storage_dir):
            return False
        try:
            managed_path = self._persist_logo_asset(self.brand_logo_path)
        except OSError:
            return False
        if managed_path != self.brand_logo_path:
            self.brand_logo_path = managed_path
            return True
        return False

    def _app_data_dir(self):
        if sys.platform == "darwin":
            base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
            return os.path.join(base, "PyWord Pro")

        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            return os.path.join(base, "PyWord Pro")

        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
        return os.path.join(base, "pyword_pro")

    def _next_unique_path(self, candidate_path: str):
        root, ext = os.path.splitext(candidate_path)
        index = 1
        path = candidate_path
        while os.path.exists(path):
            path = f"{root}_{index}{ext}"
            index += 1
        return path

    def _system_font_families(self):
        try:
            return {str(name).strip() for name in tkfont.families() if str(name).strip()}
        except Exception:
            return set()

    def _derive_font_families_from_files(self, paths):
        values = []
        seen = set()
        for path in paths if isinstance(paths, list) else []:
            family = self._guess_font_family_from_path(path)
            if not family:
                continue
            key = family.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(family)
        return values

    def _guess_font_family_from_path(self, path):
        raw_path = str(path or "").strip()
        if not raw_path:
            return ""
        try:
            from PIL import ImageFont

            family, _style = ImageFont.truetype(raw_path, size=14).getname()
            if family:
                return str(family).strip()
        except Exception:
            pass
        stem = os.path.splitext(os.path.basename(raw_path))[0]
        label = re.sub(r"[_\-]+", " ", stem).strip()
        return label

    def _collect_custom_font_families(self, before_system_families=None):
        families = self._sanitize_string_list(self.custom_font_families, limit=200)
        seen = {value.casefold() for value in families}

        current_system = self._system_font_families()
        if isinstance(before_system_families, set):
            discovered = sorted(current_system - before_system_families, key=str.casefold)
        else:
            discovered = []
        for name in discovered:
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            families.append(name)

        for name in self._derive_font_families_from_files(self.custom_font_files):
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            families.append(name)
        return families

    def _install_font_for_user(self, source_path: str):
        path = str(source_path or "").strip()
        if not path:
            return False
        install_dir = ""
        if sys.platform == "darwin":
            install_dir = os.path.join(os.path.expanduser("~"), "Library", "Fonts")
        elif sys.platform.startswith("win"):
            base = os.environ.get("LOCALAPPDATA", "")
            if base:
                install_dir = os.path.join(base, "Microsoft", "Windows", "Fonts")
        else:
            install_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "fonts")
        if not install_dir:
            return False

        try:
            os.makedirs(install_dir, exist_ok=True)
            target = os.path.join(install_dir, os.path.basename(path))
            if os.path.abspath(path) != os.path.abspath(target):
                shutil.copy2(path, target)
            if sys.platform.startswith("linux"):
                try:
                    subprocess.run(["fc-cache", "-f", install_dir], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            return True
        except OSError:
            return False

    def _refresh_font_picker_values(self):
        try:
            command_bar = getattr(self.shell, "command_bar", None)
            if command_bar and hasattr(command_bar, "set_custom_fonts"):
                command_bar.set_custom_fonts(self.custom_font_families)
            top_strip = getattr(self.shell, "top_strip", None)
            if top_strip and hasattr(top_strip, "set_custom_fonts"):
                top_strip.set_custom_fonts(self.custom_font_families)
        except Exception:
            pass

    def _build_security_scanner(self):
        return DocumentSecurityScanner.from_settings(self.security_settings)

    def _ensure_security_ready(self):
        issues = self.file_mgr.security_scanner.runtime_issues(refresh=True)
        self.security_runtime_issues = issues
        if not issues:
            return True

        text = "Security policy requirements are not met:\n- " + "\n- ".join(issues)
        strict_mode = bool(getattr(self.file_mgr.security_scanner, "strict_mode", False))
        if strict_mode:
            messagebox.showerror(
                "Security Policy",
                f"{text}\n\nInstall required security dependencies or relax policy in pyword_config.json.",
            )
            self.log("Blocked document operation due to unmet strict security policy requirements.")
            return False

        if not self._security_warning_shown:
            messagebox.showwarning(
                "Security Policy",
                f"{text}\n\nContinuing because strict mode is disabled.",
            )
            self._security_warning_shown = True
        return True

    def toggle_sidebar(self):
        if self.focus_mode:
            self.toggle_focus_mode()
        self.sidebar_visible = not self.sidebar_visible
        self.settings["sidebar_visible"] = self.sidebar_visible
        self.config_mgr.save()
        self._sync_view_state()
        return True

    def toggle_focus_mode(self):
        self.focus_mode = not self.focus_mode
        self.settings["focus_mode"] = self.focus_mode
        self.config_mgr.save()
        self._sync_view_state()
        self.log("Focus mode enabled" if self.focus_mode else "Focus mode disabled")
        return True

    def toggle_console(self):
        self.show_console = not self.show_console
        self.ui_settings["show_console"] = self.show_console
        self.config_mgr.save()
        self._sync_view_state()
        self.log("Console shown" if self.show_console else "Console hidden")
        return True

    def toggle_rulers(self):
        self.show_rulers = not self.show_rulers
        self.ui_settings["show_rulers"] = self.show_rulers
        self.config_mgr.save()
        self.shell.set_rulers_visible(self.show_rulers)
        self.log("Rulers shown" if self.show_rulers else "Rulers hidden")
        return True

    def apply_theme(self):
        self.shell.update_theme(self.colors)
        self.shell.set_rulers_visible(self.show_rulers)
        if self.command_palette is not None:
            try:
                self.command_palette.update_theme(self.colors)
            except Exception:
                pass
        try:
            self.syntax.update_theme(self.current_theme == "dark")
        except Exception:
            pass
        self._configure_search_tags()

        if self.paper_color:
            try:
                self.editor.config(bg=self.paper_color)
            except Exception:
                pass

        try:
            self.tools.refresh_template_tags()
        except Exception:
            pass

        self._sync_view_state()

    # -----------------------------
    # Document flow
    # -----------------------------

    def _remember_recent(self, path):
        if path:
            self.config_mgr.add_recent(path)
            self.shell.set_recent_files(self.settings.get("recents", []))

    def _update_window_title(self):
        current = self.file_mgr.current_file_path
        if current:
            filename = re.sub(r"\s+", " ", os.path.basename(current))
        else:
            filename = "Untitled"
        title_name = filename
        dirty_prefix = "* " if self.is_dirty else ""
        self.root.title(f"{dirty_prefix}{APP_NAME} {VERSION} - {title_name}")
        self.shell.set_document_title(title_name, self.is_dirty)

    def _set_dirty(self, value: bool):
        self.is_dirty = bool(value)
        self._update_window_title()
        self._sync_view_state()

    def _sync_view_state(self):
        self.view_state = UiViewState(
            theme=self.current_theme,
            zoom=int(self.settings.get("zoom", 100)),
            dirty=self.is_dirty,
            sidebar_visible=self.sidebar_visible,
            focus_mode=self.focus_mode,
            show_console=self.show_console,
        )
        self.shell.set_view_state(self.view_state)

    def _prompt_save_if_dirty(self):
        if not self.is_dirty:
            return True

        choice = messagebox.askyesnocancel("Unsaved Changes", "Save changes before continuing?")
        if choice is None:
            return False
        if choice:
            return bool(self.save_file())
        return True

    def on_close(self):
        if not self._prompt_save_if_dirty():
            return
        self._cancel_autosave()
        try:
            if hasattr(self, "shell") and hasattr(self.shell, "capture_layout_preferences"):
                layout = self.shell.capture_layout_preferences()
                if isinstance(layout, dict):
                    self.ui_settings.update(layout)
            self.settings["geometry"] = self.root.geometry()
            self.config_mgr.save()
        except Exception:
            pass
        try:
            if hasattr(self, "recovery_mgr") and self.recovery_mgr:
                self.recovery_mgr.mark_clean_shutdown()
                self.recovery_mgr.clear_session_snapshots()
        except Exception:
            pass
        self.root.destroy()

    def _after_successful_open(self):
        self._remember_recent(self.file_mgr.current_file_path)
        try:
            self.editor.edit_modified(False)
        except Exception:
            pass
        self.clear_document_search(clear_field=True)
        self._set_dirty(False)
        self.refresh_navigation()
        self.syntax.highlight()
        self._update_document_meta()

    def open_file(self):
        if not self._ensure_security_ready():
            return False
        if not self._prompt_save_if_dirty():
            return False

        ok = self.file_mgr.open_file()
        if ok:
            self._after_successful_open()
            self.log("Opened document")
            return True
        return False

    def new_from_template(self):
        if not self._prompt_save_if_dirty():
            return False

        selection = self.tools.open_template_picker()
        if not selection:
            return False

        if isinstance(selection, dict):
            template_id = selection.get("template_id")
            template_style = selection.get("style")
        else:
            template_id = str(selection)
            template_style = None
        if not template_id:
            return False

        template = get_template_by_id(template_id)
        if template is None:
            messagebox.showerror("Template Error", "Template could not be loaded.")
            return False

        if not template_style:
            template_style = template.preferred_style

        if not self.tools.apply_template(template.body, style=template_style):
            return False

        self.file_mgr.current_file_path = None
        try:
            self.editor.edit_modified(False)
        except Exception:
            pass
        self.clear_document_search(clear_field=True)
        self._set_dirty(True)
        self.refresh_navigation()
        self.syntax.highlight()
        self._update_document_meta()
        self.log(f"Template loaded: {template.title} ({template_style})")
        return True

    def save_current_as_template(self):
        full_content = self.editor.get("1.0", "end-1c")

        selected_content = ""
        try:
            selected_content = self.editor.get("sel.first", "sel.last")
        except tk.TclError:
            selected_content = ""

        default_name = re.sub(r"\..*$", "", self.shell.top_strip.doc_title.cget("text") or "").strip()
        if not default_name or default_name.lower() == "untitled":
            default_name = "My Template"

        template_config = self._open_template_save_dialog(
            default_name=default_name,
            has_selection=bool(selected_content.strip()),
            source_text=selected_content if selected_content.strip() else full_content,
        )
        if not template_config:
            return False

        ai_template_body = str(template_config.get("ai_body", ""))
        if ai_template_body.strip():
            template_body = ai_template_body
        else:
            use_selection = bool(template_config.get("selection_only", False))
            template_body = selected_content if use_selection else full_content
        if not template_body.strip():
            messagebox.showerror(
                "Save Template",
                "Template content is empty. Add document text or generate AI markdown.",
            )
            return False

        try:
            template = save_custom_template(
                title=str(template_config.get("title", "")).strip(),
                description=str(template_config.get("description", "")).strip(),
                body=template_body,
                category=str(template_config.get("category", "")).strip(),
                preferred_style=str(template_config.get("preferred_style", "")).strip(),
                overwrite_existing=bool(template_config.get("overwrite_existing", False)),
            )
        except ValueError as exc:
            messagebox.showerror("Save Template", str(exc))
            return False
        except OSError as exc:
            messagebox.showerror("Save Template", f"Could not save template:\n{exc}")
            return False

        self.log(
            f"Saved template: {template.title}"
            f" [{template.category}, {template.preferred_style}]"
        )
        return True

    def _open_template_save_dialog(self, default_name: str, has_selection: bool, source_text: str) -> dict | None:
        style_options = list_template_style_presets() or ["Professional Blue"]
        category_options = list_template_categories() or ["General"]

        default_style = self.tools.template_style if self.tools.template_style in style_options else style_options[0]
        result = {"accepted": False}

        win = tk.Toplevel(self.root)
        win.title("Save Template")
        win.geometry("760x650")
        win.minsize(700, 600)
        win.transient(self.root)
        win.grab_set()

        body = tk.Frame(win, padx=14, pady=12)
        body.pack(fill=tk.BOTH, expand=True)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(10, weight=1)

        title_var = tk.StringVar(value=default_name)
        desc_var = tk.StringVar(value="Custom template")
        category_var = tk.StringVar(value=category_options[0])
        style_var = tk.StringVar(value=default_style)
        selection_only_var = tk.BooleanVar(value=has_selection)
        overwrite_var = tk.BooleanVar(value=False)
        ai_prompt_var = tk.StringVar(value="")
        use_ai_var = tk.BooleanVar(value=False)
        error_var = tk.StringVar(value="")

        ttk.Label(body, text="Template name").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        title_entry = ttk.Entry(body, textvariable=title_var)
        title_entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(body, text="Description").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        ttk.Entry(body, textvariable=desc_var).grid(row=1, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(body, text="Category").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        ttk.Combobox(
            body,
            textvariable=category_var,
            values=category_options,
            state="readonly",
            width=24,
        ).grid(row=2, column=1, sticky="w", pady=(0, 8))

        ttk.Label(body, text="Default style").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        ttk.Combobox(
            body,
            textvariable=style_var,
            values=style_options,
            state="readonly",
            width=24,
        ).grid(row=3, column=1, sticky="w", pady=(0, 8))

        selection_check = ttk.Checkbutton(
            body,
            text="Save selected text only",
            variable=selection_only_var,
        )
        selection_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))
        if not has_selection:
            selection_check.state(["disabled"])
            selection_only_var.set(False)

        ttk.Checkbutton(
            body,
            text="Replace existing template with same name",
            variable=overwrite_var,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Separator(body, orient="horizontal").grid(row=6, column=0, columnspan=2, sticky="ew", pady=(12, 8))
        ttk.Label(body, text="AI Markdown Template Builder", font=("Segoe UI", 10, "bold")).grid(
            row=7, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(body, text="Prompt").grid(row=8, column=0, sticky="w", padx=(0, 10), pady=(6, 6))
        prompt_entry = ttk.Entry(body, textvariable=ai_prompt_var)
        prompt_entry.grid(row=8, column=1, sticky="ew", pady=(6, 6))

        ai_btn_row = tk.Frame(body)
        ai_btn_row.grid(row=9, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ai_text = tk.Text(
            body,
            wrap=tk.WORD,
            height=12,
            relief=tk.SUNKEN,
            bd=1,
            font=("Consolas", 10),
            padx=8,
            pady=8,
        )
        ai_text.grid(row=10, column=0, columnspan=2, sticky="nsew")

        ttk.Checkbutton(
            body,
            text="Use AI-generated markdown content when saving",
            variable=use_ai_var,
        ).grid(row=11, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Label(body, textvariable=error_var, foreground="#c23838").grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

        btn_row = tk.Frame(body)
        btn_row.grid(row=13, column=0, columnspan=2, sticky="e", pady=(14, 0))

        def _set_ai_text(content: str):
            ai_text.delete("1.0", tk.END)
            ai_text.insert("1.0", content)

        def _generate_ai():
            prompt = ai_prompt_var.get().strip()
            if not prompt and not source_text.strip():
                error_var.set("Enter an AI prompt or keep document text.")
                prompt_entry.focus_set()
                return
            draft = generate_template_draft(
                prompt=prompt,
                category=category_var.get().strip(),
                context_text=source_text,
            )
            title_var.set(draft.title)
            if not desc_var.get().strip() or desc_var.get().strip().lower() == "custom template":
                desc_var.set(draft.description)
            if draft.category in category_options:
                category_var.set(draft.category)
            if draft.preferred_style in style_options:
                style_var.set(draft.preferred_style)
            _set_ai_text(draft.body)
            use_ai_var.set(True)
            source_label = "OpenAI" if draft.source == "openai" else "local AI engine"
            error_var.set(f"AI markdown generated via {source_label}. You can edit it below.")

        def _seed_ai_from_doc():
            snippet = (source_text or "").strip()
            if not snippet:
                return
            ai_prompt_var.set(snippet[:240])
            prompt_entry.icursor(tk.END)

        def _import_markdown_source():
            path = filedialog.askopenfilename(
                title="Import Markdown Template Source",
                parent=win,
                filetypes=[
                    ("Markdown", ("*.md", "*.markdown", "*.mdown", "*.mkd")),
                    ("Text", ("*.txt",)),
                    ("All Files", "*.*"),
                ],
            )
            if not path:
                return
            category_hint = category_var.get().strip()
            style_hint = style_var.get().strip()
            try:
                with open(path, "r", encoding="utf-8-sig") as handle:
                    markdown_content = handle.read()
            except UnicodeDecodeError:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    markdown_content = handle.read()
            except OSError as exc:
                error_var.set(f"Could not read markdown file: {exc}")
                return

            try:
                imported = parse_markdown_template_content(
                    markdown_content,
                    source_name=os.path.basename(path),
                    fallback_category=category_hint,
                    fallback_style=style_hint,
                )
            except ValueError as exc:
                error_var.set(str(exc))
                return

            title_var.set(str(imported.get("title", "")).strip() or title_var.get().strip())
            desc_var.set(str(imported.get("description", "")).strip() or desc_var.get().strip())
            imported_category = str(imported.get("category", "")).strip()
            if imported_category in category_options:
                category_var.set(imported_category)
            imported_style = str(imported.get("preferred_style", "")).strip()
            if imported_style in style_options:
                style_var.set(imported_style)
            _set_ai_text(str(imported.get("body", "")))
            use_ai_var.set(True)
            error_var.set(f"Imported markdown content from {os.path.basename(path)}.")

        ttk.Button(ai_btn_row, text="Generate Markdown", width=18, command=_generate_ai).pack(side=tk.LEFT)
        ttk.Button(ai_btn_row, text="Use Document as Prompt", width=20, command=_seed_ai_from_doc).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(ai_btn_row, text="Import Markdown...", width=18, command=_import_markdown_source).pack(side=tk.LEFT, padx=(8, 0))

        def _submit():
            clean_title = title_var.get().strip()
            if not clean_title:
                error_var.set("Template name is required.")
                title_entry.focus_set()
                return
            ai_body = ai_text.get("1.0", "end-1c")
            if use_ai_var.get() and not ai_body.strip():
                error_var.set("Generate AI markdown or turn off AI content.")
                return
            result.update(
                {
                    "accepted": True,
                    "title": clean_title,
                    "description": desc_var.get().strip(),
                    "category": category_var.get().strip(),
                    "preferred_style": style_var.get().strip(),
                    "selection_only": bool(selection_only_var.get()),
                    "overwrite_existing": bool(overwrite_var.get()),
                    "ai_body": ai_body if use_ai_var.get() else "",
                }
            )
            win.destroy()

        ttk.Button(btn_row, text="Cancel", width=10, command=win.destroy).pack(side=tk.RIGHT)
        ttk.Button(btn_row, text="Save Template", width=13, command=_submit).pack(side=tk.RIGHT, padx=(0, 8))

        title_entry.bind("<Return>", lambda _event: _submit(), add="+")
        win.bind("<Escape>", lambda _event: win.destroy())
        title_entry.focus_set()
        title_entry.select_range(0, tk.END)
        self.root.wait_window(win)

        if not result.get("accepted"):
            return None
        result.pop("accepted", None)
        return result

    def open_recent(self, path):
        if not path:
            return False
        if not self._ensure_security_ready():
            return False
        if not self._prompt_save_if_dirty():
            return False
        if not os.path.exists(path):
            messagebox.showerror("Recent File", f"File not found:\n{path}")
            return False

        ok = self.file_mgr.open_path(path)
        if ok:
            self._after_successful_open()
            self.log("Opened recent document")
            return True
        return False

    def save_file(self):
        ok = self.file_mgr.save_file()
        if ok:
            self._remember_recent(self.file_mgr.current_file_path)
            try:
                self.editor.edit_modified(False)
            except Exception:
                pass
            self._set_dirty(False)
            self.log("Saved document")
            return True
        return False

    def run_spell_check(self):
        if self.processor.run_spell_check():
            self.log("Spell check completed")
            return True
        self.log("Spell check did not run")
        return False

    def _persist_custom_dictionary_entries(self, entries: dict | None):
        self.ui_settings["dictionary_custom_entries"] = entries if isinstance(entries, dict) else {}
        self._refresh_processor_dictionary_words()
        self.config_mgr.save()

    def open_dictionary_lookup(self):
        ok = self.tools.open_dictionary_lookup()
        if ok:
            self.log("Dictionary lookup opened")
            return True
        return False

    def open_wiki_lookup(self):
        ok = self.tools.open_wiki_lookup()
        if ok:
            self.log("Wikipedia lookup opened")
            return True
        return False

    def _refresh_processor_dictionary_words(self):
        if not hasattr(self, "processor") or not hasattr(self, "tools"):
            return False
        try:
            entries = self.tools.get_custom_dictionary_entries()
            self.processor.set_custom_dictionary_words(entries.keys())
            return True
        except Exception:
            return False

    def read_aloud(self):
        if self.processor.read_aloud():
            self.log("Read aloud started")
            return True
        self.log("Read aloud did not start")
        return False

    def show_stats(self):
        self.tools.show_stats()
        self.log("Document stats shown")
        self._update_document_meta()
        return True

    def navigate_to_index(self, index):
        if not index:
            return False
        try:
            self.editor.see(index)
            self.editor.mark_set(tk.INSERT, index)
            self.editor.focus()
            return True
        except Exception:
            return False

    def _execute_and_refresh(self, action, message=None, refresh=True, mark_dirty=False):
        result = action()
        if result is False:
            return False

        if refresh:
            self.refresh_navigation()
            self.syntax.trigger()
            self._update_document_meta()
        if mark_dirty:
            self._set_dirty(True)
        if message:
            self.log(message)
        return True

    # -----------------------------
    # Undo/Redo + Zoom
    # -----------------------------

    def safe_undo(self):
        changed = False
        try:
            if self.formatter.undo_format():
                changed = True
        except Exception:
            pass
        if not changed:
            try:
                self.editor.edit_undo()
                self.formatter.note_text_activity()
                changed = True
            except tk.TclError:
                pass
        if changed:
            self._set_dirty(True)
            self.refresh_navigation()
            self.syntax.trigger()
            self._update_document_meta()
            if getattr(self, "_search_query", ""):
                self.update_document_search(self._search_query, navigate=False, refresh=True)
        return changed

    def safe_redo(self):
        changed = False
        try:
            if self.formatter.redo_format():
                changed = True
        except Exception:
            pass
        if not changed:
            try:
                self.editor.edit_redo()
                changed = True
            except tk.TclError:
                pass
        if changed:
            self._set_dirty(True)
            self.refresh_navigation()
            self.syntax.trigger()
            self._update_document_meta()
            if getattr(self, "_search_query", ""):
                self.update_document_search(self._search_query, navigate=False, refresh=True)
        return changed

    def update_zoom(self, amount=0, absolute=None):
        current = self.formatter.zoom_level
        new_zoom = absolute if absolute is not None else current + amount
        new_zoom = max(50, min(200, int(new_zoom)))

        self.formatter.set_zoom(new_zoom)
        self.tools.set_zoom(new_zoom)
        self.shell.set_zoom(new_zoom)
        self.settings["zoom"] = new_zoom
        self.config_mgr.save()
        self._sync_view_state()
        self._update_document_meta()
        return True

    # -----------------------------
    # Bindings / navigation / status
    # -----------------------------

    def _bind_shortcuts(self):
        self.root.bind("<Control-s>", lambda _e: self.save_file())
        self.root.bind("<Control-o>", lambda _e: self.open_file())
        self.root.bind("<Control-f>", lambda _e: self.execute_ui_command(UiCommandRequest(UiCommandId.FIND_REPLACE)))
        self.root.bind("<Control-z>", lambda _e: self.safe_undo())
        self.root.bind("<Control-y>", lambda _e: self.safe_redo())
        self.root.bind("<Control-Shift-N>", lambda _e: self.new_from_template())
        self.root.bind("<Control-Alt-t>", lambda _e: self.save_current_as_template())
        self.root.bind("<Control-Shift-A>", lambda _e: self.execute_ui_command(UiCommandRequest(UiCommandId.ACTION_HUB)))
        self.root.bind("<Control-Shift-F>", lambda _e: self.toggle_focus_mode())
        self.root.bind("<Control-Shift-C>", lambda _e: self.toggle_console())
        self.root.bind("<Control-Shift-R>", lambda _e: self.toggle_rulers())
        self.root.bind("<Control-Shift-D>", lambda _e: self.execute_ui_command(UiCommandRequest(UiCommandId.DICTIONARY_LOOKUP)))
        self.root.bind("<Control-Shift-W>", lambda _e: self.execute_ui_command(UiCommandRequest(UiCommandId.WIKI_LOOKUP)))
        self.root.bind("<Control-Shift-L>", lambda _e: self.execute_ui_command(UiCommandRequest(UiCommandId.READ_ALOUD)))
        self.root.bind(
            "<Control-Shift-P>",
            lambda _e: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN_COMMAND_PALETTE)),
        )
        try:
            self.root.bind(
                "<Command-Shift-P>",
                lambda _e: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN_COMMAND_PALETTE)),
            )
        except tk.TclError:
            pass

        def _on_modified(_evt):
            try:
                if self.editor.edit_modified():
                    self.formatter.note_text_activity()
                    self.syntax.trigger()
                    self.refresh_navigation()
                    self._set_dirty(True)
                    self.editor.edit_modified(False)
                    if getattr(self, "_search_query", ""):
                        self.update_document_search(self._search_query, navigate=False, refresh=True)
            except Exception:
                pass

        self.editor.bind("<<Modified>>", _on_modified, add="+")
        self.editor.bind("<Return>", self.formatter.handle_return_key, add="+")
        self.editor.bind("<KeyRelease>", lambda _e: self.syntax.trigger(), add="+")

    def _cut_selection(self):
        try:
            self.editor.get("sel.first", "sel.last")
        except tk.TclError:
            return False
        self.editor.event_generate("<<Cut>>")
        return True

    def _copy_selection(self):
        try:
            self.editor.get("sel.first", "sel.last")
        except tk.TclError:
            return False
        self.editor.event_generate("<<Copy>>")
        return True

    def _paste_selection(self):
        try:
            self.root.clipboard_get()
        except tk.TclError:
            return False
        self.editor.event_generate("<<Paste>>")
        return True

    def _paste_plain_text(self):
        try:
            plain = self.root.clipboard_get()
        except tk.TclError:
            return False
        if not plain:
            return False
        self.editor.insert(tk.INSERT, plain)
        return True

    def _delete_selection(self):
        try:
            self.editor.delete("sel.first", "sel.last")
            return True
        except tk.TclError:
            return False

    def _build_editor_context_menu(self):
        menu = tk.Menu(self.root, tearoff=False)
        self.editor_context_menu = menu

        menu.add_command(label="Undo", command=self.safe_undo)
        menu.add_command(label="Redo", command=self.safe_redo)
        menu.add_separator()
        menu.add_command(
            label="Cut",
            command=lambda: self._execute_and_refresh(
                self._cut_selection,
                "Cut selection",
                mark_dirty=True,
            ),
        )
        menu.add_command(label="Copy", command=lambda: self.editor.event_generate("<<Copy>>"))
        menu.add_command(
            label="Paste",
            command=lambda: self._execute_and_refresh(
                self._paste_selection,
                "Pasted content",
                mark_dirty=True,
            ),
        )
        menu.add_command(
            label="Paste Plain Text",
            command=lambda: self._execute_and_refresh(
                self._paste_plain_text,
                "Pasted plain text",
                mark_dirty=True,
            ),
        )
        menu.add_command(
            label="Delete",
            command=lambda: self._execute_and_refresh(
                self._delete_selection,
                "Deleted selection",
                mark_dirty=True,
            ),
        )
        menu.add_command(label="Select All", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SELECT_ALL)))
        menu.add_command(label="Dictionary Lookup", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.DICTIONARY_LOOKUP)))
        menu.add_command(label="Read Aloud", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.READ_ALOUD)))
        menu.add_separator()

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN)))
        file_menu.add_command(label="Save", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SAVE)))
        file_menu.add_command(label="Export PDF", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.EXPORT_PDF)))
        file_menu.add_separator()
        file_menu.add_command(
            label="New From Template...",
            command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.NEW_FROM_TEMPLATE)),
        )
        file_menu.add_command(
            label="Save Current As Template...",
            command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SAVE_AS_TEMPLATE)),
        )
        menu.add_cascade(label="File / Export", menu=file_menu)

        insert_menu = tk.Menu(menu, tearoff=False)
        insert_menu.add_command(label="Insert Image", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_IMAGE)))
        insert_menu.add_command(label="Insert Table...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_TABLE)))
        insert_menu.add_command(label="Insert Checklist...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_CHECKLIST)))
        insert_menu.add_command(label="Insert Date / Time", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_DATE_TIME)))
        insert_menu.add_command(label="Insert Horizontal Rule", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_HORIZONTAL_LINE)))
        insert_menu.add_command(label="Insert Symbol", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_SYMBOL)))
        insert_menu.add_command(label="Insert Page Break", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_PAGE_BREAK)))
        menu.add_cascade(label="Insert", menu=insert_menu)

        review_menu = tk.Menu(menu, tearoff=False)
        review_menu.add_command(label="Spell Check", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SPELL_CHECK)))
        review_menu.add_command(label="Dictionary Lookup", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.DICTIONARY_LOOKUP)))
        review_menu.add_command(label="Wikipedia Lookup", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.WIKI_LOOKUP)))
        review_menu.add_command(label="Read Aloud", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.READ_ALOUD)))
        review_menu.add_command(label="Action Hub", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ACTION_HUB)))
        review_menu.add_command(
            label="Export Fancy To-Do Report",
            command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.EXPORT_TODO_REPORT)),
        )
        review_menu.add_command(label="Document Stats", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SHOW_STATS)))
        menu.add_cascade(label="Review", menu=review_menu)

        toolbar_layout_menu = tk.Menu(menu, tearoff=False)
        toolbar_layout_menu.add_command(label="Export Toolbar Layout...", command=self.export_toolbar_layout)
        toolbar_layout_menu.add_command(label="Import Toolbar Layout...", command=self.import_toolbar_layout)
        menu.add_cascade(label="Toolbar Layout", menu=toolbar_layout_menu)
        menu.add_separator()

        format_menu = tk.Menu(menu, tearoff=False)
        format_menu.add_command(label="Bold", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.BOLD)))
        format_menu.add_command(label="Italic", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ITALIC)))
        format_menu.add_command(label="Underline", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.UNDERLINE)))
        format_menu.add_command(label="Strike", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.STRIKE)))
        format_menu.add_separator()
        format_menu.add_command(label="Align Left", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ALIGN_LEFT)))
        format_menu.add_command(label="Align Center", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ALIGN_CENTER)))
        format_menu.add_command(label="Align Right", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ALIGN_RIGHT)))
        format_menu.add_separator()
        format_menu.add_command(label="Bullets", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.BULLET_LIST)))
        format_menu.add_command(label="Numbering", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.NUMBERED_LIST)))
        format_menu.add_separator()
        format_menu.add_command(label="Clear Formatting", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CLEAR_FORMATTING)))
        menu.add_cascade(label="Formatting", menu=format_menu)

        line_spacing_menu = tk.Menu(menu, tearoff=False)
        line_spacing_menu.add_command(
            label="Single (1.0)",
            command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.LINE_SPACING, {"value": 1.0})),
        )
        line_spacing_menu.add_command(
            label="1.5",
            command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.LINE_SPACING, {"value": 1.5})),
        )
        line_spacing_menu.add_command(
            label="Double (2.0)",
            command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.LINE_SPACING, {"value": 2.0})),
        )
        menu.add_cascade(label="Line Spacing", menu=line_spacing_menu)

        typography_menu = tk.Menu(menu, tearoff=False)
        typography_menu.add_command(label="Increase Size", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.FONT_SIZE_INCREASE)))
        typography_menu.add_command(label="Decrease Size", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.FONT_SIZE_DECREASE)))
        typography_menu.add_separator()
        typography_menu.add_command(label="Body", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Body"})))
        typography_menu.add_command(label="Title", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Title"})))
        typography_menu.add_command(label="Heading 1", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Heading 1"})))
        typography_menu.add_command(label="Heading 2", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Heading 2"})))
        typography_menu.add_command(label="Heading 3", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Heading 3"})))
        typography_menu.add_command(label="Quote", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Quote"})))
        typography_menu.add_command(label="Code", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Code"})))
        typography_menu.add_command(label="Caption", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.APPLY_TEXT_STYLE, {"value": "Caption"})))
        menu.add_cascade(label="Typography", menu=typography_menu)

        case_menu = tk.Menu(menu, tearoff=False)
        case_menu.add_command(
            label="UPPERCASE",
            command=lambda: self._execute_and_refresh(
                lambda: self.tools.convert_case("upper"),
                "Applied uppercase",
                mark_dirty=True,
            ),
        )
        case_menu.add_command(
            label="lowercase",
            command=lambda: self._execute_and_refresh(
                lambda: self.tools.convert_case("lower"),
                "Applied lowercase",
                mark_dirty=True,
            ),
        )
        case_menu.add_command(
            label="Title Case",
            command=lambda: self._execute_and_refresh(
                lambda: self.tools.convert_case("title"),
                "Applied title case",
                mark_dirty=True,
            ),
        )
        case_menu.add_command(
            label="Sentence case",
            command=lambda: self._execute_and_refresh(
                lambda: self.tools.convert_case("sentence"),
                "Applied sentence case",
                mark_dirty=True,
            ),
        )
        menu.add_cascade(label="Change Case", menu=case_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
        tools_menu.add_command(
            label="Duplicate Line/Selection",
            command=lambda: self._execute_and_refresh(
                self.tools.duplicate_selection_or_line,
                "Duplicated line/selection",
                mark_dirty=True,
            ),
        )
        tools_menu.add_command(
            label="Sort Lines A-Z",
            command=lambda: self._execute_and_refresh(
                lambda: self.tools.sort_selected_lines(reverse=False),
                "Sorted lines A-Z",
                mark_dirty=True,
            ),
        )
        tools_menu.add_command(
            label="Sort Lines Z-A",
            command=lambda: self._execute_and_refresh(
                lambda: self.tools.sort_selected_lines(reverse=True),
                "Sorted lines Z-A",
                mark_dirty=True,
            ),
        )
        tools_menu.add_command(
            label="Trim Trailing Spaces",
            command=lambda: self._execute_and_refresh(
                self.tools.clean_trailing_whitespace,
                "Removed trailing spaces",
                mark_dirty=True,
            ),
        )
        tools_menu.add_separator()
        tools_menu.add_command(label="Insert Table...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_TABLE)))
        tools_menu.add_command(label="Insert Checklist...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_CHECKLIST)))
        tools_menu.add_command(label="Insert Date/Time", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_DATE_TIME)))
        tools_menu.add_command(label="Insert Horizontal Rule", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_HORIZONTAL_LINE)))
        tools_menu.add_command(label="Insert Page Break", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.INSERT_PAGE_BREAK)))
        tools_menu.add_command(label="Memo Builder...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.OPEN_MEMO_BUILDER)))
        tools_menu.add_separator()
        tools_menu.add_command(label="Find and Replace", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.FIND_REPLACE)))
        tools_menu.add_command(label="Dictionary Lookup", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.DICTIONARY_LOOKUP)))
        tools_menu.add_command(label="Wikipedia Lookup", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.WIKI_LOOKUP)))
        tools_menu.add_command(label="Action Hub", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.ACTION_HUB)))
        tools_menu.add_command(label="Export Fancy To-Do Report", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.EXPORT_TODO_REPORT)))
        tools_menu.add_command(label="Document Stats", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SHOW_STATS)))
        tools_menu.add_separator()
        tools_menu.add_command(label="Set Default Logo...", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.SET_DEFAULT_LOGO)))
        tools_menu.add_command(label="Clear Default Logo", command=lambda: self.execute_ui_command(UiCommandRequest(UiCommandId.CLEAR_DEFAULT_LOGO)))
        menu.add_cascade(label="Professional Tools", menu=tools_menu)

        self.editor.bind("<Button-3>", self._show_editor_context_menu, add="+")
        self.editor.bind("<Button-2>", self._show_editor_context_menu, add="+")
        self.editor.bind("<Control-Button-1>", self._show_editor_context_menu, add="+")

    def _show_editor_context_menu(self, event):
        try:
            self.editor.focus_set()
            try:
                self.editor.mark_set(tk.INSERT, f"@{event.x},{event.y}")
            except tk.TclError:
                pass
            self.editor_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.editor_context_menu.grab_release()
        return "break"

    def refresh_navigation(self):
        items = []
        lines = self.editor.get("1.0", "end-1c").splitlines()
        for i, raw in enumerate(lines, start=1):
            text = raw.strip()
            if not text:
                continue

            level = 0
            heading = text
            match = re.match(r"^(#{1,6})\s+(.*)$", text)
            if match:
                level = len(match.group(1)) - 1
                heading = match.group(2)
            elif len(text) > 60:
                continue

            label = f"{'  ' * level}{heading[:45]}"
            items.append((label, f"{i}.0"))

        if not items:
            items = [("Document Start", "1.0")]

        self.shell.set_navigation_items(items)
        self._update_document_meta()

    def _update_document_meta(self):
        try:
            text = self.editor.get("1.0", "end-1c")
            words = len(text.split())
            chars = len(text)
            lines = int(self.editor.index("end-1c").split(".")[0])
            self.shell.set_document_meta(words, chars, lines)
        except Exception:
            pass

    def log(self, message):
        self.shell.append_console(message)
        self.shell.set_status(message)

    # -----------------------------
    # Recovery / Autosave
    # -----------------------------

    def _save_recovery_snapshot(self, force: bool = False):
        if not hasattr(self, "recovery_mgr") or not self.recovery_mgr or not self.recovery_mgr.enabled:
            return False
        try:
            text = self.editor.get("1.0", "end-1c")
        except Exception:
            return False
        if not force and not self.is_dirty and not text.strip():
            return False
        context = {
            "dirty": bool(self.is_dirty),
            "current_file_path": str(getattr(self.file_mgr, "current_file_path", "") or ""),
            "zoom": int(self.settings.get("zoom", 100)),
            "theme": str(self.current_theme),
        }
        try:
            return bool(self.recovery_mgr.save_snapshot(text, context))
        except Exception:
            return False

    def _autosave_tick(self):
        self._autosave_after_id = None
        self._save_recovery_snapshot()
        self._schedule_autosave()

    def _schedule_autosave(self):
        self._cancel_autosave()
        if not hasattr(self, "recovery_mgr") or not self.recovery_mgr or not self.recovery_mgr.enabled:
            return False
        interval_seconds = 30
        try:
            interval_seconds = int(self.recovery_settings.get("interval_seconds", 30))
        except Exception:
            interval_seconds = 30
        interval_ms = max(5000, interval_seconds * 1000)
        try:
            self._autosave_after_id = self.root.after(interval_ms, self._autosave_tick)
            return True
        except Exception:
            self._autosave_after_id = None
            return False

    def _cancel_autosave(self):
        job_id = getattr(self, "_autosave_after_id", None)
        self._autosave_after_id = None
        if job_id is None:
            return False
        try:
            self.root.after_cancel(job_id)
            return True
        except Exception:
            return False

    def _maybe_restore_recovery_snapshot(self):
        if not hasattr(self, "recovery_mgr") or not self.recovery_mgr or not self.recovery_mgr.enabled:
            return False
        try:
            snapshot = self.recovery_mgr.latest_snapshot()
        except Exception:
            return False
        if not isinstance(snapshot, dict):
            return False
        text = str(snapshot.get("text", "") or "")
        if not text.strip():
            return False
        timestamp = str(snapshot.get("timestamp_utc", "") or "").strip()
        details = f"\n\nSnapshot time: {timestamp}" if timestamp else ""
        should_restore = messagebox.askyesno(
            "Recover Unsaved Document",
            "An unexpected shutdown was detected. Restore the latest autosave snapshot?" + details,
        )
        if not should_restore:
            return False
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", text)
        self.file_mgr.current_file_path = None
        try:
            self.editor.edit_modified(False)
        except Exception:
            pass
        self.clear_document_search(clear_field=True)
        self._set_dirty(True)
        self.refresh_navigation()
        self.syntax.highlight()
        self._update_document_meta()
        self.log("Recovered unsaved document from autosave snapshot")
        return True
