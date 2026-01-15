import tkinter as tk
from tkinter import ttk, font
import re
from .console import ConsolePane

class LineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.textwidget = None
        self.font = font.Font(family="Consolas", size=10)
    def attach(self, tx): self.textwidget = tx
    def redraw(self, *args):
        self.delete("all")
        i = self.textwidget.index("@0,0")
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None: break
            y = dline[1]
            self.create_text(35, y, anchor="ne", text=str(i).split(".")[0], fill="#888", font=self.font)
            i = self.textwidget.index("%s+1line" % i)

class Workspace:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=app.colors["bg"])
        
        self.v_paned = tk.PanedWindow(self.frame, orient=tk.VERTICAL, bg=app.colors["bg"], sashwidth=4)
        self.v_paned.pack(fill=tk.BOTH, expand=True)
        
        self.desk = tk.Frame(self.v_paned, bg=app.colors["bg"])
        self.v_paned.add(self.desk, minsize=400)
        
        # Console
        self.console = ConsolePane(self.v_paned, app)
        self.v_paned.add(self.console.frame, minsize=0)
        self.app.dev_engine.console_widget = self.console.text_area

        # Rulers & Editor
        self.ruler_h = tk.Canvas(self.desk, height=25, bg=app.colors["ruler"], highlightthickness=0)
        self.ruler_h.pack(side=tk.TOP, fill=tk.X)
        self.ws_inner = tk.Frame(self.desk, bg=app.colors["bg"])
        self.ws_inner.pack(fill=tk.BOTH, expand=True)
        self.ruler_v = tk.Canvas(self.ws_inner, width=25, bg=app.colors["ruler"], highlightthickness=0)
        self.ruler_v.pack(side=tk.LEFT, fill=tk.Y)
        
        self.paper_frame = tk.Frame(self.ws_inner, bg=app.colors["paper"])
        self.paper_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.vs = ttk.Scrollbar(self.paper_frame, orient=tk.VERTICAL)
        self.vs.pack(side=tk.RIGHT, fill=tk.Y)
        self.linenumbers = LineNumbers(self.paper_frame, width=40, bg="#f0f0f0", bd=0, highlightthickness=0)
        self.linenumbers.pack(side=tk.LEFT, fill=tk.Y)
        
        self.editor = tk.Text(self.paper_frame, font=("Calibri", 12), wrap=tk.WORD, undo=True, padx=40, pady=40, bd=0, yscrollcommand=self.vs.set)
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.vs.config(command=self.editor.yview)
        self.linenumbers.attach(self.editor)
        
        self.editor.bind("<KeyRelease>", self._on_key)
        self._draw_rulers()

    def _on_key(self, e):
        self.linenumbers.redraw()
        if self.app.highlighter: self.app.highlighter.trigger()
        if e.keysym == "Return": self.app.file_manager.scan_nav()

    def _draw_rulers(self):
        for i in range(0, 2000, 10):
            h = 10 if i%50==0 else 5
            self.ruler_h.create_line(i+40, 25, i+40, 25-h, fill="#aaa")
            w = 10 if i%50==0 else 5
            self.ruler_v.create_line(25, i+40, 25-w, i+40, fill="#aaa")

    def update_theme(self, c):
        self.frame.config(bg=c["bg"])
        self.desk.config(bg=c["bg"])
        self.ws_inner.config(bg=c["bg"])
        self.ruler_h.config(bg=c["ruler"])
        self.ruler_v.config(bg=c["ruler"])
        self.paper_frame.config(bg=c["paper"])
        self.editor.config(bg=c["paper"], fg=c["text"], insertbackground=c["text"])
        self.console.update_theme(c)
