import os
import re
import hashlib
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

if HAS_DOCX:
    try:
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.text import WD_COLOR_INDEX
    except Exception:
        Pt = None
        RGBColor = None
        WD_ALIGN_PARAGRAPH = None
        WD_COLOR_INDEX = None

# Optional PDF export dependency
try:
    # Works with both PyFPDF (fpdf) and fpdf2
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

from src.logic.document_security import DocumentSecurityError, DocumentSecurityScanner
from src.logic.io_utils import atomic_write_file, atomic_write_text, normalize_output_path

class FileManager:
    # DOCX visual parity tuning for Word vs Tk rendering.
    DOCX_FONT_SIZE_SCALE = 0.92

    def __init__(self, editor, root, security_scanner=None):
        self.editor = editor
        self.root = root
        self.current_file_path = None
        # Keep references to dynamically-created tag fonts so Tk doesn't GC them.
        self._docx_fonts = {}
        self.security_scanner = security_scanner or DocumentSecurityScanner()

    def open_file(self):
        file_types = [("Text/Word", "*.txt *.docx"), ("All", "*.*")]
        path = filedialog.askopenfilename(filetypes=file_types)
        if not path:
            return False
        return self.open_path(path)

    def open_path(self, path):
        if not path:
            return False

        previous_text = self.editor.get("1.0", tk.END)
        ext = os.path.splitext(path)[1].lower().strip()

        try:
            if ext not in {".txt", ".docx"}:
                raise RuntimeError("Unsupported file type. Only .txt and .docx files are allowed.")
            self.security_scanner.scan_file(path, extension=ext)

            if ext == ".docx":
                if not HAS_DOCX:
                    raise RuntimeError("Cannot open .docx files because python-docx is not installed.")
                # Rich DOCX import: reconstruct formatting using Tk tags.
                self._load_docx_with_formatting(path)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.editor.delete("1.0", tk.END)
                self.editor.insert(tk.END, content)
            
            # Update state ONLY on success
            self.current_file_path = path
            self.root.title(f"PyWord Pro - {os.path.basename(path)}")
            return True
        except DocumentSecurityError as e:
            try:
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", previous_text)
            except Exception:
                pass
            messagebox.showerror("Document Security", str(e))
            return False
        except Exception as e:
            # Preserve previous content on failed open to avoid silent data loss.
            try:
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", previous_text)
            except Exception:
                pass
            messagebox.showerror("Error", f"Could not open file: {e}")
            return False

    def save_file(self):
        if self.current_file_path:
            return self._write_file(self.current_file_path)
        return self.save_as_file()

    def save_as_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text", "*.txt"), ("Word", "*.docx")])
        if path:
            try:
                target_path = normalize_output_path(path, default_extension=".txt")
            except ValueError:
                return False
            if self._write_file(target_path):
                self.current_file_path = target_path
                self.root.title(f"PyWord Pro - {os.path.basename(target_path)}")
                return True
        return False

    def _write_file(self, path):
        try:
            target_path = normalize_output_path(path, default_extension=".txt")
            ext = os.path.splitext(target_path)[1].lower().strip()
            if ext == ".docx":
                if not HAS_DOCX:
                    raise RuntimeError("Cannot save .docx files because python-docx is not installed.")
                atomic_write_file(target_path, self._export_docx_with_formatting, suffix=".docx")
            else:
                # Use end-1c to avoid persisting Tk's implicit trailing newline.
                content = self.editor.get("1.0", "end-1c")
                atomic_write_text(target_path, content, newline="")
            return True
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            return False

    def serialize_document(self, extension: str) -> bytes:
        ext = (extension or "").strip().lower()
        if ext == ".docx":
            if not HAS_DOCX:
                raise RuntimeError("Cannot export .docx because python-docx is not installed.")
            tmp_path = ""
            try:
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
                    tmp_path = handle.name
                self._export_docx_with_formatting(tmp_path)
                with open(tmp_path, "rb") as handle:
                    return handle.read()
            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

        text = self.editor.get("1.0", "end-1c")
        return text.encode("utf-8")

    def load_document_from_bytes(self, payload: bytes, extension: str, source_name: str = "Imported document") -> bool:
        ext = (extension or "").strip().lower()
        blob = payload or b""
        previous_text = self.editor.get("1.0", tk.END)
        try:
            if ext not in {".txt", ".docx"}:
                raise RuntimeError("Unsupported file type. Only .txt and .docx files are allowed.")
            self.security_scanner.scan_bytes(blob, source_name=source_name, extension=ext)
            if ext == ".docx":
                if not HAS_DOCX:
                    raise RuntimeError("Cannot open .docx because python-docx is not installed.")
                tmp_path = ""
                try:
                    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as handle:
                        tmp_path = handle.name
                        handle.write(blob)
                    self._load_docx_with_formatting(tmp_path)
                finally:
                    if tmp_path:
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
            else:
                text = blob.decode("utf-8", errors="replace")
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", text)
            self.current_file_path = None
            return True
        except DocumentSecurityError as exc:
            try:
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", previous_text)
            except Exception:
                pass
            messagebox.showerror("Document Security", str(exc))
            return False
        except Exception as exc:
            try:
                self.editor.delete("1.0", tk.END)
                self.editor.insert("1.0", previous_text)
            except Exception:
                pass
            messagebox.showerror("Open Error", f"Could not load document:\n{exc}")
            return False

    # ---------------------------
    # DOCX (Word) import/export
    # ---------------------------

    _STYLE_TAG_PREFIX = "pw_fontstyle_"

    def _index_key(self, idx: str):
        i = self.editor.index(idx)
        ln, col = i.split(".")
        return (int(ln), int(col))

    def _get_font_for_style_tag(self, tag: str):
        """Return a Tk Font for a combined style tag if available."""
        try:
            fnt_name = self.editor.tag_cget(tag, "font")
            if not fnt_name:
                return None
            return tkfont.nametofont(fnt_name)
        except Exception:
            return None

    def _get_font_for_tag(self, tag: str):
        try:
            fnt_name = self.editor.tag_cget(tag, "font")
            if not fnt_name:
                return None
            try:
                return tkfont.nametofont(fnt_name)
            except Exception:
                return tkfont.Font(font=fnt_name)
        except Exception:
            return None

    def _normalize_hex_color(self, value: str | None):
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        if re.match(r"^#?[0-9a-fA-F]{6}$", text):
            return "#" + text.lstrip("#").lower()
        try:
            red, green, blue = self.editor.winfo_rgb(text)
            return f"#{int(red / 257):02x}{int(green / 257):02x}{int(blue / 257):02x}"
        except Exception:
            return None

    def _bool_from_cget(self, value) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _template_run_spec(self, tags: set[str]):
        template_tags = [tag for tag in tags if tag.startswith("tpl_")]
        if not template_tags:
            return None

        order = {
            "tpl_placeholder": 0,
            "tpl_label": 1,
            "tpl_h1": 2,
            "tpl_h2": 3,
            "tpl_h3": 4,
            "tpl_rule": 5,
            "tpl_table": 6,
            "tpl_callout": 7,
            "tpl_bullet": 8,
            "tpl_number": 9,
            "tpl_check": 10,
            "tpl_body": 11,
        }
        template_tags.sort(key=lambda item: order.get(item, 100))

        spec = {
            "family": None,
            "size_pt": None,
            "bold": False,
            "italic": False,
            "underline": False,
            "strike": False,
            "fg": None,
            "bg": None,
        }

        for tag in template_tags:
            fnt = self._get_font_for_tag(tag)
            if fnt:
                if spec["family"] is None:
                    spec["family"] = fnt.cget("family")
                if spec["size_pt"] is None:
                    try:
                        spec["size_pt"] = abs(int(fnt.cget("size")))
                    except Exception:
                        pass
                spec["bold"] = spec["bold"] or str(fnt.cget("weight")).lower() == "bold"
                spec["italic"] = spec["italic"] or str(fnt.cget("slant")).lower() == "italic"
                spec["underline"] = spec["underline"] or self._bool_from_cget(fnt.cget("underline"))
                spec["strike"] = spec["strike"] or self._bool_from_cget(fnt.cget("overstrike"))

            try:
                spec["underline"] = spec["underline"] or self._bool_from_cget(self.editor.tag_cget(tag, "underline"))
                spec["strike"] = spec["strike"] or self._bool_from_cget(self.editor.tag_cget(tag, "overstrike"))
            except Exception:
                pass

            if spec["fg"] is None:
                spec["fg"] = self._normalize_hex_color(self.editor.tag_cget(tag, "foreground"))
            if spec["bg"] is None:
                spec["bg"] = self._normalize_hex_color(self.editor.tag_cget(tag, "background"))

        return spec

    def _parse_style_bits_from_tag(self, tag: str):
        """Parse b/i/u/o flags from combined style tag name."""
        b = i = u = o = False
        try:
            parts = tag[len(self._STYLE_TAG_PREFIX):].split("_")
            bits = {p[:1]: p[1:] for p in parts if len(p) == 2}
            b = bits.get("b") == "1"
            i = bits.get("i") == "1"
            u = bits.get("u") == "1"
            o = bits.get("o") == "1"
        except Exception:
            pass
        return b, i, u, o

    def _tags_at(self, idx: str):
        try:
            return set(self.editor.tag_names(idx))
        except tk.TclError:
            return set()

    def _tag_ranges_intersecting(self, tag: str, start: str, end: str):
        """Yield (a,b) segments of tag ranges intersecting [start,end]."""
        try:
            ranges = self.editor.tag_ranges(tag)
        except tk.TclError:
            return
        for i in range(0, len(ranges), 2):
            a = self.editor.index(ranges[i])
            b = self.editor.index(ranges[i + 1])
            # no overlap
            if self.editor.compare(b, "<=", start) or self.editor.compare(a, ">=", end):
                continue
            s = a if self.editor.compare(a, ">", start) else start
            e = b if self.editor.compare(b, "<", end) else end
            if self.editor.compare(s, "<", e):
                yield (s, e)

    def _segment_boundaries(self, start: str, end: str):
        """Compute boundaries where formatting might change within [start,end]."""
        bounds = {self.editor.index(start), self.editor.index(end)}
        all_tags = list(self.editor.tag_names())
        relevant = []
        for t in all_tags:
            if t.startswith(self._STYLE_TAG_PREFIX) or t.startswith("tpl_") or t in {"bold", "italic", "underline", "overstrike", "left", "center", "right"}:
                relevant.append(t)
            elif t.startswith("color_fg_") or t.startswith("color_bg_"):
                relevant.append(t)

        for t in relevant:
            for a, b in self._tag_ranges_intersecting(t, start, end):
                bounds.add(self.editor.index(a))
                bounds.add(self.editor.index(b))

        return sorted(bounds, key=self._index_key)

    def _effective_run_spec(self, idx: str):
        """Return effective formatting spec at idx."""
        tags = self._tags_at(idx)

        # Base font from widget
        base = tkfont.Font(font=self.editor.cget("font"))
        family = base.cget("family")
        size_pt = abs(int(base.cget("size")))

        b = i = u = o = False
        fg = None
        bg = None

        # Combined style tag wins if present.
        style_tags = [t for t in tags if t.startswith(self._STYLE_TAG_PREFIX)]
        if style_tags:
            # pick one (there should generally be one)
            st = sorted(style_tags)[0]
            fnt = self._get_font_for_style_tag(st)
            if fnt:
                family = fnt.cget("family")
                try:
                    size_pt = int(fnt.cget("size"))
                except Exception:
                    pass

            # Combined style tags encode base @100% size in their name
            # (`_s{size}_`). Prefer that for export so zoomed rendering in Tk
            # does not leak into persisted DOCX font sizes.
            try:
                m = re.search(r"_s(\d+)_", st)
                if m:
                    size_pt = int(m.group(1))
            except Exception:
                pass
            b, i, u, o = self._parse_style_bits_from_tag(st)
        else:
            # Legacy tags
            b = "bold" in tags
            i = "italic" in tags
            u = "underline" in tags
            o = "overstrike" in tags

        for t in tags:
            if t.startswith("color_fg_"):
                fg = self._normalize_hex_color(t[len("color_fg_"):])
            elif t.startswith("color_bg_"):
                bg = self._normalize_hex_color(t[len("color_bg_"):])

        template_spec = self._template_run_spec(tags)
        if template_spec:
            family = template_spec.get("family") or family
            size_pt = int(template_spec.get("size_pt") or size_pt)
            b = bool(b or template_spec.get("bold"))
            i = bool(i or template_spec.get("italic"))
            u = bool(u or template_spec.get("underline"))
            o = bool(o or template_spec.get("strike"))
            if fg is None:
                fg = template_spec.get("fg")
            if bg is None:
                bg = template_spec.get("bg")

        return {
            "family": family,
            "size_pt": size_pt,
            "size_docx_pt": max(1, int(round(float(size_pt) * float(self.DOCX_FONT_SIZE_SCALE)))),
            "bold": b,
            "italic": i,
            "underline": u,
            "strike": o,
            "fg": fg,
            "bg": bg,
        }

    def _docx_highlight_from_hex(self, hex_color: str):
        """Map a #RRGGBB to a Word highlight color (best-effort)."""
        if not hex_color or not WD_COLOR_INDEX:
            return None
        h = hex_color.lower()
        # common mappings
        mapping = {
            "#ffff00": WD_COLOR_INDEX.YELLOW,
            "#00ff00": WD_COLOR_INDEX.BRIGHT_GREEN,
            "#00ffff": WD_COLOR_INDEX.TURQUOISE,
            "#ff00ff": WD_COLOR_INDEX.PINK,
            "#0000ff": WD_COLOR_INDEX.BLUE,
            "#ff0000": WD_COLOR_INDEX.RED,
            "#000080": WD_COLOR_INDEX.DARK_BLUE,
            "#008000": WD_COLOR_INDEX.GREEN,
            "#800080": WD_COLOR_INDEX.VIOLET,
            "#008080": WD_COLOR_INDEX.TEAL,
            "#808080": WD_COLOR_INDEX.GRAY_50,
            "#c0c0c0": WD_COLOR_INDEX.GRAY_25,
            "#000000": WD_COLOR_INDEX.BLACK,
            "#ffffff": WD_COLOR_INDEX.WHITE,
        }
        return mapping.get(h)

    def _export_docx_with_formatting(self, path: str):
        """Export the current Tk editor contents to a .docx with runs."""
        if not HAS_DOCX:
            raise RuntimeError("python-docx is not installed")

        doc = Document()

        # Remove the default empty paragraph if present and we will build our own.
        try:
            if doc.paragraphs and not doc.paragraphs[0].text:
                p = doc.paragraphs[0]
                p._element.getparent().remove(p._element)
        except Exception:
            pass

        end_idx = self.editor.index("end-1c")
        total_lines = int(end_idx.split(".")[0])

        for ln in range(1, total_lines + 1):
            ls = f"{ln}.0"
            le = f"{ln}.0 lineend"

            para = doc.add_paragraph()

            # Paragraph alignment based on tag at line start.
            tags = self._tags_at(ls)
            if WD_ALIGN_PARAGRAPH:
                if "center" in tags:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif "right" in tags:
                    para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                else:
                    para.alignment = WD_ALIGN_PARAGRAPH.LEFT

            # Normalize Word's default paragraph spacing so exported documents
            # visually track the editor more closely.
            if Pt:
                try:
                    para.paragraph_format.space_before = Pt(0)
                    para.paragraph_format.space_after = Pt(0)
                except Exception:
                    pass

            # Empty line -> keep empty paragraph.
            if self.editor.compare(ls, "==", le):
                continue

            bounds = self._segment_boundaries(ls, le)
            for i in range(len(bounds) - 1):
                a = bounds[i]
                b = bounds[i + 1]
                if not self.editor.compare(a, "<", b):
                    continue
                text = self.editor.get(a, b)
                if not text:
                    continue

                spec = self._effective_run_spec(a)
                run = para.add_run(text)

                run.bold = bool(spec["bold"])
                run.italic = bool(spec["italic"])
                run.underline = bool(spec["underline"])
                run.font.strike = bool(spec["strike"])

                if Pt:
                    try:
                        run.font.size = Pt(int(spec["size_docx_pt"]))
                    except Exception:
                        pass
                try:
                    run.font.name = spec["family"]
                except Exception:
                    pass

                # Text color
                if RGBColor and spec.get("fg") and re.match(r"^#?[0-9a-fA-F]{6}$", spec["fg"]):
                    hexv = spec["fg"].lstrip("#")
                    try:
                        run.font.color.rgb = RGBColor.from_string(hexv.upper())
                    except Exception:
                        pass

                # Highlight color (best effort)
                hl = self._docx_highlight_from_hex(spec.get("bg"))
                if hl is not None:
                    try:
                        run.font.highlight_color = hl
                    except Exception:
                        pass

        doc.save(path)

    def _make_style_tag_name(self, family: str, size_pt: int, b: bool, i: bool, u: bool, o: bool):
        safe = re.sub(r"[^A-Za-z0-9]+", "-", family).strip("-") or "font"
        fam_hash = hashlib.md5(family.encode("utf-8")).hexdigest()[:6]
        bits = (
            "b1" if b else "b0",
            "i1" if i else "i0",
            "u1" if u else "u0",
            "o1" if o else "o0",
        )
        return f"{self._STYLE_TAG_PREFIX}f{safe}{fam_hash}_s{int(size_pt)}_" + "_".join(bits)

    def _ensure_style_tag(self, family: str, size_pt: int, b: bool, i: bool, u: bool, o: bool):
        tag = self._make_style_tag_name(family, size_pt, b, i, u, o)
        if tag in self._docx_fonts:
            return tag
        fnt = tkfont.Font(family=family, size=int(size_pt), weight="bold" if b else "normal", slant="italic" if i else "roman", underline=1 if u else 0, overstrike=1 if o else 0)
        self._docx_fonts[tag] = fnt
        self.editor.tag_configure(tag, font=fnt)
        return tag

    def _ensure_color_tag(self, mode: str, hex_color: str):
        tag = f"color_{mode}_{hex_color}"
        try:
            if mode == "fg":
                self.editor.tag_configure(tag, foreground=hex_color)
            else:
                self.editor.tag_configure(tag, background=hex_color)
        except Exception:
            pass
        return tag

    def _load_docx_with_formatting(self, path: str):
        """Load a .docx into the editor, reconstructing formatting tags."""
        doc = Document(path)
        self.editor.delete("1.0", tk.END)

        insert_at = "1.0"
        for pi, p in enumerate(doc.paragraphs):
            # Apply alignment tags for this paragraph.
            para_start = self.editor.index(insert_at)

            # Insert paragraph runs
            for run in p.runs:
                text = run.text or ""
                if not text:
                    continue
                start = self.editor.index(insert_at)
                self.editor.insert(insert_at, text)
                end = self.editor.index(f"{start}+{len(text)}c")

                family = run.font.name or tkfont.Font(font=self.editor.cget("font")).cget("family")
                # python-docx sizes are Length (EMU); use .pt when available
                size_pt = None
                try:
                    if run.font.size is not None:
                        size_pt = int(round(run.font.size.pt))
                except Exception:
                    size_pt = None
                if not size_pt:
                    size_pt = int(tkfont.Font(font=self.editor.cget("font")).cget("size"))

                b = bool(run.bold)
                i = bool(run.italic)
                u = bool(run.underline)
                o = bool(getattr(run.font, "strike", False))

                style_tag = self._ensure_style_tag(family, size_pt, b, i, u, o)
                self.editor.tag_add(style_tag, start, end)

                # Text color
                try:
                    if run.font.color and run.font.color.rgb:
                        hexv = "#" + str(run.font.color.rgb)
                        ct = self._ensure_color_tag("fg", hexv)
                        self.editor.tag_add(ct, start, end)
                except Exception:
                    pass

                # Highlight
                try:
                    hl = run.font.highlight_color
                    if hl is not None:
                        # Map known Word highlight to a rough hex.
                        inv = {
                            "YELLOW": "#ffff00",
                            "BRIGHT_GREEN": "#00ff00",
                            "TURQUOISE": "#00ffff",
                            "PINK": "#ff00ff",
                            "BLUE": "#0000ff",
                            "RED": "#ff0000",
                            "GREEN": "#008000",
                            "VIOLET": "#800080",
                            "TEAL": "#008080",
                            "BLACK": "#000000",
                            "WHITE": "#ffffff",
                            "GRAY_50": "#808080",
                            "GRAY_25": "#c0c0c0",
                        }
                        name = getattr(hl, "name", None) or str(hl)
                        hexv = inv.get(str(name), None)
                        if hexv:
                            bt = self._ensure_color_tag("bg", hexv)
                            self.editor.tag_add(bt, start, end)
                except Exception:
                    pass

                insert_at = end

            # Paragraph alignment tag over the whole paragraph.
            try:
                para_end = self.editor.index(insert_at)
                if p.alignment is not None:
                    if WD_ALIGN_PARAGRAPH and p.alignment == WD_ALIGN_PARAGRAPH.CENTER:
                        self.editor.tag_configure("center", justify="center")
                        self.editor.tag_add("center", para_start, para_end)
                    elif WD_ALIGN_PARAGRAPH and p.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
                        self.editor.tag_configure("right", justify="right")
                        self.editor.tag_add("right", para_start, para_end)
                    else:
                        self.editor.tag_configure("left", justify="left")
                        self.editor.tag_add("left", para_start, para_end)
            except Exception:
                pass

            # Newline between paragraphs (but not after last).
            if pi != len(doc.paragraphs) - 1:
                self.editor.insert(insert_at, "\n")
                insert_at = self.editor.index(f"{insert_at}+1c")

    def export_pdf(self):
        """Export the current editor text to a PDF file."""
        if not HAS_FPDF:
            messagebox.showinfo(
                "PDF",
                "PDF export requires the 'fpdf' package.\n\nInstall it with: pip install fpdf",
            )
            return False

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return False

        try:
            target_path = normalize_output_path(path, default_extension=".pdf")
            content = self.editor.get("1.0", tk.END).rstrip("\n")

            pdf = FPDF(format="A4", unit="mm")
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            # Built-in fonts (Helvetica/Times/Courier) are always available.
            # They are limited to latin-1; we replace unsupported chars to avoid crashes.
            pdf.set_font("Helvetica", size=12)

            for line in content.splitlines() or [""]:
                line = line.replace("\t", "    ")
                safe_line = line.encode("latin-1", "replace").decode("latin-1")
                pdf.multi_cell(0, 6, safe_line)

            atomic_write_file(target_path, lambda tmp_path: pdf.output(tmp_path), suffix=".pdf")
            messagebox.showinfo("PDF", f"Exported PDF successfully:\n{target_path}")
            return True
        except Exception as e:
            messagebox.showerror("PDF Export Error", str(e))
            return False
