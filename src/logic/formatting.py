import re
import hashlib
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


        # Metadata for each combined-style tag so per-range size changes don't affect the whole document
        # and style (bold/italic/etc.) can be preserved across font size/family changes.
        # tag_name -> {family:str, size:int(base@100%), b:bool, i:bool, u:bool, o:bool}
        self._style_meta = {}

        # Typing-mode formatting: when user clicks Bold/Italic (or changes size/family)
        # with NO selection, newly typed characters inherit this spec.
        #
        # We implement this by capturing the insert position on KeyPress and, after
        # Tk inserts text, applying a combined style tag to the newly inserted range.
        # This makes "click Bold, then type" work reliably (including across lines).
        self._typing_spec = None
        self._typing_enabled = False

        try:
            self.editor.bind('<KeyPress>', self._on_keypress_capture_insert, add=True)
            self.editor.bind('<<Paste>>', self._on_paste_capture_insert, add=True)
        except Exception:
            pass

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
        try:
            self.editor.edit_separator()
        except tk.TclError:
            pass

    # --- Helpers for combined font-spec tags (family/size + bold/italic/underline/overstrike) ---

    def _scaled_size(self, base_size: int) -> int:
        # Convert a base font size (at 100% zoom) into the current zoom-scaled size.
        try:
            z = int(self.zoom_level) if self.zoom_level else 100
        except Exception:
            z = 100
        sz = int(round(base_size * (z / 100.0)))
        return max(1, sz)

    def _get_effective_spec_at(self, index: str):
        # Return the effective (family, base_size, b,i,u,o) at a given index.
        b, i, u, o = self._get_style_flags_at(index)
        try:
            tags = self.editor.tag_names(index)
        except Exception:
            tags = ()

        for t in tags:
            if not t.startswith(STYLE_TAG_PREFIX):
                continue
            meta = self._style_meta.get(t)
            if meta:
                return {
                    'family': meta['family'],
                    'size': meta['size'],
                    'b': meta['b'],
                    'i': meta['i'],
                    'u': meta['u'],
                    'o': meta['o'],
                }
            fnt = self._style_fonts.get(t)
            if fnt:
                try:
                    base_sz = int(round(int(fnt.cget('size')) * 100 / max(1, int(self.zoom_level or 100))))
                except Exception:
                    base_sz = self.default_size
                return {
                    'family': fnt.cget('family'),
                    'size': base_sz,
                    'b': b,
                    'i': i,
                    'u': u,
                    'o': o,
                }

        # Default (unstyled) spec
        return {
            'family': self.default_font,
            'size': self.default_size,
            'b': False,
            'i': False,
            'u': False,
            'o': False,
        }

    def _apply_spec_to_range(self, spec: dict, start: str, end: str):
        # Remove any existing style tags and apply a single combined tag for this spec.
        new_tag = self._ensure_style_tag(
            family=spec['family'],
            size=int(spec['size']),
            b=bool(spec['b']),
            italic=bool(spec['i']),
            underline=bool(spec['u']),
            overstrike=bool(spec['o']),
        )
        self._remove_style_tags_in_range(start, end)
        self.editor.tag_add(new_tag, start, end)

    def _is_default_spec(self, spec: dict) -> bool:
        """Return True if spec is the plain/default font with no styles."""
        try:
            return (
                spec.get('family') == self.default_font
                and int(spec.get('size')) == int(self.default_size)
                and not spec.get('b')
                and not spec.get('i')
                and not spec.get('u')
                and not spec.get('o')
            )
        except Exception:
            return False

    def _style_boundaries_in_range(self, start: str, end: str):
        """Return sorted boundary indices where the effective style may change."""
        bounds = {self.editor.index(start), self.editor.index(end)}
        for t in self.editor.tag_names():
            if not t.startswith(STYLE_TAG_PREFIX):
                continue
            for a, b in self._snapshot_tag_ranges(t, start, end):
                bounds.add(self.editor.index(a))
                bounds.add(self.editor.index(b))

        def _key(ix: str):
            ix = self.editor.index(ix)
            ln, col = ix.split('.')
            return (int(ln), int(col))

        return sorted(bounds, key=_key)

    def _iter_style_segments(self, start: str, end: str):
        """Yield (seg_start, seg_end, spec) for each contiguous style segment."""
        bounds = self._style_boundaries_in_range(start, end)
        for i in range(len(bounds) - 1):
            s = bounds[i]
            e = bounds[i + 1]
            try:
                if self.editor.compare(s, '<', e):
                    yield s, e, self._get_effective_spec_at(s)
            except tk.TclError:
                continue

    def _on_keypress_capture_insert(self, evt=None):
        """Capture the insertion start on KeyPress and style the inserted range.

        This is the key fix for: "I want Bold/Italic selected BEFORE I type".

        Tk inserts text *after* KeyPress handlers run. We therefore record the
        current insert index and apply the active typing style on the next idle
        loop once the text has been inserted.
        """
        if not self._typing_enabled or not self._typing_spec:
            return

        try:
            before = self.editor.index('insert')
        except tk.TclError:
            return

        # Apply after Tk has performed the default key action.
        try:
            self.editor.after_idle(lambda: self._apply_typing_to_newly_inserted(before))
        except Exception:
            pass

    def _on_paste_capture_insert(self, evt=None):
        """Ensure paste operations also inherit the typing style."""
        if not self._typing_enabled or not self._typing_spec:
            return
        try:
            before = self.editor.index('insert')
        except tk.TclError:
            return
        try:
            self.editor.after_idle(lambda: self._apply_typing_to_newly_inserted(before))
        except Exception:
            pass

    def _apply_typing_to_newly_inserted(self, before_index: str):
        """Apply typing style to the range inserted since before_index."""
        if not self._typing_enabled or not self._typing_spec:
            return
        try:
            after = self.editor.index('insert')
        except tk.TclError:
            return

        # Only apply if text was inserted (insert moved forward).
        try:
            if not self.editor.compare(after, '>', before_index):
                return
        except tk.TclError:
            return

        try:
            self._apply_spec_to_range(self._typing_spec, before_index, after)
        except Exception:
            pass

    def _refresh_style_fonts(self):
        # Recompute tag font sizes when zoom changes so styled text scales consistently.
        for t, fnt in list(self._style_fonts.items()):
            meta = self._style_meta.get(t)
            if not meta:
                continue
            try:
                fnt.configure(size=self._scaled_size(int(meta['size'])))
            except Exception:
                pass
    def toggle_format(self, tag):
        """Toggle a font style tag (bold/italic/underline/overstrike).

        Fixes two common issues:
        - Bold/Italic should work with NO selection (affects subsequent typing).
        - Toggling one style should not wipe the others.
        """
        self._note_format_activity()
        self._checkpoint()

        if tag not in {'bold','italic','underline','overstrike'}:
            return

        try:
            has_sel = bool(self.editor.tag_ranges('sel'))

            if has_sel:
                start, end = self.editor.index('sel.first'), self.editor.index('sel.last')
                before = self._snapshot_style_ranges(start, end)

                # Split the selection into contiguous style segments so we don't
                # wipe out mixed formatting. Each segment toggles independently.
                segments = list(self._iter_style_segments(start, end))

                # Clear existing style tags once, then re-apply combined tags.
                self._remove_style_tags_in_range(start, end)
                for s, e, spec in segments:
                    spec = dict(spec)
                    if tag == 'bold':
                        spec['b'] = not spec['b']
                    elif tag == 'italic':
                        spec['i'] = not spec['i']
                    elif tag == 'underline':
                        spec['u'] = not spec['u']
                    elif tag == 'overstrike':
                        spec['o'] = not spec['o']

                    tname = self._ensure_style_tag(
                        family=spec['family'],
                        size=int(spec['size']),
                        b=bool(spec['b']),
                        italic=bool(spec['i']),
                        underline=bool(spec['u']),
                        overstrike=bool(spec['o']),
                    )
                    self.editor.tag_add(tname, s, e)
                after = self._snapshot_style_ranges(start, end)

                def _restore(snapshot):
                    self._remove_style_tags_in_range(start, end)
                    for tname, ranges in snapshot.items():
                        for a, b2 in ranges:
                            self.editor.tag_add(tname, a, b2)

                self._push_fmt_action(lambda: _restore(before), lambda: _restore(after))

            else:
                # No selection: enable typing-mode formatting.
                self._typing_enabled = True
                # Use the character to the left of the cursor as the current context if possible.
                try:
                    left_idx = self.editor.index('insert-1c')
                    if self.editor.compare(left_idx, '<', '1.0'):
                        raise ValueError
                    base = self._get_effective_spec_at(left_idx)
                except Exception:
                    base = {
                        'family': self.default_font,
                        'size': self.default_size,
                        'b': False,
                        'i': False,
                        'u': False,
                        'o': False,
                    }

                # If we already have a typing spec, start from it.
                if self._typing_spec:
                    base = dict(self._typing_spec)

                if tag == 'bold':
                    base['b'] = not base['b']
                elif tag == 'italic':
                    base['i'] = not base['i']
                elif tag == 'underline':
                    base['u'] = not base['u']
                elif tag == 'overstrike':
                    base['o'] = not base['o']

                # If the resulting spec is the plain default, disable typing-mode
                # so we don't add unnecessary tags while typing.
                if self._is_default_spec(base):
                    self._typing_spec = None
                    self._typing_enabled = False
                else:
                    self._typing_spec = base

        except tk.TclError:
            pass

        self._checkpoint()
    def _style_tag_name(self, *, family: str, size: int, b: bool, italic: bool, underline: bool, overstrike: bool) -> str:
        # Include family+base-size in the tag name so different size runs don't collide.
        safe = re.sub(r'[^A-Za-z0-9]+', '-', family).strip('-') or 'font'
        fam_hash = hashlib.md5(family.encode('utf-8')).hexdigest()[:6]
        bits = (
            'b1' if b else 'b0',
            'i1' if italic else 'i0',
            'u1' if underline else 'u0',
            'o1' if overstrike else 'o0',
        )
        return f"{STYLE_TAG_PREFIX}f{safe}{fam_hash}_s{int(size)}_" + '_'.join(bits)
    def _ensure_style_tag(self, *, family: str, size: int, b: bool, italic: bool, underline: bool, overstrike: bool) -> str:
        # Create (if needed) and return a combined-style tag name.
        name = self._style_tag_name(family=family, size=size, b=b, italic=italic, underline=underline, overstrike=overstrike)
        if name in self._style_fonts:
            return name

        f = font.Font(
            family=family,
            size=self._scaled_size(int(size)),
            weight='bold' if b else 'normal',
            slant='italic' if italic else 'roman',
            underline=1 if underline else 0,
            overstrike=1 if overstrike else 0,
        )
        self._style_fonts[name] = f
        self._style_meta[name] = {
            'family': family,
            'size': int(size),
            'b': bool(b),
            'i': bool(italic),
            'u': bool(underline),
            'o': bool(overstrike),
        }
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
        except tk.TclError:
            pass
        self._checkpoint()

    def toggle_list(self):
        """Toggle bullets for the current line or selected lines.

        - If all selected (non-empty) lines are already bulleted, remove bullets.
        - Otherwise, add bullets (preserving any existing indentation).
        - When adding bullets, strip an existing numbered prefix (e.g., "1. ").
        """
        bullet = "• "
        num_re = re.compile(r"^(?P<num>\d+)\.\s+")
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
                tail = txt[indent:]
                is_b = tail.startswith(bullet)
                m = num_re.match(tail)
                num_len = len(m.group(0)) if m else 0
                return ls, le, txt, indent, is_b, num_len

            # Determine whether we should add or remove bullets.
            relevant = []
            all_bulleted = True
            for ln in line_nos:
                ls, le, txt, indent, is_b, num_len = _line_info(ln)
                if txt.strip() == "":
                    # ignore empty lines for the toggle decision
                    relevant.append((ls, le, txt, indent, is_b, num_len))
                    continue
                relevant.append((ls, le, txt, indent, is_b, num_len))
                if not is_b:
                    all_bulleted = False

            # Apply
            for ls, le, txt, indent, is_b, num_len in reversed(relevant):
                # reverse so index math doesn't shift earlier lines
                insert_at = f"{ls}+{indent}c"
                if all_bulleted:
                    if is_b:
                        self.editor.delete(insert_at, f"{insert_at}+{len(bullet)}c")
                else:
                    if txt.strip() != "" and not is_b:
                        # Convert numbered list items into bullets when toggling.
                        if num_len:
                            self.editor.delete(insert_at, f"{insert_at}+{num_len}c")
                        self.editor.insert(insert_at, bullet)
        except tk.TclError:
            pass

        self._checkpoint()

    def toggle_numbered_list(self):
        """Toggle numbered list for the current line or selected lines.

        - If all selected (non-empty) lines are already numbered, remove numbering.
        - Otherwise, add numbering starting at 1 (skipping empty lines).
        - When adding numbering, strip an existing bullet prefix ("• ").
        """
        bullet = "• "
        num_re = re.compile(r"^(?P<num>\d+)\.\s+")
        self._checkpoint()

        try:
            if self.editor.tag_ranges("sel"):
                start, end = self.editor.index("sel.first"), self.editor.index("sel.last")
            else:
                start = self.editor.index("insert linestart")
                end = self.editor.index("insert lineend")

            line_nos = list(self._each_line_in_range(start, end))

            items = []  # (ls, txt, indent, is_num, num_len, is_bullet)
            all_numbered = True

            for ln in line_nos:
                ls = f"{ln}.0"
                le = f"{ln}.0 lineend"
                txt = self.editor.get(ls, le)

                indent = 0
                while indent < len(txt) and txt[indent] in (" ", "\t"):
                    indent += 1

                if txt.strip() == "":
                    items.append((ls, txt, indent, False, 0, False))
                    continue

                tail = txt[indent:]
                m = num_re.match(tail)
                is_num = bool(m)
                num_len = len(m.group(0)) if m else 0
                is_b = tail.startswith(bullet)
                items.append((ls, txt, indent, is_num, num_len, is_b))

                if not is_num:
                    all_numbered = False

            if all_numbered:
                # Remove numbering.
                for ls, txt, indent, is_num, num_len, is_b in reversed(items):
                    if txt.strip() == "" or not is_num:
                        continue
                    at = f"{ls}+{indent}c"
                    self.editor.delete(at, f"{at}+{num_len}c")
                return

            # Add numbering sequentially.
            n = 1
            for ls, txt, indent, is_num, num_len, is_b in reversed(items):
                if txt.strip() == "":
                    continue
                # We build in reverse, so compute number by counting later; easiest is two-pass.

            # Two-pass for stable numbering order
            numbers_by_ls = {}
            n = 1
            for ls, txt, indent, is_num, num_len, is_b in items:
                if txt.strip() == "":
                    continue
                numbers_by_ls[ls] = n
                n += 1

            for ls, txt, indent, is_num, num_len, is_b in reversed(items):
                if txt.strip() == "":
                    continue

                at = f"{ls}+{indent}c"

                # Strip bullet/number prefixes before applying numbering.
                if is_b:
                    self.editor.delete(at, f"{at}+{len(bullet)}c")
                if is_num and num_len:
                    self.editor.delete(at, f"{at}+{num_len}c")

                self.editor.insert(at, f"{numbers_by_ls[ls]}. ")

        except tk.TclError:
            pass
        finally:
            self._checkpoint()

    def handle_return_key(self, _evt=None):
        """Continue bullet and numbered lists on Enter.

        Bullets:
        - If the current line is a bullet item, Enter inserts a new bullet.
        - If the current line is an *empty* bullet item (just the bullet), Enter
          exits the list by removing the bullet.

        Numbered:
        - If the current line is numbered (e.g., "3. "), Enter inserts the next
          number.
        - If the current line is an *empty* numbered item, Enter exits the list.
        """
        bullet = "• "
        num_re = re.compile(r"^(?P<num>\d+)\.\s+")

        try:
            line_start = self.editor.index("insert linestart")
            line_end = self.editor.index("insert lineend")
            line_text = self.editor.get(line_start, line_end)

            # Preserve indentation (tabs/spaces exactly)
            indent = 0
            while indent < len(line_text) and line_text[indent] in (" ", "\t"):
                indent += 1
            indent_str = line_text[:indent]
            tail = line_text[indent:]

            insert_pos = self.editor.index("insert")

            # Bullet continuation
            if tail.startswith(bullet):
                after_prefix = tail[len(bullet):]

                # If line is just an empty bullet, remove bullet and insert newline.
                if after_prefix.strip() == "" and self.editor.compare(insert_pos, ">=", line_end):
                    at = f"{line_start}+{indent}c"
                    self.editor.delete(at, f"{at}+{len(bullet)}c")
                    self.editor.insert("insert", "\n")
                    return "break"

                self.editor.insert("insert", "\n" + indent_str + bullet)
                return "break"

            # Numbered continuation
            m = num_re.match(tail)
            if m:
                prefix_len = len(m.group(0))
                cur_num = int(m.group("num"))
                after_prefix = tail[prefix_len:]

                if after_prefix.strip() == "" and self.editor.compare(insert_pos, ">=", line_end):
                    at = f"{line_start}+{indent}c"
                    self.editor.delete(at, f"{at}+{prefix_len}c")
                    self.editor.insert("insert", "\n")
                    return "break"

                self.editor.insert("insert", "\n" + indent_str + f"{cur_num + 1}. ")
                return "break"

            return None
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

        # Tk Text widget spacing behavior:
        # - spacing2: extra space between *wrapped display lines* of the same logical line
        # - spacing3: extra space after each logical line (i.e., after every newline)
        #
        # Your editor uses wrap=tk.WORD, but users typically insert explicit newlines.
        # If we only set spacing2, line spacing looks like it "does nothing" unless a
        # paragraph wraps. Setting spacing3 as well makes spacing visible for normal
        # newline-separated lines *and* for wrapped lines.
        extra = max(0, int(round(line_px * max(0.0, val - 1.0))))
        self.editor.configure(spacing1=0, spacing2=extra, spacing3=extra)

        self._checkpoint()
    def apply_font_family(self, name):
        self._note_format_activity()
        self._checkpoint()
        try:
            if self.editor.tag_ranges('sel'):
                start, end = self.editor.index('sel.first'), self.editor.index('sel.last')
                before = self._snapshot_style_ranges(start, end)
                segments = list(self._iter_style_segments(start, end))
                self._remove_style_tags_in_range(start, end)
                for s, e, spec in segments:
                    spec = dict(spec)
                    spec['family'] = name
                    tname = self._ensure_style_tag(
                        family=spec['family'],
                        size=int(spec['size']),
                        b=bool(spec['b']),
                        italic=bool(spec['i']),
                        underline=bool(spec['u']),
                        overstrike=bool(spec['o']),
                    )
                    self.editor.tag_add(tname, s, e)
                after = self._snapshot_style_ranges(start, end)

                def _restore(snapshot):
                    self._remove_style_tags_in_range(start, end)
                    for tname, ranges in snapshot.items():
                        for a, b2 in ranges:
                            self.editor.tag_add(tname, a, b2)

                self._push_fmt_action(lambda: _restore(before), lambda: _restore(after))
                return
        except Exception:
            pass

        # No selection -> set typing/default font for future typing (do NOT resize existing text)
        self.default_font = name
        # enable typing mode so the next characters inherit the font
        base = dict(self._typing_spec) if self._typing_spec else {
            'family': self.default_font,
            'size': self.default_size,
            'b': False,
            'i': False,
            'u': False,
            'o': False,
        }
        base['family'] = name
        self._typing_spec = base
        self._typing_enabled = True
        self._checkpoint()

    def apply_font_size(self, size):
        self._note_format_activity()
        self._checkpoint()
        try:
            size = int(size)
        except Exception:
            size = self.default_size

        try:
            if self.editor.tag_ranges('sel'):
                start, end = self.editor.index('sel.first'), self.editor.index('sel.last')
                before = self._snapshot_style_ranges(start, end)
                segments = list(self._iter_style_segments(start, end))
                self._remove_style_tags_in_range(start, end)
                for s, e, spec in segments:
                    spec = dict(spec)
                    spec['size'] = size
                    tname = self._ensure_style_tag(
                        family=spec['family'],
                        size=int(spec['size']),
                        b=bool(spec['b']),
                        italic=bool(spec['i']),
                        underline=bool(spec['u']),
                        overstrike=bool(spec['o']),
                    )
                    self.editor.tag_add(tname, s, e)
                after = self._snapshot_style_ranges(start, end)

                def _restore(snapshot):
                    self._remove_style_tags_in_range(start, end)
                    for tname, ranges in snapshot.items():
                        for a, b2 in ranges:
                            self.editor.tag_add(tname, a, b2)

                self._push_fmt_action(lambda: _restore(before), lambda: _restore(after))
                return
        except Exception:
            pass

        # No selection -> set typing/default size for future typing (do NOT resize existing text)
        self.default_size = size
        base = dict(self._typing_spec) if self._typing_spec else {
            'family': self.default_font,
            'size': self.default_size,
            'b': False,
            'i': False,
            'u': False,
            'o': False,
        }
        base['size'] = size
        self._typing_spec = base
        self._typing_enabled = True
        self._checkpoint()

    def set_zoom(self, val):
        self.zoom_level = int(val)
        self.update_font_visuals()

    def update_font_visuals(self):
        size = int((self.default_size * self.zoom_level) / 100)
        if size < 1:
            size = 1
        pad = int(50 * (self.zoom_level / 100))
        self.editor.configure(font=(self.default_font, size))
        self.editor.configure(padx=pad, pady=pad)
        try:
            self._refresh_style_fonts()
        except Exception:
            pass
