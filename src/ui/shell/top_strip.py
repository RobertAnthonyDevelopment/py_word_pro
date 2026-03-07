import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

from src.ui.contracts import UiCommandId, UiCommandRequest


class TopStrip(tk.Frame):
    SEARCH_PLACEHOLDER = "Search in document"

    TOOL_SPECS = [
        {"id": "open", "label": "Open", "icon": "⤓", "command_id": UiCommandId.OPEN},
        {"id": "templates", "label": "Templates", "icon": "▦", "command_id": UiCommandId.NEW_FROM_TEMPLATE},
        {"id": "save", "label": "Save", "icon": "⤒", "command_id": UiCommandId.SAVE, "primary": True},
        {"id": "undo", "label": "Undo", "icon": "↶", "command_id": UiCommandId.UNDO},
        {"id": "redo", "label": "Redo", "icon": "↷", "command_id": UiCommandId.REDO},
        {"id": "cut", "label": "Cut", "icon": "✂", "command_id": UiCommandId.CUT},
        {"id": "copy", "label": "Copy", "icon": "⧉", "command_id": UiCommandId.COPY},
        {"id": "paste", "label": "Paste", "icon": "⎘", "command_id": UiCommandId.PASTE},
        {"id": "bold", "label": "Bold", "icon": "B", "command_id": UiCommandId.BOLD},
        {"id": "italic", "label": "Italic", "icon": "I", "command_id": UiCommandId.ITALIC},
        {"id": "underline", "label": "Underline", "icon": "U", "command_id": UiCommandId.UNDERLINE},
        {"id": "find", "label": "Find", "icon": "⌕", "command_id": UiCommandId.FIND_REPLACE},
        {"id": "spell", "label": "Spell", "icon": "✓", "command_id": UiCommandId.SPELL_CHECK},
        {"id": "dictionary", "label": "Dictionary", "icon": "ABC", "command_id": UiCommandId.DICTIONARY_LOOKUP},
        {"id": "read_aloud", "label": "Read Aloud", "icon": "▶", "command_id": UiCommandId.READ_ALOUD},
        {"id": "action_hub", "label": "Action Hub", "icon": "☑", "command_id": UiCommandId.ACTION_HUB},
        {"id": "command_palette", "label": "Commands", "icon": "⌘", "command_id": UiCommandId.OPEN_COMMAND_PALETTE},
        {"id": "focus_mode", "label": "Focus Mode", "icon": "◱", "command_id": UiCommandId.TOGGLE_FOCUS},
    ]

    DEFAULT_TOOL_IDS = [
        "open",
        "templates",
        "save",
        "undo",
        "redo",
        "find",
        "read_aloud",
        "command_palette",
        "focus_mode",
    ]

    ICON_COMMAND_SPECS = [
        {"id": "open", "label": "Open", "icon": "O", "command_id": UiCommandId.OPEN},
        {
            "id": "open_recent",
            "label": "Recent",
            "icon": "R",
            "command_id": UiCommandId.OPEN_RECENT,
            "payload": {"path": "__latest_recent__"},
        },
        {"id": "save", "label": "Save", "icon": "S", "command_id": UiCommandId.SAVE},
        {"id": "new_template", "label": "Template", "icon": "T", "command_id": UiCommandId.NEW_FROM_TEMPLATE},
        {"id": "save_template", "label": "SaveTpl", "icon": "TS", "command_id": UiCommandId.SAVE_AS_TEMPLATE},
        {"id": "export_pdf", "label": "PDF", "icon": "P", "command_id": UiCommandId.EXPORT_PDF},
        {"id": "undo", "label": "Undo", "icon": "↶", "command_id": UiCommandId.UNDO},
        {"id": "redo", "label": "Redo", "icon": "↷", "command_id": UiCommandId.REDO},
        {"id": "cut", "label": "Cut", "icon": "✂", "command_id": UiCommandId.CUT},
        {"id": "copy", "label": "Copy", "icon": "C", "command_id": UiCommandId.COPY},
        {"id": "paste", "label": "Paste", "icon": "V", "command_id": UiCommandId.PASTE},
        {"id": "paste_plain", "label": "PasteTxt", "icon": "VT", "command_id": UiCommandId.PASTE_PLAIN},
        {"id": "delete", "label": "Delete", "icon": "X", "command_id": UiCommandId.DELETE_SELECTION},
        {"id": "duplicate", "label": "Duplicate", "icon": "D+", "command_id": UiCommandId.DUPLICATE_SELECTION},
        {"id": "sort_asc", "label": "Sort A-Z", "icon": "AZ", "command_id": UiCommandId.SORT_LINES_ASC},
        {"id": "sort_desc", "label": "Sort Z-A", "icon": "ZA", "command_id": UiCommandId.SORT_LINES_DESC},
        {"id": "trim_spaces", "label": "Trim", "icon": "Tx", "command_id": UiCommandId.TRIM_TRAILING_SPACES},
        {"id": "case_upper", "label": "UPPER", "icon": "UP", "command_id": UiCommandId.CHANGE_CASE_UPPER},
        {"id": "case_lower", "label": "lower", "icon": "lo", "command_id": UiCommandId.CHANGE_CASE_LOWER},
        {"id": "case_title", "label": "Title", "icon": "Tt", "command_id": UiCommandId.CHANGE_CASE_TITLE},
        {"id": "case_sentence", "label": "Sentence", "icon": "Ss", "command_id": UiCommandId.CHANGE_CASE_SENTENCE},
        {"id": "find_replace", "label": "Find", "icon": "⌕", "command_id": UiCommandId.FIND_REPLACE},
        {"id": "search", "label": "Search", "icon": "?", "command_id": UiCommandId.DOCUMENT_SEARCH, "payload_from": "search_query"},
        {"id": "search_next", "label": "Next", "icon": ">", "command_id": UiCommandId.DOCUMENT_SEARCH_NEXT, "payload_from": "search_query"},
        {"id": "search_prev", "label": "Prev", "icon": "<", "command_id": UiCommandId.DOCUMENT_SEARCH_PREV, "payload_from": "search_query"},
        {"id": "search_clear", "label": "ClrFind", "icon": "x?", "command_id": UiCommandId.DOCUMENT_SEARCH_CLEAR, "payload": {"query": ""}},
        {"id": "select_all", "label": "SelectAll", "icon": "A", "command_id": UiCommandId.SELECT_ALL},
        {"id": "bold", "label": "Bold", "icon": "B", "command_id": UiCommandId.BOLD},
        {"id": "italic", "label": "Italic", "icon": "I", "command_id": UiCommandId.ITALIC},
        {"id": "underline", "label": "Under", "icon": "U", "command_id": UiCommandId.UNDERLINE},
        {"id": "strike", "label": "Strike", "icon": "St", "command_id": UiCommandId.STRIKE},
        {"id": "text_color", "label": "TextColor", "icon": "A*", "command_id": UiCommandId.TEXT_COLOR},
        {"id": "highlight", "label": "Highlight", "icon": "HL", "command_id": UiCommandId.HIGHLIGHT},
        {"id": "align_left", "label": "Left", "icon": "L", "command_id": UiCommandId.ALIGN_LEFT},
        {"id": "align_center", "label": "Center", "icon": "C", "command_id": UiCommandId.ALIGN_CENTER},
        {"id": "align_right", "label": "Right", "icon": "R", "command_id": UiCommandId.ALIGN_RIGHT},
        {"id": "bullets", "label": "Bullets", "icon": "•", "command_id": UiCommandId.BULLET_LIST},
        {"id": "numbered", "label": "Number", "icon": "1.", "command_id": UiCommandId.NUMBERED_LIST},
        {"id": "line_1_0", "label": "Line 1.0", "icon": "↕", "command_id": UiCommandId.LINE_SPACING, "payload": {"value": 1.0}},
        {"id": "line_1_5", "label": "Line 1.5", "icon": "↕", "command_id": UiCommandId.LINE_SPACING, "payload": {"value": 1.5}},
        {"id": "line_2_0", "label": "Line 2.0", "icon": "↕", "command_id": UiCommandId.LINE_SPACING, "payload": {"value": 2.0}},
        {"id": "clear_format", "label": "ClearFmt", "icon": "CF", "command_id": UiCommandId.CLEAR_FORMATTING},
        {"id": "style_body", "label": "Body", "icon": "Bd", "command_id": UiCommandId.APPLY_TEXT_STYLE, "payload": {"value": "Body"}},
        {"id": "style_h1", "label": "Heading1", "icon": "H1", "command_id": UiCommandId.APPLY_TEXT_STYLE, "payload": {"value": "Heading 1"}},
        {"id": "style_h2", "label": "Heading2", "icon": "H2", "command_id": UiCommandId.APPLY_TEXT_STYLE, "payload": {"value": "Heading 2"}},
        {"id": "style_h3", "label": "Heading3", "icon": "H3", "command_id": UiCommandId.APPLY_TEXT_STYLE, "payload": {"value": "Heading 3"}},
        {"id": "font_apply", "label": "Apply Font", "icon": "Af", "command_id": UiCommandId.FONT_FAMILY, "payload_from": "font_family"},
        {"id": "size_apply", "label": "Apply Size", "icon": "As", "command_id": UiCommandId.FONT_SIZE, "payload_from": "font_size"},
        {"id": "font_inc", "label": "Size+", "icon": "A+", "command_id": UiCommandId.FONT_SIZE_INCREASE},
        {"id": "font_dec", "label": "Size-", "icon": "A-", "command_id": UiCommandId.FONT_SIZE_DECREASE},
        {"id": "insert_image", "label": "Image", "icon": "Img", "command_id": UiCommandId.INSERT_IMAGE},
        {"id": "insert_table", "label": "Table", "icon": "Tbl", "command_id": UiCommandId.INSERT_TABLE},
        {"id": "insert_checklist", "label": "Checklist", "icon": "Chk", "command_id": UiCommandId.INSERT_CHECKLIST},
        {"id": "insert_date", "label": "Date", "icon": "Dt", "command_id": UiCommandId.INSERT_DATE_TIME},
        {"id": "insert_symbol", "label": "Symbol", "icon": "Ω", "command_id": UiCommandId.INSERT_SYMBOL},
        {"id": "insert_rule", "label": "Rule", "icon": "—", "command_id": UiCommandId.INSERT_HORIZONTAL_LINE},
        {"id": "insert_page_break", "label": "PageBreak", "icon": "PB", "command_id": UiCommandId.INSERT_PAGE_BREAK},
        {"id": "memo_builder", "label": "Memo", "icon": "M", "command_id": UiCommandId.OPEN_MEMO_BUILDER},
        {"id": "action_hub", "label": "ActionHub", "icon": "AH", "command_id": UiCommandId.ACTION_HUB},
        {"id": "todo_export", "label": "ToDoRpt", "icon": "TD", "command_id": UiCommandId.EXPORT_TODO_REPORT},
        {"id": "spell_check", "label": "Spell", "icon": "✓", "command_id": UiCommandId.SPELL_CHECK},
        {"id": "dictionary", "label": "Dictionary", "icon": "ABC", "command_id": UiCommandId.DICTIONARY_LOOKUP},
        {"id": "wiki", "label": "Wiki", "icon": "W", "command_id": UiCommandId.WIKI_LOOKUP},
        {"id": "read_aloud", "label": "Read", "icon": "▶", "command_id": UiCommandId.READ_ALOUD},
        {"id": "stats", "label": "Stats", "icon": "#", "command_id": UiCommandId.SHOW_STATS},
        {"id": "theme", "label": "Theme", "icon": "◐", "command_id": UiCommandId.TOGGLE_THEME},
        {"id": "focus", "label": "Focus", "icon": "◱", "command_id": UiCommandId.TOGGLE_FOCUS},
        {"id": "sidebar", "label": "Sidebar", "icon": "SB", "command_id": UiCommandId.TOGGLE_SIDEBAR},
        {"id": "console", "label": "Console", "icon": ">_", "command_id": UiCommandId.TOGGLE_CONSOLE},
        {"id": "rulers", "label": "Rulers", "icon": "|", "command_id": UiCommandId.TOGGLE_RULERS},
        {"id": "zoom_in", "label": "Zoom+", "icon": "+", "command_id": UiCommandId.ZOOM_IN},
        {"id": "zoom_out", "label": "Zoom-", "icon": "-", "command_id": UiCommandId.ZOOM_OUT},
        {"id": "zoom_100", "label": "100%", "icon": "1:1", "command_id": UiCommandId.ZOOM_SET, "payload": {"value": 100}},
        {"id": "paper_color", "label": "Paper", "icon": "◻", "command_id": UiCommandId.PICK_PAPER_COLOR},
        {"id": "upload_font", "label": "Font+", "icon": "F+", "command_id": UiCommandId.UPLOAD_FONT},
        {"id": "set_logo", "label": "SetLogo", "icon": "Lg", "command_id": UiCommandId.SET_DEFAULT_LOGO},
        {"id": "clear_logo", "label": "ClrLogo", "icon": "xL", "command_id": UiCommandId.CLEAR_DEFAULT_LOGO},
        {"id": "nav_top", "label": "Doc Start", "icon": "Top", "command_id": UiCommandId.NAVIGATE_TO_INDEX, "payload": {"index": "1.0"}},
        {"id": "command_palette", "label": "Commands", "icon": "⌘", "command_id": UiCommandId.OPEN_COMMAND_PALETTE},
    ]

    FONT_FALLBACK_POOL = [
        "Arial",
        "Arial Black",
        "Arial Narrow",
        "Avenir",
        "Avenir Next",
        "Baskerville",
        "Bodoni 72",
        "Book Antiqua",
        "Bookman Old Style",
        "Calibri",
        "Cambria",
        "Candara",
        "Century",
        "Century Gothic",
        "Charter",
        "Comic Sans MS",
        "Consolas",
        "Copperplate",
        "Courier New",
        "Didot",
        "Futura",
        "Garamond",
        "Georgia",
        "Gill Sans",
        "Helvetica",
        "Helvetica Neue",
        "Hoefler Text",
        "Impact",
        "Lucida Bright",
        "Lucida Console",
        "Lucida Sans",
        "Menlo",
        "Monaco",
        "Noteworthy",
        "Optima",
        "Palatino",
        "Perpetua",
        "Rockwell",
        "Segoe UI",
        "Tahoma",
        "Times New Roman",
        "Trebuchet MS",
        "Verdana",
    ]

    FONT_SIZE_OPTIONS = [
        8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 60, 72
    ]

    def __init__(self, parent, colors):
        super().__init__(
            parent,
            bg=colors["bg_panel"],
            relief=tk.RAISED,
            bd=2,
            highlightthickness=1,
            highlightbackground=colors["border"],
        )
        self.colors = colors
        self._handler = None
        self._focus_active = False
        self._custom_font_families = []
        self._on_tools_changed = None
        self._on_icon_tools_changed = None
        self._on_export_layout = None
        self._on_import_layout = None
        self._on_reset_layout = None
        self._on_icon_bar_toggle = None
        self._on_command_bar_toggle = None
        self._tool_buttons = {}
        self._tool_vars = {}
        self._visible_tool_ids = list(self.DEFAULT_TOOL_IDS)
        self._icon_buttons = {}
        self._icon_vars = {}
        self._visible_icon_ids = self.default_icon_ids()
        self._icon_bar_visible = True
        self._command_bar_visible = True
        self._tool_layout_job = None
        self._last_col_count = 0
        self.focus_btn = None
        self.save_btn = None

        self._tool_specs = list(self.TOOL_SPECS)
        self._tool_index = {spec["id"]: spec for spec in self._tool_specs}
        self._icon_specs = list(self.ICON_COMMAND_SPECS)
        self._icon_index = {spec["id"]: spec for spec in self._icon_specs}

        self.grid_columnconfigure(1, weight=1)

        left = tk.Frame(self, bg=colors["bg_panel"])
        left.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=6)

        self.doc_title = tk.Label(
            left,
            text="Untitled",
            font=("Segoe UI", 13, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_primary"],
        )
        self.doc_title.pack(side=tk.LEFT, padx=(0, 8))

        self.dirty_indicator = tk.Label(
            left,
            text="Saved",
            font=("Segoe UI", 10, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
        )
        self.dirty_indicator.pack(side=tk.LEFT)

        center = tk.Frame(self, bg=colors["bg_panel"])
        center.grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        center.grid_columnconfigure(0, weight=1)
        center.grid_columnconfigure(1, weight=0)

        self.action_row = tk.Frame(center, bg=colors["bg_panel"])
        self.action_row.grid(row=0, column=0, sticky="ew")
        self.action_row.bind("<Configure>", self._on_action_row_configure, add="+")

        for spec in self._tool_specs:
            button = self._create_tool_button(self.action_row, spec)
            self._tool_buttons[spec["id"]] = button
            if spec["id"] == "save":
                self.save_btn = button
            if spec["id"] == "focus_mode":
                self.focus_btn = button

        controls = tk.Frame(center, bg=colors["bg_panel"])
        controls.grid(row=0, column=1, sticky="e", padx=(10, 0))

        self.toolbar_menu_btn = tk.Menubutton(
            controls,
            text="Toolbar ▾",
            font=("Segoe UI", 10, "bold"),
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
            padx=8,
            pady=4,
        )
        self.toolbar_menu_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.toolbar_menu = tk.Menu(self.toolbar_menu_btn, tearoff=False)
        self.toolbar_menu_btn.configure(menu=self.toolbar_menu)

        self.tool_items_menu = tk.Menu(self.toolbar_menu, tearoff=False)
        self.toolbar_menu.add_cascade(label="Command Toolbar Items", menu=self.tool_items_menu)

        for spec in self._tool_specs:
            tool_id = spec["id"]
            var = tk.BooleanVar(value=tool_id in self._visible_tool_ids)
            self._tool_vars[tool_id] = var
            label = f'{spec.get("icon", "")} {spec.get("label", "")}'.strip()
            self.tool_items_menu.add_checkbutton(
                label=label,
                variable=var,
                command=lambda tid=tool_id: self._toggle_tool_visibility_from_menu(tid),
            )
        self.tool_items_menu.add_separator()
        self.tool_items_menu.add_command(label="Show Default Tools", command=self._reset_to_default_tools)
        self.tool_items_menu.add_command(label="Show All Tools", command=self._show_all_tools)

        self.icon_items_menu = tk.Menu(self.toolbar_menu, tearoff=False)
        self.toolbar_menu.add_cascade(label="Icon Bar Items", menu=self.icon_items_menu)
        for spec in self._icon_specs:
            icon_id = spec["id"]
            var = tk.BooleanVar(value=icon_id in self._visible_icon_ids)
            self._icon_vars[icon_id] = var
            label = f'{spec.get("icon", "")} {spec.get("label", "")}'.strip()
            self.icon_items_menu.add_checkbutton(
                label=label,
                variable=var,
                command=lambda iid=icon_id: self._toggle_icon_visibility_from_menu(iid),
            )
        self.icon_items_menu.add_separator()
        self.icon_items_menu.add_command(label="Show All Icons", command=self._show_all_icons)
        self.icon_items_menu.add_command(label="Reset Icon Defaults", command=self._reset_to_default_icons)

        self.toolbar_menu.add_separator()
        self._icon_bar_visible_var = tk.BooleanVar(value=self._icon_bar_visible)
        self.toolbar_menu.add_checkbutton(
            label="Show Icon Bar",
            variable=self._icon_bar_visible_var,
            command=self._toggle_icon_bar_visibility_from_menu,
        )
        self._command_bar_visible_var = tk.BooleanVar(value=self._command_bar_visible)
        self.toolbar_menu.add_checkbutton(
            label="Show Command Bar",
            variable=self._command_bar_visible_var,
            command=self._toggle_command_bar_visibility_from_menu,
        )

        self.toolbar_menu.add_separator()
        self.toolbar_menu.add_command(label="Export Toolbar Layout...", command=self._export_toolbar_layout)
        self.toolbar_menu.add_command(label="Import Toolbar Layout...", command=self._import_toolbar_layout)

        tk.Label(
            controls,
            text="Font",
            font=("Segoe UI", 10, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
        ).pack(side=tk.LEFT, padx=(0, 6))

        families = self._build_font_catalog()
        self.font_box = ttk.Combobox(
            controls,
            values=families,
            width=18,
            state="readonly",
            style="App.TCombobox",
        )
        if "Calibri" in families:
            self.font_box.set("Calibri")
        elif families:
            self.font_box.set(families[0])
        self.font_box.pack(side=tk.LEFT)
        self.font_box.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._emit(UiCommandId.FONT_FAMILY, {"value": self.font_box.get()}),
        )

        self.font_size_box = ttk.Combobox(
            controls,
            values=self.FONT_SIZE_OPTIONS,
            width=5,
            state="readonly",
            style="App.TCombobox",
        )
        self.font_size_box.set("11")
        self.font_size_box.pack(side=tk.LEFT, padx=(6, 0))
        self.font_size_box.bind("<<ComboboxSelected>>", lambda _e: self._emit_font_size())

        align_controls = tk.Frame(controls, bg=colors["bg_panel"])
        align_controls.pack(side=tk.LEFT, padx=(8, 0))
        self.align_left_btn = self._create_utility_button(
            align_controls,
            "Left",
            lambda: self._emit(UiCommandId.ALIGN_LEFT),
            width=6,
        )
        self.align_left_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.align_center_btn = self._create_utility_button(
            align_controls,
            "Center",
            lambda: self._emit(UiCommandId.ALIGN_CENTER),
            width=7,
        )
        self.align_center_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.align_right_btn = self._create_utility_button(
            align_controls,
            "Right",
            lambda: self._emit(UiCommandId.ALIGN_RIGHT),
            width=6,
        )
        self.align_right_btn.pack(side=tk.LEFT, padx=(0, 0))

        self.upload_font_btn = tk.Button(
            controls,
            text="+ Font",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            padx=8,
            pady=4,
            command=lambda: self._emit(UiCommandId.UPLOAD_FONT),
        )
        self.upload_font_btn.pack(side=tk.LEFT, padx=(6, 0))

        right = tk.Frame(self, bg=colors["bg_panel"])
        right.grid(row=0, column=2, sticky="e", padx=(8, 12), pady=6)

        tk.Label(
            right,
            text="Search",
            font=("Segoe UI", 10, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.search_var = tk.StringVar(value="")
        self.search_entry = ttk.Entry(right, textvariable=self.search_var, width=30, style="App.TEntry")
        self.search_entry.pack(side=tk.LEFT)
        self.search_entry.bind("<KeyRelease>", self._on_search_keyrelease, add="+")
        self.search_entry.bind("<Return>", self._on_search_next, add="+")
        self.search_entry.bind("<Shift-Return>", self._on_search_prev, add="+")
        self.search_entry.bind("<Escape>", self._on_search_clear, add="+")

        self.icon_bar_host = tk.Frame(self, bg=colors["bg_panel"])
        self.icon_bar_host.grid(row=1, column=0, columnspan=3, sticky="ew", padx=(10, 10), pady=(0, 6))
        self.icon_bar_host.grid_columnconfigure(0, weight=1)

        self.icon_canvas = tk.Canvas(
            self.icon_bar_host,
            height=42,
            bg=colors["bg_panel"],
            highlightthickness=1,
            highlightbackground=colors["border"],
            bd=0,
        )
        self.icon_canvas.grid(row=0, column=0, sticky="ew")

        self.icon_scroll = tk.Scrollbar(self.icon_bar_host, orient=tk.HORIZONTAL, command=self.icon_canvas.xview)
        self.icon_scroll.grid(row=1, column=0, sticky="ew")
        self.icon_canvas.configure(xscrollcommand=self.icon_scroll.set)

        self.icon_row = tk.Frame(self.icon_canvas, bg=colors["bg_panel"])
        self.icon_canvas_window = self.icon_canvas.create_window((0, 0), window=self.icon_row, anchor="nw")
        self.icon_row.bind("<Configure>", self._sync_icon_scrollregion, add="+")
        self.icon_canvas.bind("<Configure>", self._sync_icon_scrollregion, add="+")

        for spec in self._icon_specs:
            button = self._create_icon_button(self.icon_row, spec)
            self._icon_buttons[spec["id"]] = button

        self.set_visible_tools(self._visible_tool_ids, notify=False)
        self.set_visible_icons(self._visible_icon_ids, notify=False)
        self._set_primary_button(self.save_btn)
        self.set_icon_bar_visible(self._icon_bar_visible, notify=False)
        self.set_command_bar_visible(self._command_bar_visible, notify=False)
        self._sync_toolbar_menu_theme()

    @classmethod
    def default_tool_ids(cls):
        return list(cls.DEFAULT_TOOL_IDS)

    @classmethod
    def default_icon_ids(cls):
        return [spec["id"] for spec in cls.ICON_COMMAND_SPECS]

    def bind_commands(self, handler):
        self._handler = handler

    def get_search_query(self):
        return str(self.search_var.get() or "")

    def set_search_query(self, value: str):
        self.search_var.set(str(value or ""))

    def bind_toolbar_layout_actions(
        self,
        on_tools_changed=None,
        on_icon_tools_changed=None,
        on_icon_bar_toggle=None,
        on_command_bar_toggle=None,
        on_export=None,
        on_import=None,
        on_reset=None,
    ):
        self._on_tools_changed = on_tools_changed
        self._on_icon_tools_changed = on_icon_tools_changed
        self._on_icon_bar_toggle = on_icon_bar_toggle
        self._on_command_bar_toggle = on_command_bar_toggle
        self._on_export_layout = on_export
        self._on_import_layout = on_import
        self._on_reset_layout = on_reset

    def get_available_tool_ids(self):
        return [spec["id"] for spec in self._tool_specs]

    def get_visible_tools(self):
        return list(self._visible_tool_ids)

    def get_available_icon_ids(self):
        return [spec["id"] for spec in self._icon_specs]

    def get_visible_icons(self):
        return list(self._visible_icon_ids)

    def is_icon_bar_visible(self):
        return bool(self._icon_bar_visible)

    def is_command_bar_visible(self):
        return bool(self._command_bar_visible)

    def set_visible_tools(self, tool_ids, notify=False):
        cleaned = []
        seen = set()
        available = set(self.get_available_tool_ids())
        for value in tool_ids if isinstance(tool_ids, (list, tuple, set)) else []:
            tool_id = str(value or "").strip()
            if not tool_id or tool_id not in available or tool_id in seen:
                continue
            seen.add(tool_id)
            cleaned.append(tool_id)

        if not cleaned:
            cleaned = list(self.DEFAULT_TOOL_IDS)

        self._visible_tool_ids = cleaned
        for tool_id, var in self._tool_vars.items():
            var.set(tool_id in self._visible_tool_ids)
        self._schedule_tool_layout()

        if notify and callable(self._on_tools_changed):
            self._on_tools_changed(list(self._visible_tool_ids))

    def set_visible_icons(self, icon_ids, notify=False):
        cleaned = []
        seen = set()
        available = set(self.get_available_icon_ids())
        for value in icon_ids if isinstance(icon_ids, (list, tuple, set)) else []:
            icon_id = str(value or "").strip()
            if not icon_id or icon_id not in available or icon_id in seen:
                continue
            seen.add(icon_id)
            cleaned.append(icon_id)

        self._visible_icon_ids = cleaned
        for icon_id, var in self._icon_vars.items():
            var.set(icon_id in self._visible_icon_ids)
        self._layout_icons()

        if notify and callable(self._on_icon_tools_changed):
            self._on_icon_tools_changed(list(self._visible_icon_ids))

    def set_icon_bar_visible(self, visible: bool, notify=False):
        self._icon_bar_visible = bool(visible)
        if hasattr(self, "_icon_bar_visible_var"):
            self._icon_bar_visible_var.set(self._icon_bar_visible)
        if self._icon_bar_visible:
            self.icon_bar_host.grid()
        else:
            self.icon_bar_host.grid_remove()

        if notify and callable(self._on_icon_bar_toggle):
            self._on_icon_bar_toggle(self._icon_bar_visible)

    def set_command_bar_visible(self, visible: bool, notify=False):
        self._command_bar_visible = bool(visible)
        if hasattr(self, "_command_bar_visible_var"):
            self._command_bar_visible_var.set(self._command_bar_visible)
        if notify and callable(self._on_command_bar_toggle):
            self._on_command_bar_toggle(self._command_bar_visible)

    def set_custom_fonts(self, families):
        values = []
        if isinstance(families, (list, tuple, set)):
            seen = set()
            for item in families:
                name = str(item or "").strip()
                if not name:
                    continue
                key = name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                values.append(name)
        self._custom_font_families = values

        current = str(self.font_box.get() or "").strip()
        catalog = self._build_font_catalog()
        self.font_box.configure(values=catalog)
        if current and current in catalog:
            self.font_box.set(current)
        elif "Calibri" in catalog:
            self.font_box.set("Calibri")
        elif catalog:
            self.font_box.set(catalog[0])

    def set_document(self, title: str, dirty: bool):
        self.doc_title.config(text=title or "Untitled")
        if dirty:
            self.dirty_indicator.config(text="Unsaved changes", fg=self.colors["danger"])
        else:
            self.dirty_indicator.config(text="Saved", fg=self.colors["text_secondary"])

    def set_focus_mode(self, enabled: bool):
        self._focus_active = bool(enabled)
        if not self.focus_btn:
            return
        if self._focus_active:
            self.focus_btn.config(
                text="◱ Exit Focus",
                bg=self.colors["accent"],
                fg="#FFFFFF",
                activebackground=self.colors["accent_hover"],
                activeforeground="#FFFFFF",
                relief=tk.SUNKEN,
            )
        else:
            self.focus_btn.config(
                text="◱ Focus Mode",
                bg=self.colors["bg_surface_alt"],
                fg=self.colors["text_primary"],
                activebackground=self.colors["accent_hover"],
                activeforeground="#FFFFFF",
                relief=tk.RAISED,
            )

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["bg_panel"], highlightbackground=colors["border"])
        for widget in self.winfo_children():
            self._update_theme_recursive(widget)
        self._set_primary_button(self.save_btn)
        self.set_focus_mode(self._focus_active)
        self.icon_canvas.config(bg=colors["bg_panel"], highlightbackground=colors["border"])
        self.icon_row.config(bg=colors["bg_panel"])
        self.icon_scroll.config(
            bg=colors["bg_panel"],
            troughcolor=colors["bg_surface"],
            activebackground=colors["accent"],
        )
        self._sync_toolbar_menu_theme()

    def _update_theme_recursive(self, widget):
        if isinstance(widget, tk.Frame):
            widget.config(bg=self.colors["bg_panel"])
        elif isinstance(widget, tk.Label):
            fg = self.colors["text_primary"] if widget is self.doc_title else self.colors["text_secondary"]
            widget.config(bg=self.colors["bg_panel"], fg=fg)
        elif isinstance(widget, (tk.Button, tk.Menubutton)):
            self._set_default_button(widget)
        for child in widget.winfo_children():
            self._update_theme_recursive(child)

    def _sync_toolbar_menu_theme(self):
        menus = [getattr(self, "toolbar_menu", None), getattr(self, "tool_items_menu", None), getattr(self, "icon_items_menu", None)]
        for menu in menus:
            if not menu:
                continue
            try:
                menu.config(
                    bg=self.colors["bg_surface"],
                    fg=self.colors["text_primary"],
                    activebackground=self.colors["accent_hover"],
                    activeforeground="#FFFFFF",
                )
            except Exception:
                continue

    def _emit(self, command_id: str, payload=None):
        if self._handler:
            self._handler(UiCommandRequest(command_id=command_id, payload=payload))

    def _on_search_keyrelease(self, event=None):
        keysym = str(getattr(event, "keysym", ""))
        if keysym in {"Return", "Shift_L", "Shift_R", "Escape"}:
            return
        self._emit(UiCommandId.DOCUMENT_SEARCH, {"query": self.get_search_query()})

    def _on_search_next(self, _event=None):
        state = int(getattr(_event, "state", 0) or 0)
        if state & 0x0001:
            return "break"
        self._emit(UiCommandId.DOCUMENT_SEARCH_NEXT, {"query": self.get_search_query()})
        return "break"

    def _on_search_prev(self, _event=None):
        self._emit(UiCommandId.DOCUMENT_SEARCH_PREV, {"query": self.get_search_query()})
        return "break"

    def _on_search_clear(self, _event=None):
        self.set_search_query("")
        self._emit(UiCommandId.DOCUMENT_SEARCH_CLEAR, {"query": ""})
        return "break"

    def _emit_font_size(self):
        try:
            value = int(float(self.font_size_box.get()))
        except Exception:
            return
        self._emit(UiCommandId.FONT_SIZE, {"value": value})

    def _create_utility_button(self, parent, text: str, command, width=None):
        button = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            padx=6,
            pady=4,
            command=command,
            width=width,
        )
        self._set_default_button(button)
        return button

    def _create_icon_button(self, parent, spec: dict):
        icon = str(spec.get("icon", "")).strip()
        label = str(spec.get("label", "")).strip()
        text = f"{icon} {label}".strip()
        button = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 8, "bold"),
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=1,
            cursor="hand2",
            padx=6,
            pady=3,
            width=11,
            command=lambda item=dict(spec): self._emit_icon_command(item),
        )
        self._set_default_button(button)
        return button

    def _emit_icon_command(self, spec: dict):
        command_id = str(spec.get("command_id", "")).strip()
        if not command_id:
            return

        payload = spec.get("payload")
        payload_data = dict(payload) if isinstance(payload, dict) else None
        payload_from = str(spec.get("payload_from", "")).strip()
        if payload_from == "search_query":
            payload_data = {"query": self.get_search_query()}
        elif payload_from == "font_family":
            value = str(self.font_box.get() if hasattr(self, "font_box") else "").strip()
            if not value:
                return
            payload_data = {"value": value}
        elif payload_from == "font_size":
            raw = str(self.font_size_box.get() if hasattr(self, "font_size_box") else "").strip()
            if not raw:
                return
            try:
                value = int(float(raw))
            except (TypeError, ValueError):
                return
            payload_data = {"value": value}

        self._emit(command_id, payload_data)

    def _tool_button_label(self, spec: dict):
        icon = str(spec.get("icon", "")).strip()
        label = str(spec.get("label", "")).strip()
        return f"{icon} {label}".strip()

    def _create_tool_button(self, parent, spec: dict):
        label = self._tool_button_label(spec)
        button = tk.Button(
            parent,
            text=label,
            font=("Segoe UI", 10, "bold"),
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=2,
            overrelief=tk.GROOVE,
            cursor="hand2",
            padx=8,
            pady=6,
            anchor="center",
            command=lambda cid=str(spec.get("command_id")): self._emit(cid),
        )
        if bool(spec.get("primary", False)):
            self._set_primary_button(button)
        else:
            self._set_default_button(button)
        return button

    def _set_default_button(self, button):
        if not button:
            return
        button.config(
            bg=self.colors["bg_surface_alt"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
        )

    def _set_primary_button(self, button):
        if not button:
            return
        button.config(
            bg=self.colors["accent"],
            fg="#FFFFFF",
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
        )

    def _on_action_row_configure(self, _event=None):
        self._schedule_tool_layout()

    def _schedule_tool_layout(self):
        if self._tool_layout_job is not None:
            return
        self._tool_layout_job = self.after_idle(self._layout_tools)

    def _layout_tools(self):
        self._tool_layout_job = None
        width = max(320, int(self.action_row.winfo_width() or 0))
        visible_ids = [tool_id for tool_id in self._visible_tool_ids if tool_id in self._tool_buttons]
        if not visible_ids:
            return

        min_button_width = 124
        columns = max(1, width // min_button_width)
        columns = min(columns, len(visible_ids))

        max_cols = max(self._last_col_count, columns)
        for col in range(max_cols):
            self.action_row.grid_columnconfigure(col, weight=0, uniform="")

        for button in self._tool_buttons.values():
            button.grid_forget()

        for index, tool_id in enumerate(visible_ids):
            row = index // columns
            col = index % columns
            button = self._tool_buttons[tool_id]
            button.grid(row=row, column=col, sticky="ew", padx=(0, 6), pady=(0, 6))

        for col in range(columns):
            self.action_row.grid_columnconfigure(col, weight=1, uniform="top_strip_toolbar")

        self._last_col_count = columns
        self._set_primary_button(self.save_btn)
        self.set_focus_mode(self._focus_active)
        self._layout_icons()

    def _layout_icons(self):
        for button in self._icon_buttons.values():
            button.pack_forget()
        for icon_id in self._visible_icon_ids:
            button = self._icon_buttons.get(icon_id)
            if not button:
                continue
            button.pack(side=tk.LEFT, padx=(0, 4), pady=(4, 2))
        self._sync_icon_scrollregion()

    def _sync_icon_scrollregion(self, _event=None):
        try:
            bounds = self.icon_canvas.bbox("all")
            if bounds:
                self.icon_canvas.configure(scrollregion=bounds)
            else:
                self.icon_canvas.configure(scrollregion=(0, 0, 0, 0))
        except Exception:
            pass

    def _toggle_tool_visibility_from_menu(self, tool_id: str):
        var = self._tool_vars.get(tool_id)
        if var is None:
            return
        visible = bool(var.get())
        current = list(self._visible_tool_ids)
        if visible:
            if tool_id not in current:
                current.append(tool_id)
        else:
            current = [value for value in current if value != tool_id]

        if not current:
            var.set(True)
            return

        self.set_visible_tools(current, notify=True)

    def _toggle_icon_visibility_from_menu(self, icon_id: str):
        var = self._icon_vars.get(icon_id)
        if var is None:
            return
        visible = bool(var.get())
        current = list(self._visible_icon_ids)
        if visible:
            if icon_id not in current:
                current.append(icon_id)
        else:
            current = [value for value in current if value != icon_id]
        self.set_visible_icons(current, notify=True)

    def _show_all_icons(self):
        self.set_visible_icons(self.get_available_icon_ids(), notify=True)

    def _reset_to_default_icons(self):
        self.set_visible_icons(self.default_icon_ids(), notify=True)

    def _toggle_icon_bar_visibility_from_menu(self):
        self.set_icon_bar_visible(bool(self._icon_bar_visible_var.get()), notify=True)

    def _toggle_command_bar_visibility_from_menu(self):
        self.set_command_bar_visible(bool(self._command_bar_visible_var.get()), notify=True)

    def _show_all_tools(self):
        self.set_visible_tools(self.get_available_tool_ids(), notify=True)

    def _reset_to_default_tools(self):
        self.set_visible_tools(self.DEFAULT_TOOL_IDS, notify=True)
        if callable(self._on_reset_layout):
            self._on_reset_layout()

    def _export_toolbar_layout(self):
        if callable(self._on_export_layout):
            self._on_export_layout()

    def _import_toolbar_layout(self):
        if callable(self._on_import_layout):
            self._on_import_layout()

    def _build_font_catalog(self):
        values = []
        seen = set()

        def _add(name: str):
            value = str(name or "").strip()
            if not value:
                return
            key = value.casefold()
            if key in seen:
                return
            seen.add(key)
            values.append(value)

        for name in self._custom_font_families:
            _add(name)

        installed = []
        try:
            installed = sorted(set(tkfont.families()))
        except Exception:
            installed = []
        for name in installed:
            _add(name)

        for name in self.FONT_FALLBACK_POOL:
            _add(name)
        return values
