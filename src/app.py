import tkinter as tk
from tkinter import ttk
import platform
from .config import ConfigManager, THEME, APP_NAME, VERSION
from .ui.ribbon import Ribbon
from .ui.sidebar import Sidebar
from .ui.workspace import Workspace
from .ui.statusbar import StatusBar
from .ui.console import ConsolePane
from .logic.file_manager import FileManager
from .logic.syntax import SyntaxHighlighter
from .logic.developer import DeveloperEngine

class PyWordEnterprise:
    def __init__(self, root):
        self.root = root
        self.cfg = ConfigManager()
        self.root.title(f"{APP_NAME} {VERSION}")
        self.root.geometry(self.cfg.data.get("geometry", "1400x900"))
        
        self.current_theme = self.cfg.data["theme"]
        self.colors = THEME[self.current_theme]
        self.zoom_val = self.cfg.data.get("zoom", 100)
        self.is_macos = platform.system() == "Darwin"
        self.ctrl = "Command" if self.is_macos else "Control"
        
        self.file_manager = FileManager(self)
        self.dev_engine = DeveloperEngine(self)
        
        self._init_styles()
        
        self.ribbon = Ribbon(self.root, self)
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=self.colors["bg"], sashwidth=4)
        
        self.ribbon.pack(side=tk.TOP, fill=tk.X)
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        self.sidebar = Sidebar(self.paned, self)
        self.paned.add(self.sidebar.frame, minsize=0)
        
        self.workspace = Workspace(self.paned, self)
        self.paned.add(self.workspace.frame, minsize=600)
        
        self.statusbar = StatusBar(self.root, self)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.highlighter = SyntaxHighlighter(self.workspace.editor, self.colors)
        self.update_ui_theme()
        self.file_manager.start_autosave()

    def _init_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background=self.colors["ribbon"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=[12, 6], font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", self.colors["primary"])])

    def update_ui_theme(self):
        c = self.colors
        self.ribbon.update_theme(c)
        self.sidebar.update_theme(c)
        self.workspace.update_theme(c)
        self.statusbar.update_theme(c)
        self.highlighter.update_theme(self.current_theme == "dark")
        self.highlighter.highlight()
