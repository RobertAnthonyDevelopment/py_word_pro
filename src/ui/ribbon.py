import tkinter as tk
from tkinter import ttk, font, colorchooser
import datetime

class Ribbon:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=app.colors["ribbon"], height=140)
        self.frame.pack_propagate(False)
        
        tk.Button(self.frame, text="FILE", bg=app.colors["primary"], fg="white", 
                  font=("Segoe UI", 9, "bold"), width=6, relief=tk.FLAT, 
                  command=app.file_manager.open_backstage).pack(side=tk.LEFT, fill=tk.Y)

        self.tabs = ttk.Notebook(self.frame)
        self.tabs.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self._build_tabs()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def _add_tab(self, txt): 
        f = tk.Frame(self.tabs, bg=self.app.colors["ribbon"])
        self.tabs.add(f, text=f"  {txt}  ")
        return f

    def _grp(self, p, txt): 
        f = tk.LabelFrame(p, text=txt, bg=self.app.colors["ribbon"], fg="#666", padx=5, pady=2, font=("Segoe UI", 8))
        f.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        return f

    def _btn(self, p, txt, cmd):
        tk.Button(p, text=txt, command=cmd, relief=tk.FLAT, bg="#fcfcfc", activebackground="#e1e1e1", bd=1).pack(side=tk.LEFT, padx=2, fill=tk.Y, pady=2)

    def _build_tabs(self):
        # HOME
        t = self._add_tab("Home")
        g = self._grp(t, "Font")
        self.cb_font = ttk.Combobox(g, values=font.families()[:100], width=15, state="readonly")
        self.cb_font.set("Calibri"); self.cb_font.pack(side=tk.LEFT)
        self.cb_font.bind("<<ComboboxSelected>>", self.apply_font)
        
        self.cb_size = ttk.Combobox(g, values=[10,12,14,18,24,36], width=3, state="readonly")
        self.cb_size.set("12"); self.cb_size.pack(side=tk.LEFT)
        self.cb_size.bind("<<ComboboxSelected>>", self.apply_font)
        
        self._btn(g, "B", lambda: self.toggle_fmt("bold"))
        self._btn(g, "I", lambda: self.toggle_fmt("italic"))
        self._btn(g, "Color", self.text_color)

        # INSERT
        t = self._add_tab("Insert")
        g = self._grp(t, "Media")
        self._btn(g, "Picture", self.app.file_manager.ins_img)
        self._btn(g, "Date", lambda: self.app.workspace.editor.insert(tk.INSERT, datetime.datetime.now().strftime("%Y-%m-%d")))

        # DEV
        t = self._add_tab("Developer")
        g = self._grp(t, "Code")
        self._btn(g, "▶ Run", self.app.dev_engine.run_threaded)
        self._btn(g, "Code Block", lambda: self.app.workspace.editor.insert(tk.INSERT, "\n```\n# Code\n```\n"))

    def apply_font(self, e=None):
        f = self.cb_font.get(); s = self.cb_size.get()
        if f and s:
            tag = f"font_{f}_{s}".replace(" ", "_")
            self.app.workspace.editor.tag_configure(tag, font=(f, int(s)))
            try: self.app.workspace.editor.tag_add(tag, "sel.first", "sel.last")
            except: pass

    def toggle_fmt(self, tag):
        e = self.app.workspace.editor
        try:
            if tag in e.tag_names("sel.first"): e.tag_remove(tag, "sel.first", "sel.last")
            else: e.tag_add(tag, "sel.first", "sel.last")
            f = font.Font(font=e.cget("font"))
            if tag=="bold": f.configure(weight="bold")
            if tag=="italic": f.configure(slant="italic")
            e.tag_configure(tag, font=f)
        except: pass

    def text_color(self):
        c = colorchooser.askcolor()[1]
        if c: 
            self.app.workspace.editor.tag_configure(f"c_{c}", foreground=c)
            self.app.workspace.editor.tag_add(f"c_{c}", "sel.first", "sel.last")

    def update_theme(self, c):
        self.frame.config(bg=c["ribbon"])
