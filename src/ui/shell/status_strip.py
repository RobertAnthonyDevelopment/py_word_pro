import tkinter as tk

from src.ui.contracts import UiCommandId, UiCommandRequest


class StatusStrip(tk.Frame):
    def __init__(self, parent, colors):
        super().__init__(
            parent,
            bg=colors["bg_panel"],
            relief=tk.RAISED,
            bd=4,
            highlightthickness=1,
            highlightbackground=colors["border"],
        )
        self.colors = colors
        self._handler = None
        self._syncing_slider = False

        self.status_lbl = tk.Label(
            self,
            text="Ready",
            font=("Segoe UI", 11, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_secondary"],
        )
        self.status_lbl.pack(side=tk.LEFT, padx=16, pady=8)

        self.zoom_lbl = tk.Label(
            self,
            text="100%",
            font=("Segoe UI", 11, "bold"),
            bg=colors["bg_panel"],
            fg=colors["text_primary"],
        )
        self.zoom_lbl.pack(side=tk.RIGHT, padx=(0, 14))

        self.zoom_slider = tk.Scale(
            self,
            from_=50,
            to=200,
            orient=tk.HORIZONTAL,
            showvalue=0,
            length=300,
            bg=colors["bg_panel"],
            fg=colors["text_primary"],
            troughcolor=colors["bg_surface_alt"],
            activebackground=colors["accent"],
            highlightthickness=0,
            width=14,
            command=self._on_slide,
        )
        self.zoom_slider.set(100)
        self.zoom_slider.pack(side=tk.RIGHT, padx=(0, 10), pady=4)

    def bind_commands(self, handler):
        self._handler = handler

    def set_status(self, text: str):
        self.status_lbl.config(text=text)

    def set_zoom(self, value: int):
        self.zoom_lbl.config(text=f"{int(value)}%")
        self._syncing_slider = True
        try:
            self.zoom_slider.set(int(value))
        finally:
            self._syncing_slider = False

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["bg_panel"], highlightbackground=colors["border"])
        self.status_lbl.config(bg=colors["bg_panel"], fg=colors["text_secondary"])
        self.zoom_lbl.config(bg=colors["bg_panel"], fg=colors["text_primary"])
        self.zoom_slider.config(
            bg=colors["bg_panel"],
            fg=colors["text_primary"],
            troughcolor=colors["bg_surface"],
            activebackground=colors["accent"],
        )

    def _on_slide(self, value):
        if self._syncing_slider:
            return
        if self._handler:
            self._handler(UiCommandRequest(command_id=UiCommandId.ZOOM_SET, payload={"value": int(float(value))}))
