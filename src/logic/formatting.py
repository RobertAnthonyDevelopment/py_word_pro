import tkinter as tk
from tkinter import font, colorchooser


STYLE_TAG_PREFIX = "pw_fontstyle_"  # internal
PARA_SPACE_TAG_PREFIX = "pw_para_space_"  # internal

class FormatManager:
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.zoom_level = 100
        self.default_font = "Calibri"
        self.default_size = 11

        # Keep references to any dynamically created Tk Font objects used in
        # tag configurations so they don't get garbage collected.
        self._style_fonts = {}  # tag_name -> tkinter.font.Font

        # Current paragraph line spacing multiplier (1.0 = single spacing)
        self._line_spacing = 1.0

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
        """Toggle a font style tag (bold/italic/underline/overstrike).

        NOTE: The old approach used *separate* Tk tags for each style and
        reconfigured each tag with a full font descriptor. That caused styles
        to clobber each other (e.g., bold -> italic would reset weight).

        The new approach uses a single *combined* style tag for each unique
        combination of (bold, italic, underline, overstrike), so toggling one
        style preserves the others.
        """
        self._note_format_activity()
        self._checkpoint()

        if tag not in {"bold", "italic", "underline", "overstrike"}:
            return

        try:
            if not self.editor.tag_ranges("sel"):
                # No selection: apply to the current word/line character so the
                # user sees an immediate effect. This also makes subsequent
                # typing inherit the style in most cases (Tk copies tags from
                # the char to the left of the insert mark).
                start = self.editor.index("insert")
                end = self.editor.index("insert +1c")
                if self.editor.compare(end, ">", "end-1c"):
                    end = self.editor.index("end-1c")
                if self.editor.compare(start, "==", end):
                    return
            else:
                start, end = self.editor.index("sel.first"), self.editor.index("sel.last")

            before = self._snapshot_style_ranges(start, end)

            # Determine current style flags at start.
            b, i, u, o = self._get_style_flags_at(start)
            if tag == "bold":
                b = not b
            elif tag == "italic":
                i = not i
            elif tag == "underline":
                u = not u
            elif tag == "overstrike":
                o = not o

            new_style_tag = self._ensure_style_tag(b=b, italic=i, underline=u, overstrike=o)

            # Replace any existing style tags with the new combined tag.
            self._remove_style_tags_in_range(start, end)
            self.editor.tag_add(new_style_tag, start, end)

            after = self._snapshot_style_ranges(start, end)

            def _restore(snapshot):
                self._remove_style_tags_in_range(start, end)
                for tname, ranges in snapshot.items():
                    for a, b2 in ranges:
                        self.editor.tag_add(tname, a, b2)

            self._push_fmt_action(lambda: _restore(before), lambda: _restore(after))
        except tk.TclError:
            pass

        self._checkpoint()

    def _style_tag_name(self, *, b: bool, italic: bool, underline: bool, overstrike: bool) -> str:
        bits = (
            "b1" if b else "b0",
            "i1" if italic else "i0",
            "u1" if underline else "u0",
            "o1" if overstrike else "o0",
        )
        return STYLE_TAG_PREFIX + "_".join(bits)

    def _ensure_style_tag(self, *, b: bool, italic: bool, underline: bool, overstrike: bool) -> str:
        """Create (if needed) and return a combined-style tag name."""
        name = self._style_tag_name(b=b, italic=italic, underline=underline, overstrike=overstrike)
        if name in self._style_fonts:
            return name

        base = font.Font(font=self.editor.cget("font"))
        f = font.Font(
            family=base.cget("family"),
            size=base.cget("size"),
            weight="bold" if b else "normal",
            slant="italic" if italic else "roman",
            underline=1 if underline else 0,
            overstrike=1 if overstrike else 0,
        )
        self._style_fonts[name] = f
        self.editor.tag_configure(name, font=f)
        return name

    def _get_style_flags_at(self, index: str):
        """Return (bold, italic, underline, overstrike) for the first style tag at index."""
        try:
            tags = self.editor.tag_names(index)
        except tk.TclError:
            return False, False, False, False

        for t in tags:
            if not t.startswith(STYLE_TAG_PREFIX):
                continue
            # Parse bits from the tag name.
            parts = t[len(STYLE_TAG_PREFIX):].split("_")
            bits = {p[:1]: p[1:] for p in parts if len(p) == 2}
            return (
                bits.get("b") == "1",
                bits.get("i") == "1",
                bits.get("u") == "1",
                bits.get("o") == "1",
            )

        # Fall back to legacy tags if present (older docs/sessions).
        return (
            "bold" in tags,
            "italic" in tags,
            "underline" in tags,
            "overstrike" in tags,
        )

    def _remove_style_tags_in_range(self, start: str, end: str):
        for t in list(self.editor.tag_names()):
            if t.startswith(STYLE_TAG_PREFIX):
                self.editor.tag_remove(t, start, end)
        # Remove legacy tags too so we don't get mixed behavior.
        for t in ("bold", "italic", "underline", "overstrike"):
            try:
                self.editor.tag_remove(t, start, end)
            except tk.TclError:
                pass

    def _snapshot_style_ranges(self, start: str, end: str):
        """Snapshot all combined-style tag ranges intersecting [start, end]."""
        snap = {}
        for t in self.editor.tag_names():
            if t.startswith(STYLE_TAG_PREFIX):
                ranges = self._snapshot_tag_ranges(t, start, end)
                if ranges:
                    snap[t] = ranges
        # Include legacy tags if they exist.
        for t in ("bold", "italic", "underline", "overstrike"):
            ranges = self._snapshot_tag_ranges(t, start, end)
            if ranges:
                snap[t] = ranges
        return snap

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
        """Toggle bullets for the current line or selected lines.

        - If all selected lines are already bulleted, remove bullets.
        - Otherwise, add bullets (preserving any existing indentation).
        """
        bullet = "• "
        self._checkpoint()

        try:
            if self.editor.tag_ranges("sel"):
                start, end = self.editor.index("sel.first"), self.editor.index("sel.last")
            else:
                start = self.editor.index("insert linestart")
                end = self.editor.index("insert lineend")

            line_nos = list(self._each_line_in_range(start, end))

            def _line_info(ln: int):
                ls = f"{ln}.0"
                le = f"{ln}.0 lineend"
                txt = self.editor.get(ls, le)
                # preserve indentation
                indent = 0
                while indent < len(txt) and txt[indent] in (" ", "\t"):
                    indent += 1
                return ls, le, txt, indent

            # Determine whether we should add or remove bullets.
            relevant = []
            all_bulleted = True
            for ln in line_nos:
                ls, le, txt, indent = _line_info(ln)
                if txt.strip() == "":
                    # ignore empty lines for the toggle decision
                    relevant.append((ls, le, txt, indent, False))
                    continue
                is_b = txt[indent:].startswith(bullet)
                relevant.append((ls, le, txt, indent, is_b))
                if not is_b:
                    all_bulleted = False

            # Apply
            for ls, le, txt, indent, is_b in reversed(relevant):
                # reverse so index math doesn't shift earlier lines
                insert_at = f"{ls}+{indent}c"
                if all_bulleted:
                    if is_b:
                        self.editor.delete(insert_at, f"{insert_at}+{len(bullet)}c")
                else:
                    if txt.strip() != "" and not is_b:
                        self.editor.insert(insert_at, bullet)
        except tk.TclError:
            pass

        self._checkpoint()

    def handle_return_key(self, _evt=None):
        """Continue bullet lists on Enter.

        If the current line is a bullet item, Enter inserts a new bullet.
        If the current line is an *empty* bullet item (just the bullet), Enter
        exits the list by removing the bullet.
        """
        bullet = "• "
        try:
            line_start = self.editor.index("insert linestart")
            line_end = self.editor.index("insert lineend")
            line_text = self.editor.get(line_start, line_end)

            # Compute indentation
            indent = 0
            while indent < len(line_text) and line_text[indent] in (" ", "\t"):
                indent += 1

            if not line_text[indent:].startswith(bullet):
                return None

            after_bullet = line_text[indent + len(bullet):]
            insert_pos = self.editor.index("insert")

            # If line is just an empty bullet, remove bullet and insert newline.
            if after_bullet.strip() == "" and self.editor.compare(insert_pos, ">=", line_end):
                self.editor.delete(f"{line_start}+{indent}c", f"{line_start}+{indent + len(bullet)}c")
                self.editor.insert("insert", "\n")
                return "break"

            # Normal bullet continuation
            self.editor.insert("insert", "\n" + (" " * indent) + bullet)
            return "break"
        except tk.TclError:
            return None

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
        """Set document line spacing.

        Tk's Text widget uses pixel-based spacing (spacing1/2/3). The previous
        implementation used fixed pixel values that were too small to notice on
        many font sizes, which made the feature look "broken".

        We compute spacing based on the current font's line height so values like
        1.15x / 1.5x / 2.0x are visible and scale with zoom.
        """
        self._note_format_activity()
        self._checkpoint()

        try:
            val = float(val)
        except Exception:
            val = 1.0

        # Base line height in pixels for the current editor font.
        try:
            current_font = font.Font(font=self.editor.cget("font"))
            line_px = int(current_font.metrics("linespace"))
        except Exception:
            line_px = 14

        # spacing2 is extra space *between* display lines.
        extra = max(0, int(round(line_px * max(0.0, val - 1.0))))
        self.editor.configure(spacing1=0, spacing2=extra, spacing3=0)

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
