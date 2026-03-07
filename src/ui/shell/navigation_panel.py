import tkinter as tk
from tkinter import ttk

from src.ui.contracts import UiCommandId, UiCommandRequest


class NavigationPanel(tk.Frame):
    def __init__(self, parent, colors, width=264):
        panel_width = max(220, int(width))
        super().__init__(
            parent,
            bg=colors["bg_panel"],
            width=panel_width,
            relief=tk.RAISED,
            bd=4,
            highlightthickness=1,
            highlightbackground=colors["border"],
        )
        self.colors = colors
        self._handler = None
        self.pack_propagate(False)

        self.inner = tk.Frame(self, bg=colors["bg_panel"])
        self.inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)

        header = tk.Frame(self.inner, bg=colors["bg_panel"])
        header.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            header,
            text="Navigation",
            font=("Segoe UI", 13, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_primary"],
        ).pack(side=tk.LEFT)

        quick_section = tk.LabelFrame(
            self.inner,
            text="Quick actions",
            font=("Segoe UI", 10, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
            bd=2,
            relief=tk.GROOVE,
            padx=10,
            pady=8,
        )
        quick_section.pack(fill=tk.X, pady=(0, 12))

        quick_row = tk.Frame(quick_section, bg=colors["bg_panel"])
        quick_row.pack(fill=tk.X)
        quick_row.grid_columnconfigure(0, weight=1)
        quick_row.grid_columnconfigure(1, weight=1)
        quick_row.grid_columnconfigure(2, weight=1)

        self.quick_open_btn = self._quick_button(quick_row, "Open", lambda: self._emit(UiCommandId.OPEN))
        self.quick_open_btn.grid(row=0, column=0, sticky="ew", padx=3)

        self.quick_template_btn = self._quick_button(quick_row, "Template", lambda: self._emit(UiCommandId.NEW_FROM_TEMPLATE))
        self.quick_template_btn.grid(row=0, column=1, sticky="ew", padx=3)

        self.quick_save_btn = self._quick_button(
            quick_row,
            "Save",
            lambda: self._emit(UiCommandId.SAVE),
            primary=True,
        )
        self.quick_save_btn.grid(row=0, column=2, sticky="ew", padx=3)

        recent_section = tk.LabelFrame(
            self.inner,
            text="Recent files",
            font=("Segoe UI", 10, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
            bd=2,
            relief=tk.GROOVE,
            padx=10,
            pady=8,
        )
        recent_section.pack(fill=tk.X, pady=(0, 12))

        recents_body = tk.Frame(recent_section, bg=colors["bg_panel"])
        recents_body.pack(fill=tk.X)
        recents_body.grid_columnconfigure(0, weight=1)

        self.recent_var = tk.StringVar(value="")
        self.recent_box = ttk.Combobox(
            recents_body,
            textvariable=self.recent_var,
            state="readonly",
            style="App.TCombobox",
        )
        self.recent_box.grid(row=0, column=0, sticky="ew")
        self.recent_box.bind("<<ComboboxSelected>>", self._open_selected_recent)

        self.open_recent_btn = tk.Button(
            recents_body,
            text="Open Selected",
            font=("Segoe UI", 11, "bold"),
            bg=colors["bg_surface_alt"],
            fg=colors["text_primary"],
            activebackground=colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=3,
            overrelief=tk.SUNKEN,
            cursor="hand2",
            padx=12,
            pady=6,
            command=self._open_selected_recent,
        )
        self.open_recent_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        tk.Label(
            self.inner,
            text="Document outline",
            font=("Segoe UI", 11, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
        ).pack(anchor="w", pady=(0, 6))

        self.tree = ttk.Treeview(self.inner, show="tree", style="Nav.Treeview")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_tree)

    def bind_commands(self, handler):
        self._handler = handler

    def set_items(self, items):
        self.tree.delete(*self.tree.get_children())
        for label, index in items:
            self.tree.insert("", "end", iid=index, text=label)

    def set_recents(self, recents):
        values = list(recents) if recents else []
        self.recent_box["values"] = values
        self.recent_var.set(values[0] if values else "")

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["bg_panel"], highlightbackground=colors["border"])
        self._update_theme_recursive(self)

    def _update_theme_recursive(self, widget):
        if isinstance(widget, tk.LabelFrame):
            widget.config(bg=self.colors["bg_panel"], fg=self.colors["text_secondary"])
        elif isinstance(widget, tk.Frame):
            widget.config(bg=self.colors["bg_panel"])
        elif isinstance(widget, tk.Label):
            is_header = "bold" in str(widget.cget("font"))
            fg = self.colors["text_primary"] if is_header else self.colors["text_secondary"]
            widget.config(bg=self.colors["bg_panel"], fg=fg)
        elif isinstance(widget, tk.Button):
            is_primary = "save" == str(widget.cget("text")).strip().lower()
            widget.config(
                bg=self.colors["accent"] if is_primary else self.colors["bg_surface_alt"],
                fg="#FFFFFF" if is_primary else self.colors["text_primary"],
                activebackground=self.colors["accent_hover"],
                activeforeground="#FFFFFF",
            )
        for child in widget.winfo_children():
            self._update_theme_recursive(child)

    def _quick_button(self, parent, label, command, primary=False):
        return tk.Button(
            parent,
            text=label,
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["accent"] if primary else self.colors["bg_surface_alt"],
            fg="#FFFFFF" if primary else self.colors["text_primary"],
            activebackground=self.colors["accent_hover"],
            activeforeground="#FFFFFF",
            relief=tk.RAISED,
            bd=3,
            overrelief=tk.SUNKEN,
            cursor="hand2",
            padx=10,
            pady=6,
            command=command,
        )

    def _open_selected_recent(self, _event=None):
        selected = self.recent_var.get().strip()
        if selected and self._handler:
            self._handler(UiCommandRequest(command_id=UiCommandId.OPEN_RECENT, payload={"path": selected}))

    def _emit(self, command_id: str, payload=None):
        if self._handler:
            self._handler(UiCommandRequest(command_id=command_id, payload=payload))

    def _on_select_tree(self, _event=None):
        sel = self.tree.selection()
        if sel and self._handler:
            self._handler(UiCommandRequest(command_id=UiCommandId.NAVIGATE_TO_INDEX, payload={"index": sel[0]}))
