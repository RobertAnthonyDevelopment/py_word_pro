import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

from src.ui.contracts import UiCommandId, UiCommandRequest


class CommandBar(tk.Frame):
    TEXT_STYLE_PRESETS = [
        "Body",
        "Title",
        "Subtitle",
        "Heading 1",
        "Heading 2",
        "Heading 3",
        "Quote",
        "Code",
        "Caption",
    ]

    FONT_SIZE_OPTIONS = [
        6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 20, 22, 24, 26, 28,
        30, 32, 36, 40, 44, 48, 54, 60, 66, 72, 80, 88, 96,
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
        self._tab_layouts = {}
        self._custom_font_families = []

        self.surface = tk.Frame(self, bg=colors["bg_panel"], bd=2, relief=tk.GROOVE)
        self.surface.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        self.notebook = ttk.Notebook(self.surface, style="App.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        self._build_home_tab()
        self._build_insert_tab()
        self._build_review_tab()
        self._build_view_tab()

    def bind_commands(self, handler):
        self._handler = handler

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["bg_panel"], highlightbackground=colors["border"])
        self.surface.config(bg=colors["bg_panel"])
        for tab in self.notebook.winfo_children():
            self._update_theme_recursive(tab)

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
        if hasattr(self, "font_box"):
            current = str(self.font_box.get() or "").strip()
            catalog = self._build_font_catalog()
            self.font_box.configure(values=catalog)
            if current and current in catalog:
                self.font_box.set(current)
            elif "Calibri" in catalog:
                self.font_box.set("Calibri")
            elif catalog:
                self.font_box.set(catalog[0])

    def _build_home_tab(self):
        tab = self._create_responsive_tab("Home")

        self._group(tab, "File", (
            ("Open", UiCommandId.OPEN),
            ("Save", UiCommandId.SAVE),
            ("Save Template", UiCommandId.SAVE_AS_TEMPLATE),
            ("Export PDF", UiCommandId.EXPORT_PDF),
        ), columns=2)
        self._group(tab, "Clipboard", (
            ("Cut", UiCommandId.CUT),
            ("Copy", UiCommandId.COPY),
            ("Paste", UiCommandId.PASTE),
            ("Paste Text", UiCommandId.PASTE_PLAIN),
            ("Delete", UiCommandId.DELETE_SELECTION),
        ), columns=2)
        self._group(tab, "Edit", (
            ("Undo", UiCommandId.UNDO),
            ("Redo", UiCommandId.REDO),
            ("Find/Replace", UiCommandId.FIND_REPLACE),
            ("Select All", UiCommandId.SELECT_ALL),
        ), columns=2)
        self._group(tab, "Writing Tools", (
            ("Duplicate", UiCommandId.DUPLICATE_SELECTION),
            ("Sort A-Z", UiCommandId.SORT_LINES_ASC),
            ("Sort Z-A", UiCommandId.SORT_LINES_DESC),
            ("Trim Spaces", UiCommandId.TRIM_TRAILING_SPACES),
        ), columns=2)
        self._group(tab, "Case", (
            ("UPPERCASE", UiCommandId.CHANGE_CASE_UPPER),
            ("lowercase", UiCommandId.CHANGE_CASE_LOWER),
            ("Title Case", UiCommandId.CHANGE_CASE_TITLE),
            ("Sentence case", UiCommandId.CHANGE_CASE_SENTENCE),
        ), columns=2)
        self._group(tab, "Proofing", (
            ("Spell Check", UiCommandId.SPELL_CHECK),
            ("Dictionary", UiCommandId.DICTIONARY_LOOKUP),
            ("Read Aloud", UiCommandId.READ_ALOUD),
        ), columns=1)

        font_group = self._group_container(tab, "Font", preferred_width=680)
        style_row = tk.Frame(font_group, bg=self.colors["bg_panel"])
        style_row.pack(fill=tk.X)
        tk.Label(
            style_row,
            text="Style",
            bg=self.colors["bg_panel"],
            fg=self.colors["text_secondary"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.style_box = ttk.Combobox(
            style_row,
            values=self.TEXT_STYLE_PRESETS,
            width=16,
            state="readonly",
            style="App.TCombobox",
        )
        self.style_box.set("Body")
        self.style_box.pack(side=tk.LEFT, padx=(0, 8))
        self.style_box.bind("<<ComboboxSelected>>", lambda _e: self._emit_text_style())

        style_buttons = tk.Frame(style_row, bg=self.colors["bg_panel"])
        style_buttons.pack(side=tk.LEFT)
        tk.Button(
            style_buttons,
            text="H1",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["bg_surface_alt"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=2,
            overrelief=tk.GROOVE,
            cursor="hand2",
            padx=6,
            pady=3,
            command=lambda: self._emit(UiCommandId.APPLY_TEXT_STYLE, {"value": "Heading 1"}),
            width=4,
        ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(
            style_buttons,
            text="H2",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["bg_surface_alt"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=2,
            overrelief=tk.GROOVE,
            cursor="hand2",
            padx=6,
            pady=3,
            command=lambda: self._emit(UiCommandId.APPLY_TEXT_STYLE, {"value": "Heading 2"}),
            width=4,
        ).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(
            style_buttons,
            text="Body",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["bg_surface_alt"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=2,
            overrelief=tk.GROOVE,
            cursor="hand2",
            padx=6,
            pady=3,
            command=lambda: self._emit(UiCommandId.APPLY_TEXT_STYLE, {"value": "Body"}),
            width=5,
        ).pack(side=tk.LEFT, padx=(0, 4))

        top = tk.Frame(font_group, bg=self.colors["bg_panel"])
        top.pack(fill=tk.X, pady=(6, 0))
        families = self._build_font_catalog()
        self.font_box = ttk.Combobox(top, values=families, width=22, state="readonly", style="App.TCombobox")
        if "Calibri" in families:
            self.font_box.set("Calibri")
        elif families:
            self.font_box.set(families[0])
        self.font_box.pack(side=tk.LEFT, padx=(0, 6))
        self.font_box.bind("<<ComboboxSelected>>", lambda _e: self._emit(UiCommandId.FONT_FAMILY, {"value": self.font_box.get()}))

        self.size_box = ttk.Combobox(
            top,
            values=self.FONT_SIZE_OPTIONS,
            width=6,
            state="readonly",
            style="App.TCombobox",
        )
        self.size_box.set(11)
        self.size_box.pack(side=tk.LEFT)
        self.size_box.bind("<<ComboboxSelected>>", lambda _e: self._emit_font_size())

        tk.Button(
            top,
            text="A-",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["bg_surface_alt"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=2,
            overrelief=tk.GROOVE,
            cursor="hand2",
            padx=4,
            pady=3,
            command=lambda: self._emit(UiCommandId.FONT_SIZE_DECREASE),
            width=4,
        ).pack(side=tk.LEFT, padx=(6, 2))
        tk.Button(
            top,
            text="A+",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["bg_surface_alt"],
            fg=self.colors["text_primary"],
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=2,
            overrelief=tk.GROOVE,
            cursor="hand2",
            padx=4,
            pady=3,
            command=lambda: self._emit(UiCommandId.FONT_SIZE_INCREASE),
            width=4,
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.upload_font_btn = self._button(top, "Upload Font", UiCommandId.UPLOAD_FONT, width=12)
        self.upload_font_btn.pack(side=tk.LEFT, padx=(8, 0))

        bottom = tk.Frame(font_group, bg=self.colors["bg_panel"])
        bottom.pack(fill=tk.X, pady=(6, 0))
        self._button_grid(
            bottom,
            [
                ("Bold", UiCommandId.BOLD),
                ("Italic", UiCommandId.ITALIC),
                ("Underline", UiCommandId.UNDERLINE),
                ("Strike", UiCommandId.STRIKE),
                ("Text Color", UiCommandId.TEXT_COLOR),
                ("Highlight", UiCommandId.HIGHLIGHT),
            ],
            columns=3,
        )

        paragraph = self._group_container(tab, "Paragraph", preferred_width=520)
        row = tk.Frame(paragraph, bg=self.colors["bg_panel"])
        row.pack(fill=tk.X)
        self._button_grid(
            row,
            [
                ("Align Left", UiCommandId.ALIGN_LEFT),
                ("Center", UiCommandId.ALIGN_CENTER),
                ("Align Right", UiCommandId.ALIGN_RIGHT),
                ("Bullets", UiCommandId.BULLET_LIST),
                ("Numbering", UiCommandId.NUMBERED_LIST),
                ("Clear Formatting", UiCommandId.CLEAR_FORMATTING),
            ],
            columns=3,
        )

        spacing_row = tk.Frame(paragraph, bg=self.colors["bg_panel"])
        spacing_row.pack(fill=tk.X, pady=(4, 0))
        tk.Label(spacing_row, text="Line Spacing", bg=self.colors["bg_panel"], fg=self.colors["text_secondary"], font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        self.spacing_box = ttk.Combobox(
            spacing_row,
            values=["1.0", "1.15", "1.25", "1.5", "1.75", "2.0", "2.5", "3.0"],
            width=8,
            state="readonly",
            style="App.TCombobox",
        )
        self.spacing_box.set("1.0")
        self.spacing_box.pack(side=tk.LEFT)
        self.spacing_box.bind("<<ComboboxSelected>>", lambda _e: self._emit_line_spacing())

    def _build_insert_tab(self):
        tab = self._create_responsive_tab("Insert")

        self._group(tab, "Start", (
            ("Templates", UiCommandId.NEW_FROM_TEMPLATE),
            ("Save Template", UiCommandId.SAVE_AS_TEMPLATE),
        ), columns=1)
        self._group(tab, "Media", (
            ("Image", UiCommandId.INSERT_IMAGE),
            ("Horizontal Line", UiCommandId.INSERT_HORIZONTAL_LINE),
        ), columns=1)
        self._group(tab, "Text", (
            ("Date and Time", UiCommandId.INSERT_DATE_TIME),
            ("Symbols", UiCommandId.INSERT_SYMBOL),
            ("Find and Replace", UiCommandId.FIND_REPLACE),
        ), columns=1)
        self._group(tab, "Structures", (
            ("Insert Table", UiCommandId.INSERT_TABLE),
            ("Insert Checklist", UiCommandId.INSERT_CHECKLIST),
            ("Page Break", UiCommandId.INSERT_PAGE_BREAK),
        ), columns=1)
        self._group(tab, "Business", (
            ("Memo Builder", UiCommandId.OPEN_MEMO_BUILDER),
            ("Action Hub", UiCommandId.ACTION_HUB),
            ("Export To-Do", UiCommandId.EXPORT_TODO_REPORT),
        ), columns=1)

    def _build_review_tab(self):
        tab = self._create_responsive_tab("Review")
        self._group(tab, "Proofing", (
            ("Spell Check", UiCommandId.SPELL_CHECK),
            ("Dictionary", UiCommandId.DICTIONARY_LOOKUP),
            ("Wiki Lookup", UiCommandId.WIKI_LOOKUP),
            ("Read Aloud", UiCommandId.READ_ALOUD),
        ), columns=1)
        self._group(tab, "Insights", (
            ("Document Stats", UiCommandId.SHOW_STATS),
            ("Action Hub", UiCommandId.ACTION_HUB),
            ("Export To-Do", UiCommandId.EXPORT_TODO_REPORT),
        ), columns=1)

    def _build_view_tab(self):
        tab = self._create_responsive_tab("View")
        self._group(tab, "Window", (
            ("Command Palette", UiCommandId.OPEN_COMMAND_PALETTE),
            ("Toggle Theme", UiCommandId.TOGGLE_THEME),
            ("Focus Mode", UiCommandId.TOGGLE_FOCUS),
            ("Toggle Sidebar", UiCommandId.TOGGLE_SIDEBAR),
            ("Toggle Console", UiCommandId.TOGGLE_CONSOLE),
            ("Toggle Rulers", UiCommandId.TOGGLE_RULERS),
        ), columns=1)
        self._group(tab, "Zoom", (
            ("Zoom In", UiCommandId.ZOOM_IN),
            ("Zoom Out", UiCommandId.ZOOM_OUT),
        ), columns=1)
        self._group(tab, "Page", (
            ("Paper Color", UiCommandId.PICK_PAPER_COLOR),
        ), columns=1)
        self._group(tab, "Brand", (
            ("Set Logo", UiCommandId.SET_DEFAULT_LOGO),
            ("Clear Logo", UiCommandId.CLEAR_DEFAULT_LOGO),
        ), columns=1)

    def _group(self, parent, title, items, columns=2, preferred_width=280):
        frame = self._group_container(parent, title, preferred_width=preferred_width)
        body = tk.Frame(frame, bg=self.colors["bg_panel"])
        body.pack(fill=tk.BOTH, expand=True, pady=1)
        self._button_grid(body, items, columns=max(1, int(columns)))

    def _create_responsive_tab(self, title: str):
        host = tk.Frame(self.notebook, bg=self.colors["bg_panel"])
        self.notebook.add(host, text=f" {title} ")
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(
            host,
            bg=self.colors["bg_panel"],
            highlightthickness=0,
            bd=0,
        )
        canvas.grid(row=0, column=0, sticky="nsew")

        scroll = tk.Scrollbar(host, orient=tk.VERTICAL, command=canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scroll.set)

        body = tk.Frame(canvas, bg=self.colors["bg_panel"])
        rows = tk.Frame(body, bg=self.colors["bg_panel"])
        rows.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _sync_scrollregion(_event=None, c=canvas):
            bounds = c.bbox("all")
            if not bounds:
                return
            c.configure(scrollregion=bounds)

        def _sync_body_width(event, c=canvas, item=window_id, b=body):
            width = max(1, int(getattr(event, "width", c.winfo_width())) - 2)
            tab = self._tab_layouts.get(id(b))
            if tab and tab.get("last_canvas_width") == width:
                return
            if tab:
                tab["last_canvas_width"] = width
            c.itemconfigure(item, width=width)
            self._schedule_relayout(b)

        body.bind("<Configure>", _sync_scrollregion, add="+")
        canvas.bind("<Configure>", _sync_body_width, add="+")
        self._tab_layouts[id(body)] = {
            "canvas": canvas,
            "scroll": scroll,
            "body": body,
            "rows": rows,
            "groups": [],
            "relayout_job": None,
            "last_canvas_width": None,
        }
        self._schedule_relayout(body)
        return body

    def _group_container(self, parent, title, preferred_width=280):
        frame = tk.LabelFrame(
            parent,
            text=title,
            bg=self.colors["bg_panel"],
            fg=self.colors["text_secondary"],
            bd=2,
            relief=tk.RIDGE,
            font=("Segoe UI", 10, "bold"),
            padx=8,
            pady=8,
        )
        self._register_group_frame(parent, frame, preferred_width)
        return frame

    def _register_group_frame(self, parent, frame, preferred_width=280):
        tab = self._tab_layouts.get(id(parent))
        if not tab:
            return
        tab["groups"].append((frame, max(180, int(preferred_width))))
        self._schedule_relayout(parent)

    def _schedule_relayout(self, body):
        tab = self._tab_layouts.get(id(body))
        if not tab:
            return
        if tab.get("relayout_job") is not None:
            return
        tab["relayout_job"] = self.after_idle(lambda b=body: self._relayout_groups(b))

    def _relayout_groups(self, body):
        tab = self._tab_layouts.get(id(body))
        if not tab:
            return
        tab["relayout_job"] = None
        rows_container = tab["rows"]
        groups = tab["groups"]
        canvas = tab["canvas"]
        if not groups:
            return

        width = max(240, int(canvas.winfo_width()) - 16)

        for child in rows_container.winfo_children():
            child.destroy()

        row_frame = tk.Frame(rows_container, bg=self.colors["bg_panel"])
        row_frame.pack(fill=tk.X, anchor="n")
        used = 0
        row_has_items = False

        for frame, preferred in groups:
            estimated = max(180, int(preferred)) + 12
            if row_has_items and (used + estimated) > width:
                row_frame = tk.Frame(rows_container, bg=self.colors["bg_panel"])
                row_frame.pack(fill=tk.X, anchor="n")
                used = 0
                row_has_items = False

            frame.pack_forget()
            frame.grid_forget()
            frame.pack(in_=row_frame, side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4, anchor="n")
            used += estimated
            row_has_items = True

    def _button(self, parent, label, command_id, width=None):
        options = {
            "text": label,
            "font": ("Segoe UI", 10, "bold"),
            "bg": self.colors["bg_surface_alt"],
            "fg": self.colors["text_primary"],
            "activebackground": self.colors["accent_hover"],
            "activeforeground": "#FFFFFF",
            "relief": tk.RAISED,
            "bd": 2,
            "overrelief": tk.GROOVE,
            "cursor": "hand2",
            "padx": 8,
            "pady": 5,
            "command": lambda cid=command_id: self._emit(cid),
        }
        if width is not None:
            options["width"] = width
        return tk.Button(parent, **options)

    def _button_grid(self, parent, items, columns=2):
        cols = max(1, int(columns))
        for idx in range(cols):
            parent.grid_columnconfigure(idx, weight=1, uniform=f"group_{id(parent)}")
        for index, (label, command_id) in enumerate(items):
            row = index // cols
            column = index % cols
            button = self._button(parent, label, command_id)
            button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)

    def _update_theme_recursive(self, widget):
        if isinstance(widget, tk.LabelFrame):
            widget.config(bg=self.colors["bg_panel"], fg=self.colors["text_secondary"])
        elif isinstance(widget, tk.Frame):
            widget.config(bg=self.colors["bg_panel"])
        elif isinstance(widget, tk.Canvas):
            widget.config(bg=self.colors["bg_panel"])
        elif isinstance(widget, tk.Scrollbar):
            widget.config(
                bg=self.colors["bg_panel"],
                troughcolor=self.colors["bg_surface"],
                activebackground=self.colors["accent"],
            )
        elif isinstance(widget, tk.Label):
            widget.config(bg=self.colors["bg_panel"], fg=self.colors["text_secondary"])
        elif isinstance(widget, tk.Button):
            widget.config(
                bg=self.colors["bg_surface_alt"],
                fg=self.colors["text_primary"],
                activebackground=self.colors["accent_hover"],
                activeforeground="#FFFFFF",
            )
        for child in widget.winfo_children():
            self._update_theme_recursive(child)

    def _emit(self, command_id: str, payload=None):
        if self._handler:
            self._handler(UiCommandRequest(command_id=command_id, payload=payload))

    def _emit_font_size(self):
        try:
            value = int(float(self.size_box.get()))
        except Exception:
            return
        self._emit(UiCommandId.FONT_SIZE, {"value": value})

    def _emit_line_spacing(self):
        try:
            value = float(self.spacing_box.get())
        except Exception:
            return
        self._emit(UiCommandId.LINE_SPACING, {"value": value})

    def _emit_text_style(self):
        value = str(self.style_box.get() if hasattr(self, "style_box") else "").strip()
        if not value:
            return
        self._emit(UiCommandId.APPLY_TEXT_STYLE, {"value": value})

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
