import tkinter as tk
from tkinter import ttk


class Sidebar:
    def __init__(self, parent, app, colors):
        self.app = app
        self.frame = tk.Frame(parent, bg=colors["sidebar"], width=220)

        self.lbl = tk.Label(
            self.frame,
            text=" NAVIGATION ",
            bg=colors["sidebar"],
            font=("Segoe UI", 9, "bold"),
            fg="#555"
        )
        self.lbl.pack(fill=tk.X, pady=(10, 0))

        style = ttk.Style()
        style.configure(
            "Sidebar.Treeview",
            background=colors["paper"],
            fieldbackground=colors["paper"],
            foreground=colors["text"],
            borderwidth=0
        )

        self.tree = ttk.Treeview(
            self.frame,
            show="tree",
            selectmode="browse",
            style="Sidebar.Treeview"
        )
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.nav_jump)

    def nav_jump(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return

        # FIX: Workspace does not expose workspace.editor; App exposes app.editor
        try:
            self.app.editor.see(sel[0])
            self.app.editor.mark_set(tk.INSERT, sel[0])
            self.app.editor.focus()
        except Exception:
            pass

    def update_theme(self, c):
        self.frame.config(bg=c["sidebar"])
        self.lbl.config(bg=c["sidebar"], fg=c["text"])

        style = ttk.Style()
        style.configure(
            "Sidebar.Treeview",
            background=c["paper"],
            fieldbackground=c["paper"],
            foreground=c["text"]
        )
