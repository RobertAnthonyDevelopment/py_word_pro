import os
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# Optional PDF export dependency
try:
    # Works with both PyFPDF (fpdf) and fpdf2
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# Optional PDF import dependency (for opening PDFs as editable text)
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

try:
    from pypdf import PdfReader  # fallback
    HAS_PYPDF = True
except Exception:
    HAS_PYPDF = False

class FileManager:
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.current_file_path = None
        # If the last opened document came from a PDF, we treat it as an
        # imported text document (not safe to overwrite the original PDF).
        self._opened_from_pdf = False

    def open_file(self):
        file_types = [
            ("Supported", "*.txt *.docx *.pdf"),
            ("Text", "*.txt"),
            ("Word", "*.docx"),
            ("PDF", "*.pdf"),
            ("All", "*.*"),
        ]
        path = filedialog.askopenfilename(filetypes=file_types)
        if not path: return

        try:
            content = ""
            ext = os.path.splitext(path)[1].lower()

            if ext == ".docx" and HAS_DOCX:
                doc = Document(path)
                content = "\n".join([p.text for p in doc.paragraphs])
                self._opened_from_pdf = False
                self.current_file_path = path
                self.root.title(f"PyWord Pro - {os.path.basename(path)}")

            elif ext == ".pdf":
                content = self._read_pdf_as_text(path)
                self._opened_from_pdf = True
                # Don't allow "Save" to overwrite a PDF with plain text.
                # Force users to Save As (txt/docx) or Export PDF.
                self.current_file_path = None
                self.root.title(f"PyWord Pro - {os.path.basename(path)} (PDF Imported)")
            else:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                self._opened_from_pdf = False
                self.current_file_path = path
                self.root.title(f"PyWord Pro - {os.path.basename(path)}")

            self.editor.delete("1.0", tk.END)
            self.editor.insert(tk.END, content)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")

    def save_file(self):
        # If content came from a PDF import, we can't safely overwrite the
        # original PDF with plain text.
        if self._opened_from_pdf:
            messagebox.showinfo(
                "Save",
                "This document was imported from a PDF.\n\n"
                "Use 'Save As' to save as .txt/.docx, or use 'Export PDF' to create a new PDF.",
            )
            self.save_as_file()
            return

        if self.current_file_path:
            self._write_file(self.current_file_path)
        else:
            self.save_as_file()

    def save_as_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text", "*.txt"), ("Word", "*.docx")])
        if path:
            if self._write_file(path):
                self.current_file_path = path
                self._opened_from_pdf = False
                self.root.title(f"PyWord Pro - {os.path.basename(path)}")

    def _write_file(self, path):
        try:
            # Prevent corrupting a PDF by saving plain text to a .pdf path.
            if os.path.splitext(path)[1].lower() == ".pdf":
                messagebox.showinfo(
                    "Save",
                    "To save as a PDF, use 'Export PDF' instead of 'Save'.",
                )
                return False

            content = self.editor.get("1.0", tk.END)
            if path.endswith(".docx") and HAS_DOCX:
                doc = Document()
                doc.add_paragraph(content)
                doc.save(path)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            return True
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            return False

    def export_pdf(self):
        """Export the current editor text to a PDF file."""
        if not HAS_FPDF:
            messagebox.showinfo(
                "PDF",
                "PDF export requires the 'fpdf' package.\n\nInstall it with: pip install fpdf",
            )
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return

        try:
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

            pdf.output(path)
            messagebox.showinfo("PDF", f"Exported PDF successfully:\n{path}")
        except Exception as e:
            messagebox.showerror("PDF Export Error", str(e))

    def _read_pdf_as_text(self, path: str) -> str:
        """Extract readable text from a PDF.

        This is NOT full PDF editing. We import the PDF's text into the editor.
        Layout, images, and complex formatting won't be preserved.
        """
        # Preferred: PyMuPDF
        if HAS_PYMUPDF:
            try:
                doc = fitz.open(path)
                parts = []
                for page in doc:
                    parts.append(page.get_text("text"))
                doc.close()
                text = "\n\n".join([p.strip("\n") for p in parts]).strip()
                if text:
                    return text
            except Exception:
                pass

        # Fallback: pypdf
        if HAS_PYPDF:
            try:
                reader = PdfReader(path)
                parts = []
                for page in reader.pages:
                    parts.append(page.extract_text() or "")
                text = "\n\n".join([p.strip("\n") for p in parts]).strip()
                if text:
                    return text
            except Exception:
                pass

        # If we reached here, we couldn't extract any text.
        if not (HAS_PYMUPDF or HAS_PYPDF):
            raise RuntimeError(
                "PDF import requires 'pymupdf' (recommended) or 'pypdf'.\n"
                "Install one of them:\n  pip install pymupdf\n  pip install pypdf"
            )

        return (
            "[No extractable text found in this PDF]\n\n"
            "This often happens when the PDF is scanned images (not selectable text).\n"
            "If you need to edit a scanned PDF, you'd need OCR support."
        )
