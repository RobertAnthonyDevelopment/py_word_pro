import tkinter as tk
from tkinter import messagebox, colorchooser

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

        # --- View state (persisted) ---
        self.current_theme = self.settings.get("theme", "light")
        self.paper_color = self.settings.get("paper_color")  # hex or None
        self.sidebar_visible = bool(self.settings.get("sidebar_visible", True))
        self.focus_mode = bool(self.settings.get("focus_mode", False))

        self.colors = THEME[self.current_theme]

        # Layout
        self.main_container = tk.Frame(self.root, bg=self.colors["bg"])
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Content area (sidebar + workspace)
        self.content = tk.Frame(self.main_container, bg=self.colors["bg"])
        self.content.pack(fill=tk.BOTH, expand=True)

        # Sidebar + workspace (we control packing/visibility here)
        self.sidebar = Sidebar(self.content, self, self.colors)
        self.workspace = Workspace(self.content, self.colors)
        self.editor = self.workspace.get_editor()

        # Workspace packs itself in its __init__; undo that so we can lay out properly
        try:
            self.workspace.pack_forget()
        except Exception:
            pass

        # Logic Modules
        self.file_mgr = FileManager(self.editor, self.root)
        self.formatter = FormatManager(self.editor, self.root)
        self.tools = ToolManager(self.editor, self.root)
        self.processor = TextProcessor(self.editor)

        # Statusbar
        self.statusbar = StatusBar(self.root, self, self.colors)

        # Apply stored paper color override (if any)
        if self.paper_color:
            try:
                self.editor.config(bg=self.paper_color)
            except Exception:
                pass

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

            # Lists
            'list': self.formatter.toggle_list,
            'num_list': self.formatter.toggle_numbered_list,

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

            # Review (now wired)
            'spell': self.processor.run_spell_check,
            'tts': self.processor.read_aloud,

            # View tab
            'pg_color': self.pick_paper_color,
            'theme': self.toggle_theme,
            'focus': self.toggle_focus_mode,
            'sidebar': self.toggle_sidebar,
        }

        self.ribbon = Ribbon(self.root, callbacks, self.colors)
        self.ribbon.pack(side=tk.TOP, fill=tk.X, before=self.main_container)

        self._bind_shortcuts()

        # Pack sidebar/workspace according to view state
        self._apply_layout_state()

        # Init Zoom
        self.update_zoom(0, absolute=self.settings.get("zoom", 100))

        # If focus mode was saved as ON, enforce it after everything exists
        if self.focus_mode:
            self._apply_focus_state(True)

    # -----------------------------
    # View Tab Features
    # -----------------------------

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.colors = THEME[self.current_theme]

        self.settings["theme"] = self.current_theme
        self.config_mgr.save()

        self.apply_theme()

    def pick_paper_color(self):
        # Returns ( (r,g,b), "#rrggbb" ) or (None, None)
        _, hex_color = colorchooser.askcolor(title="Choose Paper Color")
        if not hex_color:
            return

        self.paper_color = hex_color
        self.settings["paper_color"] = hex_color
        self.config_mgr.save()

        # Apply directly to the editor "paper"
        try:
            self.editor.config(bg=hex_color)
        except Exception:
            pass

        # Sidebar tree uses colors["paper"], so refresh theme so it matches better
        try:
            self.sidebar.update_theme(self.colors)
        except Exception:
            pass

    def toggle_sidebar(self):
        # If focus mode is on, turning sidebar on/off should also exit focus cleanly
        if self.focus_mode:
            self.toggle_focus_mode()
            return

        self.sidebar_visible = not self.sidebar_visible
        self.settings["sidebar_visible"] = self.sidebar_visible
        self.config_mgr.save()

        self._apply_layout_state()

    def toggle_focus_mode(self):
        self.focus_mode = not self.focus_mode
        self.settings["focus_mode"] = self.focus_mode
        self.config_mgr.save()

        self._apply_focus_state(self.focus_mode)

    def _apply_focus_state(self, enabled: bool):
        if enabled:
            # Hide sidebar + statusbar for distraction-free mode
            try:
                self.sidebar.frame.pack_forget()
            except Exception:
                pass
            try:
                self.statusbar.frame.pack_forget()
            except Exception:
                pass
            # Keep workspace visible
            self._pack_workspace_only()
        else:
            # Restore statusbar and sidebar based on saved sidebar_visible
            try:
                self.statusbar.frame.pack(side=tk.BOTTOM, fill=tk.X)
            except Exception:
                pass
            self._apply_layout_state()

    def _apply_layout_state(self):
        # Always clear current packing first
        try:
            self.sidebar.frame.pack_forget()
        except Exception:
            pass
        try:
            self.workspace.pack_forget()
        except Exception:
            pass

        if self.sidebar_visible:
            # Sidebar on the left
            self.sidebar.frame.pack(side=tk.LEFT, fill=tk.Y)

        # Workspace consumes the rest
        self.workspace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _pack_workspace_only(self):
        try:
            self.workspace.pack_forget()
        except Exception:
            pass
        self.workspace.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def apply_theme(self):
        # Update background frames
        try:
            self.main_container.config(bg=self.colors["bg"])
            self.content.config(bg=self.colors["bg"])
        except Exception:
            pass

        # Push theme into components
        try:
            self.ribbon.update_theme(self.colors)
        except Exception:
            pass
        try:
            self.workspace.update_theme(self.colors)
        except Exception:
            pass
        try:
            self.sidebar.update_theme(self.colors)
        except Exception:
            pass
        try:
            self.statusbar.update_theme(self.colors)
        except Exception:
            pass

        # Re-apply paper override after theme swap
        if self.paper_color:
            try:
                self.editor.config(bg=self.paper_color)
            except Exception:
                pass

    # -----------------------------
    # Undo/Redo (safe versions)
    # -----------------------------

    def safe_undo(self):
        try:
            if self.formatter.undo_format():
                return
        except Exception:
            pass
        try:
            self.editor.edit_undo()
            self.formatter.note_text_activity()
        except tk.TclError:
            pass

    def safe_redo(self):
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

        if new_zoom < 50:
            new_zoom = 50
        if new_zoom > 200:
            new_zoom = 200

        self.formatter.set_zoom(new_zoom)
        self.statusbar.update_zoom_label(new_zoom)
        self.settings["zoom"] = new_zoom
        self.config_mgr.save()

    def _bind_shortcuts(self):
        self.root.bind("<Control-s>", lambda e: self.file_mgr.save_file())
        self.root.bind("<Control-z>", lambda e: self.safe_undo())
        self.root.bind("<Control-y>", lambda e: self.safe_redo())

        def _on_modified(_evt):
            try:
                if self.editor.edit_modified():
                    self.formatter.note_text_activity()
                    self.editor.edit_modified(False)
            except Exception:
                pass

        self.editor.bind("<<Modified>>", _on_modified, add="+")

        # List continuation (bullets + numbering)
        self.editor.bind("<Return>", self.formatter.handle_return_key, add="+")
