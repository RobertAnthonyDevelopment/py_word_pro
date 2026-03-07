import tkinter as tk
from tkinter import scrolledtext


class DevConsole(tk.Frame):
    def __init__(self, parent, colors):
        super().__init__(
            parent,
            bg=colors["console"],
            height=160,
            relief=tk.SUNKEN,
            bd=2,
            highlightthickness=1,
            highlightbackground=colors["border"],
        )
        self.colors = colors
        self.pack_propagate(False)

        self.title = tk.Label(
            self,
            text="Developer Console",
            anchor="w",
            font=("Segoe UI", 10, "bold"),
            bg=colors["console"],
            fg=colors["text_primary"],
        )
        self.title.pack(fill=tk.X, padx=8, pady=(6, 2))

        self.text_area = scrolledtext.ScrolledText(
            self,
            height=6,
            font=("Consolas", 9),
            state="disabled",
            bg=colors["console"],
            fg=colors["text_primary"],
            insertbackground=colors["text_primary"],
            relief=tk.FLAT,
        )
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def append(self, message: str):
        self.text_area.configure(state="normal")
        self.text_area.insert(tk.END, f"{message}\n")
        self.text_area.see(tk.END)
        self.text_area.configure(state="disabled")

    def clear(self):
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", tk.END)
        self.text_area.configure(state="disabled")

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["console"], highlightbackground=colors["border"])
        self.title.config(bg=colors["console"], fg=colors["text_primary"])
        self.text_area.config(bg=colors["console"], fg=colors["text_primary"], insertbackground=colors["text_primary"])
