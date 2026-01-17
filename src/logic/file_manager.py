import os
import tkinter as tk
from tkinter import filedialog, messagebox

# --- LIBRARY CHECKS ---
try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

class FileManager:
    def __init__(self, editor_widget, root):
        self.editor = editor_widget
        self.root = root
        # This variable is the "Source of Truth" for where the file lives.
        # It is ONLY updated upon a successful Open or successful Save As.
        self.current_file_path = None

    def open_file(self):
        """
        Opens a file and updates the workspace state ONLY if successful.
        """
        # 1. Define File Types for Mac/Windows compatibility
        patterns = ["*.txt"]
        if HAS_DOCX: patterns.append("*.docx")
        if HAS_FITZ: patterns.append("*.pdf")
        all_patterns = " ".join(patterns)
        
        file_types = [("All Supported", all_patterns), ("Text", "*.txt")]
        if HAS_DOCX: file_types.append(("Word Document", "*.docx"))
        if HAS_FITZ: file_types.append(("PDF", "*.pdf"))

        # 2. Ask User for File
        path = filedialog.askopenfilename(filetypes=file_types)
        if not path:
            return # User cancelled, do not change state

        # 3. Attempt to Read File
        # We read into a temporary variable first. We do NOT clear the editor yet.
        # This prevents losing your current work if the file you try to open is corrupted.
        content = None
        is_formatted_docx = False
        
        try:
            if path.endswith(".docx") and HAS_DOCX:
                # We handle DOCX specially to preserve formatting
                is_formatted_docx = True
            elif path.endswith(".pdf") and HAS_FITZ:
                doc = fitz.open(path)
                text = ""
                for page in doc:
                    text += page.get_text()
                content = text
            else:
                # Fallback for text files
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

            # 4. If Read was Successful, NOW we update the Editor and State
            self.editor.delete("1.0", tk.END)
            
            if is_formatted_docx:
                self._read_docx_with_formatting(path)
            else:
                self.editor.insert(tk.END, content)
            
            # Update the Source of Truth
            self.current_file_path = path
            self.root.title(f"PyWord Pro - {os.path.basename(path)}")

        except Exception as e:
            messagebox.showerror("Open Error", f"Could not read file:\n{e}")
            # Note: We do NOT update self.current_file_path here. 
            # The app stays on the previous file, safe and sound.

    def save_file(self):
        """
        Handles the "Save" button logic.
        """
        # If we have a file path, write to it.
        # If we don't (it's a new unsaved document), redirect to "Save As".
        if self.current_file_path:
            self._write_to_disk(self.current_file_path)
        else:
            self.save_as_file()

    def save_as_file(self):
        """
        Handles "Save As" or "Save" for new files.
        """
        file_types = [("Word Document", "*.docx"), ("Text File", "*.txt")]
        
        path = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=file_types)
        if not path:
            return # User cancelled

        # Enforce extension if user deleted it
        if not path.endswith(".docx") and not path.endswith(".txt"):
            path += ".docx"

        # 1. Attempt to Write
        success = self._write_to_disk(path)
        
        # 2. ONLY update the app state if the write actually worked
        if success:
            self.current_file_path = path
            self.root.title(f"PyWord Pro - {os.path.basename(path)}")

    def export_pdf(self):
        if not HAS_FPDF:
            messagebox.showerror("Error", "FPDF library missing.")
            return
        
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if path:
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                text = self.editor.get("1.0", tk.END).encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 10, text)
                pdf.output(path)
                messagebox.showinfo("Success", "PDF Exported.")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def _write_to_disk(self, path):
        """
        The low-level writer. Returns True if success, False if failed.
        """
        try:
            if path.endswith(".docx") and HAS_DOCX:
                self._save_docx_with_formatting(path)
            else:
                if path.endswith(".txt"):
                    if not messagebox.askyesno("Format Warning", "Saving as .txt will remove Bold/Italic styles.\nContinue?"):
                        return False
                
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.editor.get("1.0", tk.END))
            
            return True # Success
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file:\n{e}")
            return False # Failure

    # --- ADVANCED FORMATTING LOGIC (PRESERVES BOLD/ITALIC) ---

    def _read_docx_with_formatting(self, path):
        doc = Document(path)
        for para in doc.paragraphs:
            for run in para.runs:
                self.editor.insert(tk.END, run.text)
                
                # Apply tags to the text we just inserted
                run_len = len(run.text)
                start_index = f"end-{run_len+1}c" 
                end_index = "end-1c"

                if run.bold:
                    self.editor.tag_add("bold", start_index, end_index)
                    self._ensure_tag_configured("bold")
                if run.italic:
                    self.editor.tag_add("italic", start_index, end_index)
                    self._ensure_tag_configured("italic")
                if run.underline:
                    self.editor.tag_add("underline", start_index, end_index)
                    self._ensure_tag_configured("underline")
                
                # Handle combined bold+italic if we used the combined tag system
                if run.bold and run.italic:
                    self.editor.tag_add("bold_italic", start_index, end_index)
                    self._ensure_tag_configured("bold_italic")

            self.editor.insert(tk.END, "\n")

    def _save_docx_with_formatting(self, path):
        doc = Document()
        last_line_idx = int(self.editor.index('end-1c').split('.')[0])
        
        for line_num in range(1, last_line_idx + 1):
            line_text = self.editor.get(f"{line_num}.0", f"{line_num}.end")
            if not line_text:
                doc.add_paragraph("")
                continue
                
            paragraph = doc.add_paragraph()
            
            # Buffer for grouping characters with same style
            current_run_text = ""
            current_tags = set()
            
            # Initial tags
            first_tags = set(self.editor.tag_names(f"{line_num}.0"))
            current_tags = self._filter_style_tags(first_tags)

            for char_index, char in enumerate(line_text):
                abs_index = f"{line_num}.{char_index}"
                char_tags = set(self.editor.tag_names(abs_index))
                clean_tags = self._filter_style_tags(char_tags)

                # Style change detected? Flush buffer.
                if clean_tags != current_tags:
                    self._add_run_to_paragraph(paragraph, current_run_text, current_tags)
                    current_run_text = char
                    current_tags = clean_tags
                else:
                    current_run_text += char
            
            # Flush final buffer
            if current_run_text:
                self._add_run_to_paragraph(paragraph, current_run_text, current_tags)

        doc.save(path)

    def _add_run_to_paragraph(self, paragraph, text, tags):
        """Helper to create a run with correct attributes."""
        run = paragraph.add_run(text)
        if "bold" in tags or "bold_italic" in tags: run.bold = True
        if "italic" in tags or "bold_italic" in tags: run.italic = True
        if "underline" in tags: run.underline = True

    def _filter_style_tags(self, tags):
        return {t for t in tags if t in {"bold", "italic", "underline", "bold_italic"}}

    def _ensure_tag_configured(self, tag_name):
        # Re-asserts visual style in case it wasn't loaded
        from tkinter import font
        current_font = font.Font(font=self.editor.cget("font"))
        if "bold" in tag_name: current_font.configure(weight="bold")
        if "italic" in tag_name: current_font.configure(slant="italic")
        if "underline" in tag_name: current_font.configure(underline=True)
        self.editor.tag_configure(tag_name, font=current_font)