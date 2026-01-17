import tkinter as tk
from tkinter import messagebox

# Import your existing configuration
from src.config import ConfigManager, THEME, APP_NAME, VERSION

# UI Components
from src.ui.ribbon import Ribbon
from src.ui.workspace import Workspace
from src.ui.sidebar import Sidebar
from src.ui.statusbar import StatusBar

# Logic
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
        
        # State
        self.current_theme_mode = self.settings.get("theme", "light")
        self.colors = THEME[self.current_theme_mode]
        self.is_focus_mode = False
        self.sidebar_visible = False

        # --- LAYOUT MANAGER ---
        # 1. Main Container (holds sidebar + workspace)
        self.main_container = tk.Frame(self.root, bg=self.colors["bg"])
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # 2. Initialize Components
        self.workspace = Workspace(self.main_container, self.colors, self.settings.get("zoom", 100))
        self.sidebar = Sidebar(self.main_container, self, self.colors)
        self.statusbar = StatusBar(self.root, self, self.colors)
        
        self.editor = self.workspace.get_editor()

        # 3. Initialize Logic
        self.file_mgr = FileManager(self.editor, self.root)
        self.processor = TextProcessor(self.editor)
        self.formatter = FormatManager(self.editor, self.root)
        self.tools = ToolManager(self.editor, self.root)

        # 4. Create Callback Map
        callbacks = {
            'open': self.file_mgr.open_file,
            'save': self.file_mgr.save_file,
            'pdf': self.file_mgr.export_pdf,
            'undo': self.editor.edit_undo,
            'redo': self.editor.edit_redo,
            'select_all': self.tools.select_all,
            'bold': lambda: self.formatter.toggle_format('bold'),
            'italic': lambda: self.formatter.toggle_format('italic'),
            'underline': lambda: self.formatter.toggle_format('underline'),
            'strike': lambda: self.formatter.toggle_format('overstrike'),
            'color': self.formatter.pick_text_color,
            'highlight': self.formatter.apply_highlight,
            'clear_fmt': self.formatter.clear_formatting,
            'spacing': self.formatter.set_line_spacing,
            'font_fam': self.formatter.apply_font_family,
            'font_size': self.formatter.apply_font_size,
            'align_l': lambda: self.formatter.set_alignment('left'),
            'align_c': lambda: self.formatter.set_alignment('center'),
            'align_r': lambda: self.formatter.set_alignment('right'),
            'img': self.tools.insert_image,
            'hr_line': self.tools.insert_horizontal_line,
            'date': self.tools.insert_date_time,
            'symbol': self.tools.open_symbol_picker,
            'find': self.tools.open_find_replace,
            'stats': self.tools.show_stats,
            'zoom_in': lambda: self.update_zoom(10),
            'zoom_out': lambda: self.update_zoom(-10),
            'pg_color': self.formatter.set_page_color,
            'spell': self.processor.run_spell_check,
            'tts': self.processor.read_aloud,
            'theme': self.toggle_theme,
            'focus': self.toggle_focus_mode,
            'sidebar': self.toggle_sidebar
        }

        # 5. Mount Ribbon (Packed BEFORE main container)
        self.ribbon = Ribbon(self.root, callbacks, self.colors)
        self.ribbon.pack(side=tk.TOP, fill=tk.X, before=self.main_container)
        
        self._bind_shortcuts()
        
        # Apply initial zoom from settings
        self.update_zoom(0)

    def update_zoom(self, amount):
        current_zoom = self.settings.get("zoom", 100)
        new_zoom = current_zoom + amount
        if new_zoom < 50: new_zoom = 50
        if new_zoom > 200: new_zoom = 200
        
        self.settings["zoom"] = new_zoom
        self.formatter.set_zoom(new_zoom, reset=(amount==0))
        self.statusbar.update_zoom_label(new_zoom)
        
        # Save config on change
        self.config_mgr.data = self.settings
        self.config_mgr.save()

    def toggle_theme(self):
        self.current_theme_mode = "dark" if self.current_theme_mode == "light" else "light"
        self.settings["theme"] = self.current_theme_mode
        self.config_mgr.save()
        
        c = THEME[self.current_theme_mode]
        self.colors = c
        
        self.main_container.config(bg=c["bg"])
        self.workspace.update_theme(c)
        self.sidebar.update_theme(c)
        self.statusbar.update_theme(c)
        self.ribbon.update_theme(c)

    def toggle_focus_mode(self):
        if not self.is_focus_mode:
            self.ribbon.pack_forget()
            self.statusbar.frame.pack_forget()
            if self.sidebar_visible: self.sidebar.frame.pack_forget()
            self.root.attributes("-fullscreen", True)
            self.is_focus_mode = True
            messagebox.showinfo("Focus Mode", "Press ESC to exit Focus Mode")
            self.root.bind("<Escape>", lambda e: self.toggle_focus_mode())
        else:
            self.root.attributes("-fullscreen", False)
            self.statusbar.frame.pack(side=tk.BOTTOM, fill=tk.X)
            self.ribbon.pack(side=tk.TOP, fill=tk.X, before=self.main_container)
            if self.sidebar_visible: self.sidebar.frame.pack(side=tk.LEFT, fill=tk.Y)
            self.is_focus_mode = False
            self.root.unbind("<Escape>")

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.frame.pack_forget()
            self.sidebar_visible = False
        else:
            self.sidebar.frame.pack(side=tk.LEFT, fill=tk.Y)
            self.sidebar_visible = True

    def _bind_shortcuts(self):
        # File
        self.root.bind("<Control-s>", lambda e: self.file_mgr.save_file())
        self.root.bind("<Command-s>", lambda e: self.file_mgr.save_file())
        self.root.bind("<Control-o>", lambda e: self.file_mgr.open_file())
        self.root.bind("<Command-o>", lambda e: self.file_mgr.open_file())
        # Formatting
        self.root.bind("<Control-b>", lambda e: self.formatter.toggle_format('bold'))
        self.root.bind("<Command-b>", lambda e: self.formatter.toggle_format('bold'))
        self.root.bind("<Control-i>", lambda e: self.formatter.toggle_format('italic'))
        self.root.bind("<Command-i>", lambda e: self.formatter.toggle_format('italic'))
        self.root.bind("<Control-u>", lambda e: self.formatter.toggle_format('underline'))
        self.root.bind("<Command-u>", lambda e: self.formatter.toggle_format('underline'))
        # Tools
        self.root.bind("<Control-f>", lambda e: self.tools.open_find_replace())
        self.root.bind("<Command-f>", lambda e: self.tools.open_find_replace())
        # Editor
        self.root.bind("<Control-z>", lambda e: self.editor.edit_undo())
        self.root.bind("<Command-z>", lambda e: self.editor.edit_undo())
        self.root.bind("<Control-y>", lambda e: self.editor.edit_redo())
        self.root.bind("<Command-y>", lambda e: self.editor.edit_redo())

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()