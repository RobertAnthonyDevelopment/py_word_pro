import tkinter as tk
from tkinter import font, colorchooser

class FormatManager:
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.zoom_level = 100
        self.default_font = "Calibri"
        self.default_size = 11

    def toggle_format(self, format_type):
        """
        Toggles Bold, Italic, Underline, or Strikethrough.
        Handles the conflict between Bold and Italic by using a combined tag.
        """
        try:
            if not self.editor.tag_ranges("sel"):
                return
            
            # 1. Identify current state
            current_tags = self.editor.tag_names("sel.first")
            
            is_bold = "bold" in current_tags or "bold_italic" in current_tags
            is_italic = "italic" in current_tags or "bold_italic" in current_tags
            is_underline = "underline" in current_tags
            is_overstrike = "overstrike" in current_tags
            
            # 2. Flip state
            if format_type == "bold": is_bold = not is_bold
            elif format_type == "italic": is_italic = not is_italic
            elif format_type == "underline": is_underline = not is_underline
            elif format_type == "overstrike": is_overstrike = not is_overstrike
            
            # 3. Clear formatting tags
            self.editor.tag_remove("bold", "sel.first", "sel.last")
            self.editor.tag_remove("italic", "sel.first", "sel.last")
            self.editor.tag_remove("bold_italic", "sel.first", "sel.last")
            self.editor.tag_remove("underline", "sel.first", "sel.last")
            self.editor.tag_remove("overstrike", "sel.first", "sel.last")
            
            # 4. Re-apply correct Font Tags
            if is_bold and is_italic:
                tag = "bold_italic"
                self.editor.tag_add(tag, "sel.first", "sel.last")
                new_font = font.Font(family=self.default_font, size=self.default_size, weight="bold", slant="italic")
                self.editor.tag_configure(tag, font=new_font)
            elif is_bold:
                tag = "bold"
                self.editor.tag_add(tag, "sel.first", "sel.last")
                new_font = font.Font(family=self.default_font, size=self.default_size, weight="bold")
                self.editor.tag_configure(tag, font=new_font)
            elif is_italic:
                tag = "italic"
                self.editor.tag_add(tag, "sel.first", "sel.last")
                new_font = font.Font(family=self.default_font, size=self.default_size, slant="italic")
                self.editor.tag_configure(tag, font=new_font)

            # 5. Apply Independent Tags
            if is_underline:
                self.editor.tag_add("underline", "sel.first", "sel.last")
                self.editor.tag_configure("underline", underline=True)
                
            if is_overstrike:
                self.editor.tag_add("overstrike", "sel.first", "sel.last")
                self.editor.tag_configure("overstrike", overstrike=True)

        except tk.TclError:
            pass 

    def apply_highlight(self):
        color = colorchooser.askcolor(title="Choose Highlight Color")[1]
        if color:
            try:
                if not self.editor.tag_ranges("sel"): return
                tag = f"bg_{color}"
                self.editor.tag_add(tag, "sel.first", "sel.last")
                self.editor.tag_configure(tag, background=color)
            except tk.TclError: pass

    def clear_formatting(self):
        """Removes all custom tags from selection."""
        try:
            if not self.editor.tag_ranges("sel"): return
            for tag in self.editor.tag_names():
                if tag != "sel":
                    self.editor.tag_remove(tag, "sel.first", "sel.last")
        except tk.TclError: pass

    def set_line_spacing(self, spacing_val):
        """Sets line spacing (1.0, 1.5, 2.0)."""
        # spacing2 is the space between lines in pixels
        px_spacing = 0
        if spacing_val == 1.5: px_spacing = 6
        if spacing_val == 2.0: px_spacing = 14
        
        self.editor.configure(spacing2=px_spacing)

    # --- Standard Methods (Preserved) ---
    def apply_font_family(self, font_name):
        self.default_font = font_name
        self._update_font_selection()

    def apply_font_size(self, size):
        self.default_size = int(size)
        self._update_font_selection()

    def _update_font_selection(self):
        try:
            if not self.editor.tag_ranges("sel"): return
            new_font = (self.default_font, self.default_size)
            tag_name = f"base_font" 
            self.editor.tag_add(tag_name, "sel.first", "sel.last")
            self.editor.tag_configure(tag_name, font=new_font)
        except tk.TclError: pass

    def pick_text_color(self):
        color = colorchooser.askcolor(title="Choose Text Color")[1]
        if color:
            try:
                if not self.editor.tag_ranges("sel"): return
                tag = f"color_{color}"
                self.editor.tag_add(tag, "sel.first", "sel.last")
                self.editor.tag_configure(tag, foreground=color)
            except tk.TclError: pass

    def set_alignment(self, align_type):
        try:
            self.editor.tag_add(align_type, "sel.first", "sel.last")
        except tk.TclError:
            self.editor.tag_add(align_type, "insert linestart", "insert lineend")
        self.editor.tag_configure(align_type, justify=align_type)

    def set_zoom(self, amount, reset=False):
        if reset: self.zoom_level = 100
        else: self.zoom_level += amount
        if self.zoom_level < 50: self.zoom_level = 50
        if self.zoom_level > 200: self.zoom_level = 200
        
        scaled_size = int((self.default_size * self.zoom_level) / 100)
        scaled_pad = int(40 * (self.zoom_level / 100))
        self.editor.configure(font=(self.default_font, scaled_size))
        self.editor.configure(padx=scaled_pad)

    def set_page_color(self):
        color = colorchooser.askcolor(title="Page Background")[1]
        if color: self.editor.configure(bg=color)