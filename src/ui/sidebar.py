import tkinter as tk
from tkinter import ttk

class Sidebar:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=app.colors["sidebar"], width=200)
        
        self.lbl = tk.Label(self.frame, text=" NAVIGATION ", bg=app.colors["sidebar"], font=("Segoe UI", 9, "bold"), fg="#555")
        self.lbl.pack(fill=tk.X, pady=(10,0))
        
        self.tree = ttk.Treeview(self.frame, show="tree", selectmode="browse", height=10)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.nav_jump)

    def nav_jump(self, e):
        sel = self.tree.selection()
        if sel: 
            self.app.workspace.editor.see(sel[0])
            self.app.workspace.editor.mark_set(tk.INSERT, sel[0])

    def update_theme(self, c):
        self.frame.config(bg=c["sidebar"])
        self.lbl.config(bg=c["sidebar"])
