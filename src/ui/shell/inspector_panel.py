import tkinter as tk


class InspectorPanel(tk.Frame):
    def __init__(self, parent, colors, width=320):
        super().__init__(
            parent,
            bg=colors["bg_panel"],
            width=width,
            relief=tk.RAISED,
            bd=3,
            highlightthickness=1,
            highlightbackground=colors["border"],
        )
        self.colors = colors
        self.pack_propagate(False)

        tk.Label(
            self,
            text="Inspector",
            font=("Segoe UI", 13, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_primary"],
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.meta_frame = tk.Frame(self, bg=colors["bg_panel"])
        self.meta_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.words_lbl = self._meta("Words", "0")
        self.chars_lbl = self._meta("Characters", "0")
        self.lines_lbl = self._meta("Lines", "0")
        self.zoom_lbl = self._meta("Zoom", "100%")

        tk.Label(
            self,
            text="Paragraph / font summary",
            font=("Segoe UI", 10, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
        ).pack(anchor="w", padx=12, pady=(8, 4))
        self.summary = tk.Label(
            self,
            text="Cursor details will appear here.",
            justify=tk.LEFT,
            anchor="nw",
            font=("Segoe UI", 9),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
        )
        self.summary.pack(fill=tk.X, padx=12)

    def set_visible(self, visible: bool):
        if visible:
            self.grid()
        else:
            self.grid_remove()

    def set_document_stats(self, words: int, chars: int, lines: int):
        self.words_lbl.config(text=str(words))
        self.chars_lbl.config(text=str(chars))
        self.lines_lbl.config(text=str(lines))

    def set_zoom(self, zoom: int):
        self.zoom_lbl.config(text=f"{zoom}%")

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["bg_panel"], highlightbackground=colors["border"])
        self._update_theme_recursive(self)

    def _meta(self, label: str, value: str):
        row = tk.Frame(self.meta_frame, bg=self.colors["bg_panel"])
        row.pack(fill=tk.X, pady=1)
        tk.Label(
            row,
            text=f"{label}:",
            width=10,
            anchor="w",
            font=("Segoe UI", 10),
            bg=self.colors["bg_panel"],
            fg=self.colors["text_secondary"],
        ).pack(side=tk.LEFT)
        val = tk.Label(
            row,
            text=value,
            anchor="w",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["bg_panel"],
            fg=self.colors["text_primary"],
        )
        val.pack(side=tk.LEFT)
        return val

    def _update_theme_recursive(self, widget):
        if isinstance(widget, tk.Frame):
            widget.config(bg=self.colors["bg_panel"])
        elif isinstance(widget, tk.Label):
            is_bold = "bold" in str(widget.cget("font"))
            fg = self.colors["text_primary"] if is_bold else self.colors["text_secondary"]
            widget.config(bg=self.colors["bg_panel"], fg=fg)
        for child in widget.winfo_children():
            self._update_theme_recursive(child)
