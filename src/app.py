import tkinter as tk
from tkinter import messagebox
from src.config import ConfigManager, THEME, APP_NAME, VERSION
from src.ui.ribbon import Ribbon
from src.ui.workspace import Workspace
from src.ui.sidebar import Sidebar
from src.ui.statusbar import StatusBar
from src.logic.file_manager import FileManager
from src.logic.processor import TextProcessor
from src.logic.formatting import FormatManager
from src.logic.tools import ToolManager

class App:
    def __init__(self, root):
        self.root = root
        self.config_mgr = ConfigManager()
        self.settings = self.config_mgr.data
        
        self.root.title(f"{APP_NAME} {VERSION}")
        self.root.geometry(self.settings.get("geometry", "1400x900"))
        
        self.current_theme = self.settings.get("theme", "light")
        self.colors = THEME[self.current_theme]

        # Layout
        self.main_container = tk.Frame(self.root, bg=self.colors["bg"])
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Components
        self.workspace = Workspace(self.main_container, self.colors)
        self.editor = self.workspace.get_editor()
        
        # Logic Modules
        self.file_mgr = FileManager(self.editor, self.root)
        self.formatter = FormatManager(self.editor, self.root)
        self.tools = ToolManager(self.editor, self.root)
        self.processor = TextProcessor(self.editor)

        # UI Bars
        self.sidebar = Sidebar(self.main_container, self, self.colors)
        self.statusbar = StatusBar(self.root, self, self.colors)

        # Commands
        callbacks = {
            'open': self.file_mgr.open_file,
            'save': self.file_mgr.save_file,
            'undo': self.safe_undo,
            'redo': self.safe_redo,
            'bold': lambda: self.formatter.toggle_format('bold'),
            'italic': lambda: self.formatter.toggle_format('italic'),
            'underline': lambda: self.formatter.toggle_format('underline'),
            'strike': lambda: self.formatter.toggle_format('overstrike'),
            'align_l': lambda: self.formatter.set_alignment('left'),
            'align_c': lambda: self.formatter.set_alignment('center'),
            'align_r': lambda: self.formatter.set_alignment('right'),
            'list': self.formatter.toggle_list,
            'color': self.formatter.pick_text_color,
            'highlight': self.formatter.apply_highlight,
            'clear_fmt': self.formatter.clear_formatting,
            'spacing': self.formatter.set_line_spacing,
            'font_fam': self.formatter.apply_font_family,
            'font_size': self.formatter.apply_font_size,
            'zoom_in': lambda: self.update_zoom(10),
            'zoom_out': lambda: self.update_zoom(-10),
            'img': self.tools.insert_image,
            'hr_line': self.tools.insert_horizontal_line,
            'date': self.tools.insert_date_time,
            'symbol': self.tools.open_symbol_picker,
            'find': self.tools.open_find_replace,
            'stats': self.tools.show_stats,
            'pdf': self.file_mgr.export_pdf,
            'select_all': self.tools.select_all,
            'pg_color': lambda: None, 'spell': lambda: None, 'tts': lambda: None,
            'theme': lambda: None, 'focus': lambda: None, 'sidebar': lambda: None
        }

        self.ribbon = Ribbon(self.root, callbacks, self.colors)
        self.ribbon.pack(side=tk.TOP, fill=tk.X, before=self.main_container)
        self._bind_shortcuts()
        
        # Init Zoom
        self.update_zoom(0, absolute=self.settings.get("zoom", 100))

    def safe_undo(self):
        # Tk's native undo stack doesn't reliably capture tag-based formatting
        # (e.g., alignment). If the most recent user action was formatting,
        # undo that first to avoid "Undo" deleting newly typed text.
        try:
            if self.formatter.undo_format():
                return
        except Exception:
            # Fall through to Tk undo
            pass
        try:
            self.editor.edit_undo()
            # After a successful text undo, prevent redo-format from firing.
            self.formatter.note_text_activity()
        except tk.TclError:
            pass

    def safe_redo(self):
        # Prefer redoing formatting only immediately after a formatting undo.
        try:
            if self.formatter.redo_format():
                return
        except Exception:
            pass
        try:
            self.editor.edit_redo()
        except tk.TclError:
            pass

    def update_zoom(self, amount=0, absolute=None):
        current = self.formatter.zoom_level
        new_zoom = absolute if absolute else current + amount
        
        if new_zoom < 50: new_zoom = 50
        if new_zoom > 200: new_zoom = 200
        
        self.formatter.set_zoom(new_zoom)
        self.statusbar.update_zoom_label(new_zoom)
        self.settings["zoom"] = new_zoom
        self.config_mgr.save()

    def _bind_shortcuts(self):
        self.root.bind("<Control-s>", lambda e: self.file_mgr.save_file())
        self.root.bind("<Control-z>", lambda e: self.safe_undo())
        self.root.bind("<Control-y>", lambda e: self.safe_redo())

        # Track *actual* text modifications (typing, paste, programmatic inserts)
        # without being confused by navigation keys.
        def _on_modified(_evt):
            try:
                if self.editor.edit_modified():
                    self.formatter.note_text_activity()
                    # Reset so the virtual event can fire again on the next edit.
                    self.editor.edit_modified(False)
            except Exception:
                pass

        self.editor.bind("<<Modified>>", _on_modified, add="+")