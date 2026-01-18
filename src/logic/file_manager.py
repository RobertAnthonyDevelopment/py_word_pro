import os
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

class FileManager:
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.current_file_path = None

    def open_file(self):
        file_types = [("Text/Word", "*.txt *.docx"), ("All", "*.*")]
        path = filedialog.askopenfilename(filetypes=file_types)
        if not path: return

        try:
            content = ""
            if path.endswith(".docx") and HAS_DOCX:
                doc = Document(path)
                content = "\n".join([p.text for p in doc.paragraphs])
            else:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

            self.editor.delete("1.0", tk.END)
            self.editor.insert(tk.END, content)
            
            # Update state ONLY on success
            self.current_file_path = path
            self.root.title(f"PyWord Pro - {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")

    def save_file(self):
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
                self.root.title(f"PyWord Pro - {os.path.basename(path)}")

    def _write_file(self, path):
        try:
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
        messagebox.showinfo("PDF", "PDF Export requires FPDF library.")