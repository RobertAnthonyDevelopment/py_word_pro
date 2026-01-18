import tkinter as tk
from tkinter import font, colorchooser

class FormatManager:
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.zoom_level = 100
        self.default_font = "Calibri"
        self.default_size = 11

        # Tk's built-in Text undo stack does not reliably capture tag-based
        # formatting changes (e.g., alignment). We therefore keep a small,
        # explicit formatting undo/redo stack and only use it when a
        # formatting button was the most recent user action.
        self._fmt_undo_stack = []  # list[dict[str, callable]]
        self._fmt_redo_stack = []
        self._last_action_kind = "text"  # "text" | "format"
        self._last_undo_kind = None  # None | "format" | "text"

    def note_text_activity(self):
        """Mark that the user just performed a text edit (typing/paste/etc.)."""
        self._last_action_kind = "text"
        self._last_undo_kind = None

    def _note_format_activity(self):
        """Mark that the user just performed a formatting action."""
        self._last_action_kind = "format"
        self._last_undo_kind = None

    def _push_fmt_action(self, undo_fn, redo_fn):
        # New action invalidates redo history (standard behavior).
        self._fmt_redo_stack.clear()
        self._fmt_undo_stack.append({"undo": undo_fn, "redo": redo_fn})

    def can_undo_format(self):
        return self._last_action_kind == "format" and len(self._fmt_undo_stack) > 0

    def can_redo_format(self):
        # Only redo formatting if the most recent undo we performed was a
        # formatting undo (so Ctrl+Y behaves as expected after Ctrl+Z).
        return self._last_undo_kind == "format" and len(self._fmt_redo_stack) > 0

    def undo_format(self):
        if not self.can_undo_format():
            return False
        action = self._fmt_undo_stack.pop()
        try:
            action["undo"]()
            self._fmt_redo_stack.append(action)
            self._last_undo_kind = "format"
            return True
        except tk.TclError:
            return False

    def redo_format(self):
        if not self.can_redo_format():
            return False
        action = self._fmt_redo_stack.pop()
        try:
            action["redo"]()
            self._fmt_undo_stack.append(action)
            # Redoing a formatting action makes formatting the last action again.
            self._last_action_kind = "format"
            self._last_undo_kind = None
            return True
        except tk.TclError:
            return False

    def _each_line_in_range(self, start, end):
        """Yield 1-based line numbers covered by [start, end]."""
        s = self.editor.index(start)
        e = self.editor.index(end)
        s_line = int(s.split(".")[0])
        e_line = int(e.split(".")[0])
        # If end is at column 0 of a later line, treat it as excluding that line
        # (common when end == "sel.last" and selection ends at line start).
        if e.endswith(".0") and e_line > s_line:
            e_line -= 1
        return range(s_line, max(s_line, e_line) + 1)

    def _get_line_align(self, line_no):
        idx = f"{line_no}.0"
        tags = self.editor.tag_names(idx)
        for t in ("left", "center", "right"):
            if t in tags:
                return t
        return None

    def _apply_alignment_to_lines(self, align, line_nos):
        # Configure once (idempotent). `align` may be None when restoring a
        # line that had no explicit alignment tag.
        if align:
            self.editor.tag_configure(align, justify=align)
        for ln in line_nos:
            ls = f"{ln}.0"
            # Include the line break so newly typed text at EOL inherits the tag.
            le = f"{ln}.0 lineend+1c"
            for t in ("left", "center", "right"):
                self.editor.tag_remove(t, ls, le)
            if align:
                self.editor.tag_add(align, ls, le)

    def _checkpoint(self):
        """Creates an undo checkpoint to protect typing history."""
        try: self.editor.edit_separator()
        except tk.TclError: pass

    def toggle_format(self, tag):
        self._note_format_activity()
        self._checkpoint() # Cut rope
        try:
            if self.editor.tag_ranges("sel"):
                # Snapshot current state (within selection) for undo.
                sel_start, sel_end = self.editor.index("sel.first"), self.editor.index("sel.last")
                before = self._snapshot_tag_ranges(tag, sel_start, sel_end)

                current = self.editor.tag_names("sel.first")
                if tag in current:
                    self.editor.tag_remove(tag, "sel.first", "sel.last")
                else:
                    self.editor.tag_add(tag, "sel.first", "sel.last")
                    self._configure_tag(tag)

                after = self._snapshot_tag_ranges(tag, sel_start, sel_end)

                def _restore(ranges):
                    # Remove then restore the exact prior tagged segments.
                    self.editor.tag_remove(tag, sel_start, sel_end)
                    for a, b in ranges:
                        self.editor.tag_add(tag, a, b)
                    self._configure_tag(tag)

                self._push_fmt_action(lambda: _restore(before), lambda: _restore(after))
        except tk.TclError: pass
        self._checkpoint() # Cut rope again

    def _configure_tag(self, tag):
        f = font.Font(font=self.editor.cget("font"))
        if tag == "bold": f.configure(weight="bold")
        if tag == "italic": f.configure(slant="italic")
        if tag == "underline": f.configure(underline=True)
        if tag == "overstrike": f.configure(overstrike=True)
        self.editor.tag_configure(tag, font=f)

    def _snapshot_tag_ranges(self, tag, start, end):
        """Return a list of (start, end) ranges for `tag` intersecting [start, end]."""
        out = []
        try:
            ranges = self.editor.tag_ranges(tag)
        except tk.TclError:
            return out
        for i in range(0, len(ranges), 2):
            a = self.editor.index(ranges[i])
            b = self.editor.index(ranges[i + 1])

            # intersection = [max(a,start), min(b,end)] if they overlap
            if self.editor.compare(b, "<=", start) or self.editor.compare(a, ">=", end):
                continue
            s = a if self.editor.compare(a, ">", start) else start
            e = b if self.editor.compare(b, "<", end) else end
            if self.editor.compare(s, "<", e):
                out.append((s, e))
        return out

    def set_alignment(self, align):
        self._note_format_activity()
        self._checkpoint()
        try:
            # Range: Selection OR Current Line
            if self.editor.tag_ranges("sel"):
                start, end = "sel.first", "sel.last"
            else:
                start, end = "insert linestart", "insert lineend"

            line_nos = list(self._each_line_in_range(start, end))
            before = {ln: self._get_line_align(ln) for ln in line_nos}

            self._apply_alignment_to_lines(align, line_nos)

            def _undo():
                for ln in line_nos:
                    prev = before.get(ln)
                    self._apply_alignment_to_lines(prev, [ln])

            def _redo():
                self._apply_alignment_to_lines(align, line_nos)

            self._push_fmt_action(_undo, _redo)
        except tk.TclError: pass
        self._checkpoint()

    def toggle_list(self):
        self._checkpoint()
        try:
            start = "insert linestart"
            bullet = "• "
            if self.editor.get(start, f"{start}+2c") == bullet:
                self.editor.delete(start, f"{start}+2c")
            else:
                self.editor.insert(start, bullet)
        except tk.TclError: pass
        self._checkpoint()

    def pick_text_color(self):
        c = colorchooser.askcolor()[1]
        if c:
            self._note_format_activity()
            self._checkpoint()
            self._apply_color(c, "fg")
            self._checkpoint()

    def apply_highlight(self):
        c = colorchooser.askcolor()[1]
        if c:
            self._note_format_activity()
            self._checkpoint()
            self._apply_color(c, "bg")
            self._checkpoint()

    def _apply_color(self, color, mode):
        try:
            if not self.editor.tag_ranges("sel"):
                return
            sel_start, sel_end = self.editor.index("sel.first"), self.editor.index("sel.last")
            tag = f"color_{mode}_{color}"

            before = self._snapshot_tag_ranges(tag, sel_start, sel_end)

            self.editor.tag_add(tag, sel_start, sel_end)
            if mode == "fg":
                self.editor.tag_configure(tag, foreground=color)
            else:
                self.editor.tag_configure(tag, background=color)

            after = self._snapshot_tag_ranges(tag, sel_start, sel_end)

            def _restore(ranges):
                self.editor.tag_remove(tag, sel_start, sel_end)
                for a, b in ranges:
                    self.editor.tag_add(tag, a, b)

            self._push_fmt_action(lambda: _restore(before), lambda: _restore(after))
        except Exception:
            pass

    def clear_formatting(self):
        self._note_format_activity()
        self._checkpoint()
        try:
            if self.editor.tag_ranges("sel"):
                sel_start, sel_end = self.editor.index("sel.first"), self.editor.index("sel.last")
                tags = [t for t in self.editor.tag_names() if t != "sel"]

                before = {t: self._snapshot_tag_ranges(t, sel_start, sel_end) for t in tags}

                for t in tags:
                    self.editor.tag_remove(t, sel_start, sel_end)

                def _restore(state):
                    for t in tags:
                        self.editor.tag_remove(t, sel_start, sel_end)
                    for t, ranges in state.items():
                        for a, b in ranges:
                            self.editor.tag_add(t, a, b)

                self._push_fmt_action(lambda: _restore(before), lambda: _restore({}))
        except Exception:
            pass
        self._checkpoint()

    def set_line_spacing(self, val):
        self._checkpoint()
        px = 0
        if val == 1.5: px = 6
        elif val == 2.0: px = 14
        self.editor.configure(spacing2=px)
        self._checkpoint()

    def apply_font_family(self, name):
        self._checkpoint()
        self.default_font = name
        self.update_font_visuals()
        self._checkpoint()

    def apply_font_size(self, size):
        self._checkpoint()
        self.default_size = int(size)
        self.update_font_visuals()
        self._checkpoint()

    def set_zoom(self, val):
        self.zoom_level = int(val)
        self.update_font_visuals()

    def update_font_visuals(self):
        size = int((self.default_size * self.zoom_level) / 100)
        if size < 1: size = 1
        pad = int(50 * (self.zoom_level / 100))
        self.editor.configure(font=(self.default_font, size))
        self.editor.configure(padx=pad, pady=pad)
