import tkinter as tk
from tkinter import Toplevel, messagebox, filedialog, Button, ttk, simpledialog
import datetime
import os
import re
import threading
from typing import Optional

from src.logic.dictionary_lookup import DictionaryService
from src.logic.wiki_client import WikipediaApiClient, WikipediaApiError
from src.logic.action_hub import (
    build_action_line,
    build_action_dashboard,
    build_action_focus_plan,
    build_action_report_html,
    parse_action_items,
    parse_due_input,
    set_action_due_date,
    set_action_effort,
    set_action_owner,
    set_action_priority,
    set_action_project,
    toggle_action_line_done,
)
from src.logic.templates import (
    get_template_style_preset,
    import_markdown_template_file,
    list_template_categories,
    list_template_style_presets,
    list_templates,
    summarize_template_markdown,
)
from src.logic.io_utils import atomic_write_text, normalize_output_path

# Safe import for Pillow
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class ToolManager:
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.images = []  # Prevent garbage collection
        self.template_style = "Professional Blue"
        self._template_zoom = 100
        self.default_logo_path = ""
        self._set_logo_callback = None
        self._clear_logo_callback = None
        self._dictionary_persist_callback = None
        self.dictionary = DictionaryService()
        self.wikipedia = WikipediaApiClient()

    def set_default_logo_path(self, path: str | None):
        value = (path or "").strip()
        self.default_logo_path = value

    def get_default_logo_path(self) -> str:
        return self.default_logo_path

    def set_logo_callbacks(self, set_callback=None, clear_callback=None):
        self._set_logo_callback = set_callback
        self._clear_logo_callback = clear_callback

    def set_custom_dictionary_entries(self, entries: dict | None):
        self.dictionary.load_custom_entries(entries if isinstance(entries, dict) else {})

    def get_custom_dictionary_entries(self) -> dict:
        return self.dictionary.export_custom_entries()

    def set_dictionary_persist_callback(self, callback=None):
        self._dictionary_persist_callback = callback

    def set_zoom(self, zoom_value: int):
        try:
            self._template_zoom = max(50, min(200, int(zoom_value)))
        except (TypeError, ValueError):
            self._template_zoom = 100
        self.refresh_template_tags()

    def refresh_template_tags(self):
        try:
            self._configure_template_tags(self.template_style)
        except Exception:
            pass

    def select_all(self):
        self.editor.tag_add("sel", "1.0", "end")
        self.editor.mark_set("insert", "1.0")
        self.editor.see("insert")
        return "break"

    def insert_horizontal_line(self):
        self.editor.insert(tk.INSERT, "\n" + "_" * 40 + "\n")

    def insert_date_time(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.editor.insert(tk.INSERT, now)

    def insert_image(self):
        if not HAS_PIL:
            messagebox.showerror("Error", "Pillow library not installed.\nRun: pip install Pillow")
            return

        # IMPORTANT (macOS/Tk): do NOT use semicolon-separated patterns like "*.png;*.jpg"
        # Use a tuple (or space-separated string) so Tk can safely map to allowed file types.
        path = filedialog.askopenfilename(
            parent=self.root,
            filetypes=[
                ("Images", ("*.png", "*.jpg", "*.jpeg", "*.gif")),
                ("All Files", "*"),
            ],
        )
        if not path:
            return

        try:
            img = Image.open(path)
            # Resize giant images to prevent UI freeze
            img.thumbnail((500, 500))
            photo = ImageTk.PhotoImage(img)

            self.images.append(photo)  # Keep reference
            self.editor.image_create(tk.INSERT, image=photo, padx=10, pady=10)
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not load image:\n{e}")

    def open_symbol_picker(self):
        win = Toplevel(self.root)
        win.title("Symbols")
        win.geometry("350x250")
        win.transient(self.root)

        symbols = [
            "©", "®", "™", "€", "£", "¥", "¢", "§",
            "¶", "∞", "≠", "≈", "±", "≤", "≥", "÷",
            "×", "°", "α", "β", "π", "Ω", "Σ", "★",
            "•", "→", "←", "↑", "↓", "✓"
        ]

        row = 0
        col = 0
        for s in symbols:
            btn = Button(
                win,
                text=s,
                width=4,
                font=("Segoe UI", 12),
                command=lambda char=s: self.editor.insert(tk.INSERT, char),
            )
            btn.grid(row=row, column=col, padx=3, pady=3)
            col += 1
            if col > 5:
                col = 0
                row += 1

    def open_find_replace(self):
        win = Toplevel(self.root)
        win.title("Find & Replace")
        win.geometry("330x200")
        win.transient(self.root)

        tk.Label(win, text="Find:").pack(pady=(5, 0))
        e_find = tk.Entry(win, width=25)
        e_find.pack()

        tk.Label(win, text="Replace with:").pack(pady=(5, 0))
        e_rep = tk.Entry(win, width=25)
        e_rep.pack()

        case_sensitive = tk.BooleanVar(value=True)
        tk.Checkbutton(win, text="Match case", variable=case_sensitive).pack(pady=(6, 0))

        def _search_next(find_str: str, start_at: str = "insert") -> Optional[str]:
            if not find_str:
                return None
            opts = {} if case_sensitive.get() else {"nocase": True}
            return self.editor.search(find_str, start_at, stopindex=tk.END, **opts)

        def do_find_next():
            self.editor.tag_remove("highlight_find", "1.0", tk.END)
            find_str = e_find.get()
            pos = _search_next(find_str)
            if not pos:
                messagebox.showinfo("Find", "No match found.")
                return
            end_pos = f"{pos}+{len(find_str)}c"
            self.editor.tag_add("highlight_find", pos, end_pos)
            self.editor.mark_set(tk.INSERT, end_pos)
            self.editor.see(pos)

        def do_replace():
            find_str = e_find.get()
            rep_str = e_rep.get()
            if not find_str:
                return

            # NON-DESTRUCTIVE SEARCH ALGORITHM
            start_pos = "1.0"
            count = 0

            while True:
                # Search specifically for the string
                pos = _search_next(find_str, start_at=start_pos)
                if not pos:
                    break

                # Calculate end position of match
                end_pos = f"{pos}+{len(find_str)}c"

                # Replace ONLY the text found (preserves formatting elsewhere)
                self.editor.delete(pos, end_pos)
                self.editor.insert(pos, rep_str)

                # Move pointer forward
                start_pos = f"{pos}+{len(rep_str)}c"
                count += 1

            if count > 0:
                messagebox.showinfo("Result", f"Replaced {count} occurrences.")
                win.destroy()
            else:
                messagebox.showinfo("Result", "No matches found.")

        actions = tk.Frame(win)
        actions.pack(pady=12)
        tk.Button(actions, text="Find Next", command=do_find_next).pack(side=tk.LEFT, padx=4)
        tk.Button(actions, text="Replace All", command=do_replace).pack(side=tk.LEFT, padx=4)

        e_find.focus_set()

    def _active_word(self) -> str:
        try:
            selected = self.editor.get("sel.first", "sel.last").strip()
        except tk.TclError:
            selected = ""
        if selected:
            normalized = self.dictionary.normalize_word(selected)
            if normalized:
                return normalized

        try:
            word = self.editor.get("insert wordstart", "insert wordend").strip()
        except tk.TclError:
            word = ""
        return self.dictionary.normalize_word(word)

    def _active_query(self) -> str:
        try:
            selected = self.editor.get("sel.first", "sel.last").strip()
        except tk.TclError:
            selected = ""
        if selected:
            return " ".join(selected.split())[:120]
        return self._active_word()

    def _persist_dictionary_entries(self):
        callback = self._dictionary_persist_callback
        if not callable(callback):
            return
        try:
            callback(self.dictionary.export_custom_entries())
        except Exception:
            pass

    def open_dictionary_lookup(self):
        win = Toplevel(self.root)
        win.title("Dictionary Lookup")
        win.geometry("620x430")
        win.minsize(560, 380)
        win.transient(self.root)

        frame = tk.Frame(win, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        tk.Label(frame, text="Dictionary", font=("Segoe UI", 14, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", pady=(0, 8)
        )

        lookup_row = tk.Frame(frame)
        lookup_row.grid(row=1, column=0, sticky="ew")
        lookup_row.grid_columnconfigure(0, weight=1)

        word_var = tk.StringVar(value=self._active_word())
        entry = tk.Entry(lookup_row, textvariable=word_var, font=("Segoe UI", 11))
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        result = tk.Text(frame, wrap=tk.WORD, height=10, relief=tk.SOLID, bd=1)
        result.grid(row=2, column=0, sticky="nsew", pady=(10, 8))
        result.config(state=tk.DISABLED)

        suggestion_row = tk.Frame(frame)
        suggestion_row.grid(row=3, column=0, sticky="ew")
        suggestion_row.grid_columnconfigure(1, weight=1)
        tk.Label(suggestion_row, text="Suggestions:", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        suggestion_box = ttk.Combobox(suggestion_row, values=(), state="readonly")
        suggestion_box.grid(row=0, column=1, sticky="ew")

        status_var = tk.StringVar(value="Type a word and click Lookup.")
        tk.Label(frame, textvariable=status_var, anchor="w", justify=tk.LEFT, font=("Segoe UI", 10)).grid(
            row=4, column=0, sticky="ew", pady=(8, 0)
        )

        def _write_result(text: str):
            result.config(state=tk.NORMAL)
            result.delete("1.0", tk.END)
            result.insert("1.0", text)
            result.config(state=tk.DISABLED)

        def _lookup():
            raw_word = str(word_var.get() or "").strip()
            key = self.dictionary.normalize_word(raw_word)
            if not key:
                status_var.set("Enter a valid single word.")
                _write_result("")
                suggestion_box.configure(values=())
                return False
            word_var.set(key)

            entry_data = self.dictionary.lookup(key)
            suggestions = self.dictionary.suggest(key, limit=8)
            suggestion_box.configure(values=suggestions)
            if suggestions:
                suggestion_box.set(suggestions[0])
            else:
                suggestion_box.set("")

            if entry_data is None:
                _write_result(f"{key}\n\nNo local definition found.")
                status_var.set("No definition found. You can add a custom entry.")
                return False

            synonyms_text = ", ".join(entry_data.get("synonyms") or []) or "-"
            example_text = str(entry_data.get("example", "") or "").strip() or "-"
            message = (
                f"{entry_data['word']} ({entry_data['part_of_speech']})\n"
                f"Source: {entry_data.get('source', 'local')}\n\n"
                f"{entry_data['definition']}\n\n"
                f"Synonyms: {synonyms_text}\n"
                f"Example: {example_text}\n"
            )
            _write_result(message)
            status_var.set("Definition loaded.")
            return True

        def _use_selection_word():
            selected = self._active_word()
            if not selected:
                status_var.set("No valid word at cursor/selection.")
                return
            word_var.set(selected)
            _lookup()

        def _use_suggestion():
            chosen = str(suggestion_box.get() or "").strip()
            if not chosen:
                return
            word_var.set(chosen)
            _lookup()

        def _save_custom_definition():
            key = self.dictionary.normalize_word(word_var.get())
            if not key:
                status_var.set("Enter a valid word before saving a custom definition.")
                return
            existing = self.dictionary.lookup(key) or {}
            definition = simpledialog.askstring(
                "Custom Definition",
                f"Definition for '{key}':",
                initialvalue=str(existing.get("definition", "")),
                parent=win,
            )
            if definition is None:
                return
            if not str(definition).strip():
                messagebox.showerror("Dictionary", "Definition cannot be empty.", parent=win)
                return
            part = simpledialog.askstring(
                "Part of Speech",
                "Part of speech (noun/verb/adjective/adverb/phrase):",
                initialvalue=str(existing.get("part_of_speech", "noun")),
                parent=win,
            )
            if part is None:
                return
            synonyms = simpledialog.askstring(
                "Synonyms",
                "Comma-separated synonyms (optional):",
                initialvalue=", ".join(existing.get("synonyms", [])),
                parent=win,
            )
            example = simpledialog.askstring(
                "Example",
                "Example sentence (optional):",
                initialvalue=str(existing.get("example", "")),
                parent=win,
            )
            ok = self.dictionary.add_custom_entry(
                key,
                str(definition).strip(),
                part_of_speech=str(part or "noun"),
                synonyms=(synonyms or ""),
                example=(example or ""),
            )
            if not ok:
                messagebox.showerror("Dictionary", "Could not save custom definition.", parent=win)
                return
            self._persist_dictionary_entries()
            status_var.set("Custom definition saved.")
            _lookup()

        tk.Button(lookup_row, text="Lookup", width=11, command=_lookup).grid(row=0, column=1, padx=(0, 6))
        tk.Button(lookup_row, text="Use Selection", width=13, command=_use_selection_word).grid(row=0, column=2)

        action_row = tk.Frame(frame)
        action_row.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        tk.Button(action_row, text="Use Suggestion", width=14, command=_use_suggestion).pack(side=tk.LEFT)
        tk.Button(action_row, text="Add / Update Custom", width=18, command=_save_custom_definition).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )
        tk.Button(action_row, text="Close", width=10, command=win.destroy).pack(side=tk.RIGHT)

        entry.bind("<Return>", lambda _e: _lookup(), add="+")
        suggestion_box.bind("<<ComboboxSelected>>", lambda _e: _use_suggestion(), add="+")
        entry.focus_set()
        if word_var.get():
            _lookup()
        return True

    def _lookup_wikipedia_data(self, query: str, related_limit: int = 8):
        normalized_query = str(query or "").strip()
        if not normalized_query:
            raise ValueError("Wikipedia query is required.")

        hit = self.wikipedia.lookup(normalized_query)

        related: list[str] = []
        related_warning = ""
        try:
            related = self.wikipedia.search_titles(normalized_query, limit=related_limit)
        except WikipediaApiError as exc:
            related_warning = str(exc)

        clean_related = []
        for value in related if isinstance(related, list) else []:
            item = str(value or "").strip()
            if item and item not in clean_related:
                clean_related.append(item)

        return hit, clean_related, related_warning

    def open_wiki_lookup(self):
        win = Toplevel(self.root)
        win.title("Wikipedia Lookup")
        win.geometry("740x520")
        win.minsize(660, 440)
        win.transient(self.root)

        frame = tk.Frame(win, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        tk.Label(
            frame,
            text="Wikipedia Research Lookup",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        lookup_row = tk.Frame(frame)
        lookup_row.grid(row=1, column=0, sticky="ew")
        lookup_row.grid_columnconfigure(0, weight=1)

        query_var = tk.StringVar(value=self._active_query())
        query_entry = tk.Entry(lookup_row, textvariable=query_var, font=("Segoe UI", 11))
        query_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        result = tk.Text(frame, wrap=tk.WORD, relief=tk.SOLID, bd=1)
        result.grid(row=2, column=0, sticky="nsew", pady=(10, 8))
        result.config(state=tk.DISABLED)

        suggestion_row = tk.Frame(frame)
        suggestion_row.grid(row=3, column=0, sticky="ew")
        suggestion_row.grid_columnconfigure(1, weight=1)
        tk.Label(suggestion_row, text="Related pages:", font=("Segoe UI", 10, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 8),
        )
        suggestion_box = ttk.Combobox(suggestion_row, values=(), state="readonly")
        suggestion_box.grid(row=0, column=1, sticky="ew")

        status_var = tk.StringVar(value="Enter a topic and click Search.")
        tk.Label(frame, textvariable=status_var, anchor="w", justify=tk.LEFT, font=("Segoe UI", 10)).grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(8, 0),
        )

        current_hit = {"data": None}
        lookup_state = {"busy": False, "token": 0}
        controls = {
            "search": None,
            "selection": None,
            "suggestion": None,
            "insert": None,
        }

        def _write_result(text: str):
            result.config(state=tk.NORMAL)
            result.delete("1.0", tk.END)
            result.insert("1.0", text)
            result.config(state=tk.DISABLED)

        def _set_lookup_busy(is_busy: bool):
            lookup_state["busy"] = bool(is_busy)
            button_state = tk.DISABLED if is_busy else tk.NORMAL
            entry_state = tk.DISABLED if is_busy else tk.NORMAL
            combo_state = "disabled" if is_busy else "readonly"

            try:
                query_entry.configure(state=entry_state)
                suggestion_box.configure(state=combo_state)
            except tk.TclError:
                return

            for key in ("search", "selection", "suggestion", "insert"):
                widget = controls.get(key)
                if widget is None:
                    continue
                try:
                    widget.configure(state=button_state)
                except tk.TclError:
                    pass

        def _lookup():
            if lookup_state.get("busy"):
                status_var.set("Wikipedia search in progress...")
                return False

            query = str(query_var.get() or "").strip()
            if not query:
                status_var.set("Enter a topic to search.")
                _write_result("")
                suggestion_box.configure(values=())
                suggestion_box.set("")
                current_hit["data"] = None
                return False

            lookup_state["token"] += 1
            token = lookup_state["token"]
            status_var.set("Searching Wikipedia...")
            _set_lookup_busy(True)

            result_box = {"payload": None}
            error_box = {"message": ""}

            def _worker():
                try:
                    result_box["payload"] = self._lookup_wikipedia_data(query, related_limit=8)
                except (WikipediaApiError, ValueError) as exc:
                    error_box["message"] = str(exc)
                except Exception:
                    error_box["message"] = "Wikipedia lookup failed unexpectedly."

            worker = threading.Thread(target=_worker, daemon=True)
            worker.start()

            def _poll_worker():
                try:
                    if not win.winfo_exists() or token != lookup_state.get("token"):
                        return
                except tk.TclError:
                    return

                if worker.is_alive():
                    win.after(80, _poll_worker)
                    return

                _set_lookup_busy(False)

                failure_message = str(error_box.get("message") or "").strip()
                if failure_message:
                    status_var.set(failure_message)
                    _write_result("")
                    suggestion_box.configure(values=())
                    suggestion_box.set("")
                    current_hit["data"] = None
                    return

                payload = result_box.get("payload")
                if not isinstance(payload, tuple) or len(payload) != 3:
                    status_var.set("Wikipedia lookup failed unexpectedly.")
                    _write_result("")
                    suggestion_box.configure(values=())
                    suggestion_box.set("")
                    current_hit["data"] = None
                    return

                hit, related, related_warning = payload
                current_hit["data"] = hit
                suggestion_box.configure(values=related)
                if related:
                    suggestion_box.set(related[0])
                else:
                    suggestion_box.set("")

                description = str(hit.get("description") or "").strip()
                description_line = f"{description}\n" if description else ""
                text = (
                    f"{hit.get('title', 'Wikipedia')}\n"
                    f"{description_line}\n"
                    f"{hit.get('summary', '')}\n\n"
                    f"Source: {hit.get('url', '')}\n"
                )
                _write_result(text)
                if related_warning:
                    status_var.set("Wikipedia summary loaded. Related pages unavailable.")
                else:
                    status_var.set("Wikipedia summary loaded.")

            win.after(80, _poll_worker)
            return True

        def _use_selection():
            active = self._active_query()
            if not active:
                status_var.set("No useful selection or word at cursor.")
                return
            query_var.set(active)
            _lookup()

        def _use_suggestion():
            choice = str(suggestion_box.get() or "").strip()
            if not choice:
                return
            query_var.set(choice)
            _lookup()

        def _insert_summary():
            if lookup_state.get("busy"):
                status_var.set("Wikipedia search in progress. Wait for results.")
                return
            data = current_hit.get("data")
            if not isinstance(data, dict):
                if _lookup():
                    status_var.set("Searching Wikipedia. Insert again after results load.")
                return
            block = (
                "\n[Wikipedia Note]\n"
                f"Topic: {data.get('title', '')}\n"
                f"{data.get('summary', '')}\n"
                f"Source: {data.get('url', '')}\n"
            )
            self.editor.insert(tk.INSERT, block)
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            status_var.set("Summary inserted into document.")

        controls["search"] = tk.Button(lookup_row, text="Search Wiki", width=12, command=_lookup)
        controls["search"].grid(row=0, column=1, padx=(0, 6))
        controls["selection"] = tk.Button(lookup_row, text="Use Selection", width=13, command=_use_selection)
        controls["selection"].grid(row=0, column=2)

        action_row = tk.Frame(frame)
        action_row.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        controls["suggestion"] = tk.Button(action_row, text="Use Suggested Page", width=16, command=_use_suggestion)
        controls["suggestion"].pack(side=tk.LEFT)
        controls["insert"] = tk.Button(action_row, text="Insert Summary", width=13, command=_insert_summary)
        controls["insert"].pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(action_row, text="Close", width=10, command=win.destroy).pack(side=tk.RIGHT)

        query_entry.bind("<Return>", lambda _e: _lookup(), add="+")
        suggestion_box.bind("<<ComboboxSelected>>", lambda _e: _use_suggestion(), add="+")
        query_entry.focus_set()
        if query_var.get():
            _lookup()
        return True

    def show_stats(self):
        try:
            text = self.editor.get("1.0", tk.END)
            words = len(text.split())
            chars = len(text) - 1
            lines = int(self.editor.index("end-1c").split(".")[0])
            messagebox.showinfo("Stats", f"Words: {words}\nCharacters: {chars}\nLines: {lines}")
        except tk.TclError:
            messagebox.showerror("Stats", "Unable to calculate document statistics.")

    def export_fancy_todo_report(self, items: list | None = None):
        dataset = items if items is not None else parse_action_items(self.editor.get("1.0", "end-1c"))
        path = filedialog.asksaveasfilename(
            title="Export Fancy To-Do Report",
            defaultextension=".html",
            filetypes=[("HTML", "*.html"), ("All Files", "*.*")],
            parent=self.root,
        )
        if not path:
            return False
        try:
            target_path = normalize_output_path(path, default_extension=".html")
            report_html = build_action_report_html(
                dataset,
                title="To-Do Action Report",
                logo_path=self.default_logo_path,
                generated_by="PyWord Pro Action Hub",
            )
            atomic_write_text(target_path, report_html, default_extension=".html", newline="")
            messagebox.showinfo("To-Do Report", f"Fancy report exported:\n{target_path}")
            return True
        except OSError as exc:
            messagebox.showerror("To-Do Report", f"Export failed:\n{exc}")
            return False

    def _selection_bounds(self) -> tuple[str, str] | None:
        try:
            return self.editor.index("sel.first"), self.editor.index("sel.last")
        except tk.TclError:
            return None

    def _line_bounds_at_insert(self) -> tuple[str, str]:
        line_no = self.editor.index("insert").split(".")[0]
        return f"{line_no}.0", f"{line_no}.end"

    def _sentence_case(self, value: str) -> str:
        result = []
        capitalize = True
        for ch in value:
            if capitalize and ch.isalpha():
                result.append(ch.upper())
                capitalize = False
            else:
                result.append(ch.lower())
            if ch in ".!?\n":
                capitalize = True
        return "".join(result)

    def convert_case(self, mode: str):
        bounds = self._selection_bounds() or self._line_bounds_at_insert()
        start, end = bounds
        text = self.editor.get(start, end)
        if not text:
            return False

        transform = {
            "upper": str.upper,
            "lower": str.lower,
            "title": str.title,
            "sentence": self._sentence_case,
        }.get((mode or "").lower())
        if not transform:
            return False

        updated = transform(text)
        if updated == text:
            return False
        self.editor.delete(start, end)
        self.editor.insert(start, updated)
        return True

    def duplicate_selection_or_line(self):
        sel = self._selection_bounds()
        if sel:
            start, end = sel
            text = self.editor.get(start, end)
            if not text:
                return False
            self.editor.insert(end, text)
            return True

        line_start, line_end = self._line_bounds_at_insert()
        line_text = self.editor.get(line_start, line_end)
        self.editor.insert(line_end, f"\n{line_text}")
        return True

    def sort_selected_lines(self, reverse: bool = False):
        bounds = self._selection_bounds()
        if bounds:
            start, end = bounds
        else:
            start, end = "1.0", "end-1c"

        raw = self.editor.get(start, end)
        lines = raw.splitlines()
        if len(lines) < 2:
            return False

        sorted_lines = sorted(lines, key=lambda line: line.lower(), reverse=reverse)
        updated = "\n".join(sorted_lines)
        if updated == raw:
            return False

        self.editor.delete(start, end)
        self.editor.insert(start, updated)
        return True

    def clean_trailing_whitespace(self):
        raw = self.editor.get("1.0", "end-1c")
        cleaned = "\n".join(line.rstrip() for line in raw.splitlines())
        if cleaned == raw:
            return False
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", cleaned + ("\n" if cleaned else ""))
        return True

    def insert_table(self, rows: int = 3, cols: int = 3):
        try:
            rows = int(rows)
            cols = int(cols)
        except (TypeError, ValueError):
            return False
        rows = max(1, min(30, rows))
        cols = max(1, min(12, cols))

        header = "| " + " | ".join(f"Column {i + 1}" for i in range(cols)) + " |"
        divider = "| " + " | ".join("---" for _ in range(cols)) + " |"
        body = ["| " + " | ".join(" " for _ in range(cols)) + " |" for _ in range(rows)]
        table = "\n".join([header, divider] + body)
        self.editor.insert(tk.INSERT, f"\n{table}\n")
        return True

    def insert_table_prompt(self):
        rows = simpledialog.askinteger("Insert Table", "Body rows:", initialvalue=4, minvalue=1, maxvalue=30, parent=self.root)
        if rows is None:
            return False
        cols = simpledialog.askinteger("Insert Table", "Columns:", initialvalue=3, minvalue=1, maxvalue=12, parent=self.root)
        if cols is None:
            return False
        return self.insert_table(rows=rows, cols=cols)

    def insert_checklist(self, items: int = 5):
        try:
            items = int(items)
        except (TypeError, ValueError):
            return False
        items = max(1, min(50, items))
        body = "\n".join(f"- [ ] Task {i + 1}" for i in range(items))
        self.editor.insert(tk.INSERT, f"\n{body}\n")
        return True

    def insert_checklist_prompt(self):
        items = simpledialog.askinteger("Insert Checklist", "Number of items:", initialvalue=6, minvalue=1, maxvalue=50, parent=self.root)
        if items is None:
            return False
        return self.insert_checklist(items=items)

    def insert_page_break(self):
        self.editor.insert(tk.INSERT, "\n" + "=" * 24 + " Page Break " + "=" * 24 + "\n")
        return True

    def _build_memo_content(
        self,
        *,
        doc_type: str,
        title: str,
        audience: str,
        owner: str,
        objective: str,
        key_points: str,
        add_todo: bool,
    ) -> str:
        date_str = datetime.date.today().isoformat()
        clean_title = title.strip() or doc_type
        clean_audience = audience.strip() or "Internal Team"
        clean_owner = owner.strip() or "Document Owner"
        clean_objective = objective.strip() or "Summarize context, decisions, and next steps."
        points = [line.strip() for line in key_points.splitlines() if line.strip()]

        lines: list[str] = [
            f"# {clean_title}",
            "",
            f"Document Type: {doc_type}",
            f"Date: {date_str}",
            f"Owner: {clean_owner}",
            f"Audience: {clean_audience}",
            "",
            "## Executive Summary",
            clean_objective,
            "",
            "## Key Points",
        ]
        if points:
            lines.extend(f"- {point}" for point in points)
        else:
            lines.extend(["- [Insert key point]", "- [Insert key point]"])
        lines.extend(["", "## References", "- Related docs:", "- Approvers:"])

        if doc_type == "Internal Memo":
            lines.extend(
                [
                    "",
                    "## Decision / Request",
                    "- Decision needed:",
                    "- Deadline:",
                    "",
                    "## Communication Plan",
                    "- Stakeholder update:",
                    "- Publish channel:",
                ]
            )
        elif doc_type == "Internal Documentation":
            lines.extend(
                [
                    "",
                    "## Context",
                    "[Describe why this process/system exists]",
                    "",
                    "## Procedure",
                    "1. Step one",
                    "2. Step two",
                    "3. Step three",
                    "",
                    "## Troubleshooting",
                    "- Symptom:",
                    "- Resolution:",
                ]
            )
        elif doc_type == "SOP":
            lines.extend(
                [
                    "",
                    "## Scope",
                    "[Define boundaries and ownership]",
                    "",
                    "## Prerequisites",
                    "- Access requirements",
                    "- Inputs needed",
                    "",
                    "## Standard Procedure",
                    "1. Preparation",
                    "2. Execution",
                    "3. Verification",
                    "",
                    "## QA Checklist",
                    "- [ ] Validation complete",
                    "- [ ] Peer review complete",
                    "- [ ] Sign-off captured",
                ]
            )

        if add_todo:
            lines.extend(
                [
                    "",
                    "## Action Items",
                    "- [ ] Task: [Define next step] | owner: [name] | due: [YYYY-MM-DD]",
                    "- [ ] Task: [Define next step] | owner: [name] | due: [YYYY-MM-DD]",
                ]
            )

        lines.append("")
        return "\n".join(lines)

    def open_memo_builder(self):
        win = Toplevel(self.root)
        win.title("Memo Builder")
        win.geometry("760x560")
        win.minsize(680, 520)
        win.transient(self.root)
        win.grab_set()

        outer = tk.Frame(win, padx=14, pady=14)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.grid_columnconfigure(1, weight=1)
        outer.grid_rowconfigure(6, weight=1)

        tk.Label(
            outer,
            text="Automatic Memo / Internal Documentation / SOP Builder",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        tk.Label(outer, text="Document type", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", padx=(0, 8))
        doc_type_var = tk.StringVar(value="Internal Memo")
        doc_type_box = ttk.Combobox(
            outer,
            textvariable=doc_type_var,
            values=("Internal Memo", "Internal Documentation", "SOP"),
            state="readonly",
            width=28,
        )
        doc_type_box.grid(row=1, column=1, sticky="ew")

        def _entry_row(row: int, label: str, default: str = ""):
            tk.Label(outer, text=label, font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
            var = tk.StringVar(value=default)
            tk.Entry(outer, textvariable=var).grid(row=row, column=1, sticky="ew", pady=(8, 0))
            return var

        title_var = _entry_row(2, "Title", "Weekly Operations Memo")
        audience_var = _entry_row(3, "Audience", "Operations Team")
        owner_var = _entry_row(4, "Owner", "Team Lead")
        objective_var = _entry_row(5, "Objective", "Capture updates, decisions, and required actions.")

        tk.Label(outer, text="Key points (one per line)", font=("Segoe UI", 10, "bold")).grid(
            row=6, column=0, sticky="nw", padx=(0, 8), pady=(10, 0)
        )
        key_points = tk.Text(outer, height=8, wrap=tk.WORD)
        key_points.grid(row=6, column=1, sticky="nsew", pady=(10, 0))
        key_points.insert("1.0", "Team goal for this cycle\nCurrent blockers\nResource asks")

        todo_var = tk.BooleanVar(value=True)
        tk.Checkbutton(outer, text="Include to-do action items section", variable=todo_var).grid(
            row=7, column=1, sticky="w", pady=(10, 0)
        )

        status_var = tk.StringVar(value="Build a polished internal document and insert it into the editor.")
        tk.Label(outer, textvariable=status_var, anchor="w", justify=tk.LEFT, font=("Segoe UI", 10)).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )

        button_row = tk.Frame(outer)
        button_row.grid(row=9, column=0, columnspan=2, sticky="e", pady=(10, 0))

        def _insert():
            content = self._build_memo_content(
                doc_type=doc_type_var.get(),
                title=title_var.get(),
                audience=audience_var.get(),
                owner=owner_var.get(),
                objective=objective_var.get(),
                key_points=key_points.get("1.0", "end-1c"),
                add_todo=todo_var.get(),
            )
            ok = self.apply_template(content, style=self.template_style)
            if not ok:
                status_var.set("Unable to build memo.")
                return
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            status_var.set("Memo inserted into the document.")
            win.destroy()

        tk.Button(button_row, text="Cancel", width=11, command=win.destroy).pack(side=tk.RIGHT)
        tk.Button(button_row, text="Build and Insert", width=16, relief=tk.RAISED, bd=2, command=_insert).pack(
            side=tk.RIGHT, padx=(0, 8)
        )
        return True

    def open_action_hub(self):
        win = Toplevel(self.root)
        win.title("Action Hub")
        win.geometry("1240x700")
        win.minsize(980, 560)
        win.transient(self.root)

        outer = tk.Frame(win, padx=12, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.grid_rowconfigure(2, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        tk.Label(
            outer,
            text="Action Hub",
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        filter_row = tk.Frame(outer)
        filter_row.grid(row=1, column=0, sticky="ew", pady=(8, 8))

        tk.Label(filter_row, text="Status", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        status_var = tk.StringVar(value="Open")
        status_box = ttk.Combobox(
            filter_row,
            textvariable=status_var,
            state="readonly",
            width=14,
            values=("All", "Open", "Done", "Overdue", "Due today", "Due soon"),
        )
        status_box.pack(side=tk.LEFT, padx=(6, 12))

        tk.Label(filter_row, text="Owner", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        owner_var = tk.StringVar(value="All owners")
        owner_box = ttk.Combobox(
            filter_row,
            textvariable=owner_var,
            state="readonly",
            width=16,
            values=("All owners",),
        )
        owner_box.pack(side=tk.LEFT, padx=(6, 12))

        tk.Label(filter_row, text="Priority", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        priority_var = tk.StringVar(value="All priorities")
        priority_box = ttk.Combobox(
            filter_row,
            textvariable=priority_var,
            state="readonly",
            width=14,
            values=("All priorities", "Critical", "High", "Medium", "Normal", "Low"),
        )
        priority_box.pack(side=tk.LEFT, padx=(6, 12))

        tk.Label(filter_row, text="Workstream", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        stream_var = tk.StringVar(value="All streams")
        stream_box = ttk.Combobox(
            filter_row,
            textvariable=stream_var,
            state="readonly",
            width=16,
            values=("All streams",),
        )
        stream_box.pack(side=tk.LEFT, padx=(6, 12))

        tk.Label(filter_row, text="Search", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        search_var = tk.StringVar(value="")
        search_entry = tk.Entry(filter_row, textvariable=search_var, width=28)
        search_entry.pack(side=tk.LEFT, padx=(6, 0))

        info_lbl = tk.Label(
            outer,
            text="",
            anchor="w",
            justify=tk.LEFT,
            font=("Segoe UI", 10),
        )
        info_lbl.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        tree = ttk.Treeview(
            outer,
            columns=("status", "priority", "stream", "score", "urgency", "due", "owner", "task", "line"),
            show="headings",
            height=14,
        )
        tree.heading("status", text="Status")
        tree.heading("priority", text="Priority")
        tree.heading("stream", text="Workstream")
        tree.heading("score", text="Score")
        tree.heading("urgency", text="Urgency")
        tree.heading("due", text="Due")
        tree.heading("owner", text="Owner")
        tree.heading("task", text="Task")
        tree.heading("line", text="Line")
        tree.column("status", width=90, anchor="w")
        tree.column("priority", width=90, anchor="w")
        tree.column("stream", width=130, anchor="w")
        tree.column("score", width=70, anchor="center")
        tree.column("urgency", width=110, anchor="w")
        tree.column("due", width=110, anchor="w")
        tree.column("owner", width=120, anchor="w")
        tree.column("task", width=430, anchor="w")
        tree.column("line", width=70, anchor="center")
        tree.grid(row=2, column=0, sticky="nsew")

        btn_row_primary = tk.Frame(outer)
        btn_row_primary.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        btn_row_secondary = tk.Frame(outer)
        btn_row_secondary.grid(row=5, column=0, sticky="ew", pady=(8, 0))

        all_items = []
        visible_items = []
        row_item_map = {}

        def _refresh_owner_values():
            owners = sorted({item.owner for item in all_items if item.owner}, key=lambda x: x.lower())
            values = ["All owners"] + owners
            previous = owner_var.get()
            owner_box["values"] = values
            if previous in values:
                owner_var.set(previous)
            else:
                owner_var.set("All owners")

        def _refresh_stream_values():
            streams = sorted({item.workstream for item in all_items if item.workstream}, key=lambda x: x.lower())
            values = ["All streams"] + streams
            previous = stream_var.get()
            stream_box["values"] = values
            if previous in values:
                stream_var.set(previous)
            else:
                stream_var.set("All streams")

        def _matches_filters(item):
            mode = status_var.get()
            if mode == "Open" and item.status != "Open":
                return False
            if mode == "Done" and item.status != "Done":
                return False
            if mode == "Overdue" and item.urgency != "Overdue":
                return False
            if mode == "Due today" and item.urgency != "Due today":
                return False
            if mode == "Due soon" and item.urgency != "Due soon":
                return False

            owner_mode = owner_var.get()
            if owner_mode != "All owners" and (item.owner or "") != owner_mode:
                return False

            priority_mode = priority_var.get()
            if priority_mode != "All priorities" and item.priority != priority_mode:
                return False

            stream_mode = stream_var.get()
            if stream_mode != "All streams" and item.workstream != stream_mode:
                return False

            query = search_var.get().strip().lower()
            haystack = " ".join(
                [
                    item.task,
                    item.owner or "",
                    item.project or "",
                    item.workstream,
                    item.priority,
                ]
            ).lower()
            if query and query not in haystack:
                return False
            return True

        def _render_items():
            nonlocal visible_items, row_item_map
            tree.delete(*tree.get_children())
            row_item_map = {}
            visible_items = [item for item in all_items if _matches_filters(item)]

            for idx, item in enumerate(visible_items):
                tree.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=(
                        item.status,
                        item.priority,
                        item.workstream,
                        item.focus_score,
                        item.urgency,
                        item.due_display,
                        item.owner or "-",
                        item.task,
                        item.line_number,
                    ),
                )
                row_item_map[str(idx)] = item

            if all_items:
                top_score = max((item.focus_score for item in visible_items), default=0)
                info_lbl.config(
                    text=f"{len(visible_items)} shown / {len(all_items)} total action items. "
                    f"Top visible focus score: {top_score}. "
                    "Patterns: TODO:/Action:, markdown checkboxes, Owner:, Due:, Priority:, Effort:, Project:, @mentions."
                )
            else:
                info_lbl.config(
                    text="No action items detected. Try lines like `TODO: call Alex | owner: Alex | due: 2026-03-12` "
                    "or `- [ ] Draft proposal`."
                )

        def _refresh():
            nonlocal all_items
            all_items = parse_action_items(self.editor.get("1.0", "end-1c"))
            _refresh_owner_values()
            _refresh_stream_values()
            _render_items()

        def _selected_item():
            sel = tree.selection()
            if not sel:
                return None
            return row_item_map.get(sel[0])

        def _jump_to_selected():
            item = _selected_item()
            if not item:
                return
            try:
                self.editor.see(item.line_index)
                self.editor.mark_set(tk.INSERT, item.line_index)
                self.editor.focus_set()
            except tk.TclError:
                pass

        def _focus_next():
            open_items = [i for i in all_items if i.status == "Open"]
            if not open_items:
                info_lbl.config(text="No open items to focus.")
                return
            target = sorted(
                open_items,
                key=lambda i: (
                    -i.focus_score,
                    i.due_date or datetime.date.max,
                    i.line_number,
                ),
            )[0]
            try:
                self.editor.see(target.line_index)
                self.editor.mark_set(tk.INSERT, target.line_index)
                self.editor.focus_set()
            except tk.TclError:
                pass

            # Select row if visible under current filters.
            for row_id, item in row_item_map.items():
                if item.line_number == target.line_number:
                    tree.selection_set(row_id)
                    tree.focus(row_id)
                    break
            info_lbl.config(
                text=(
                    f"Focused next action: line {target.line_number} "
                    f"(score {target.focus_score}, {target.workstream}, {target.priority})."
                )
            )

        def _toggle_done_selected():
            item = _selected_item()
            if not item:
                info_lbl.config(text="Select an action item first.")
                return
            line_start = f"{item.line_number}.0"
            line_end = f"{item.line_number}.end"
            current_line = self.editor.get(line_start, line_end)
            updated = toggle_action_line_done(current_line)
            if updated is None:
                info_lbl.config(
                    text="Could not toggle this line automatically. Use TODO:/DONE: or checkbox task format."
                )
                return
            self.editor.delete(line_start, line_end)
            self.editor.insert(line_start, updated)
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            info_lbl.config(text=f"Toggled completion on line {item.line_number}.")
            _refresh()

        def _set_owner_selected():
            item = _selected_item()
            if not item:
                info_lbl.config(text="Select an action item first.")
                return
            owner = simpledialog.askstring(
                "Action Hub",
                "Owner (leave blank to clear):",
                initialvalue=item.owner or "",
                parent=win,
            )
            if owner is None:
                return
            line_start = f"{item.line_number}.0"
            line_end = f"{item.line_number}.end"
            current_line = self.editor.get(line_start, line_end)
            updated = set_action_owner(current_line, owner.strip())
            if updated is None:
                info_lbl.config(text="Could not update owner on this line.")
                return
            self.editor.delete(line_start, line_end)
            self.editor.insert(line_start, updated)
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            info_lbl.config(text=f"Owner updated on line {item.line_number}.")
            _refresh()

        def _set_due_selected():
            item = _selected_item()
            if not item:
                info_lbl.config(text="Select an action item first.")
                return
            raw_due = simpledialog.askstring(
                "Action Hub",
                "Due date (YYYY-MM-DD, MM/DD/YYYY, today, tomorrow, +7d). Leave blank to clear:",
                initialvalue="" if item.due_display == "-" else item.due_display,
                parent=win,
            )
            if raw_due is None:
                return
            due_date = parse_due_input(raw_due)
            if raw_due.strip() and due_date is None:
                info_lbl.config(text="Invalid due date format.")
                return
            line_start = f"{item.line_number}.0"
            line_end = f"{item.line_number}.end"
            current_line = self.editor.get(line_start, line_end)
            updated = set_action_due_date(current_line, due_date)
            if updated is None:
                info_lbl.config(text="Could not update due date on this line.")
                return
            self.editor.delete(line_start, line_end)
            self.editor.insert(line_start, updated)
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            info_lbl.config(text=f"Due date updated on line {item.line_number}.")
            _refresh()

        def _set_priority_selected():
            item = _selected_item()
            if not item:
                info_lbl.config(text="Select an action item first.")
                return
            priority_raw = simpledialog.askstring(
                "Action Hub",
                "Priority (critical/high/medium/low). Leave blank for normal:",
                initialvalue=item.priority,
                parent=win,
            )
            if priority_raw is None:
                return
            line_start = f"{item.line_number}.0"
            line_end = f"{item.line_number}.end"
            current_line = self.editor.get(line_start, line_end)
            updated = set_action_priority(current_line, priority_raw.strip())
            if updated is None:
                info_lbl.config(text="Could not update priority on this line.")
                return
            self.editor.delete(line_start, line_end)
            self.editor.insert(line_start, updated)
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            info_lbl.config(text=f"Priority updated on line {item.line_number}.")
            _refresh()

        def _set_effort_selected():
            item = _selected_item()
            if not item:
                info_lbl.config(text="Select an action item first.")
                return
            effort_raw = simpledialog.askstring(
                "Action Hub",
                "Effort (quick/standard/deep):",
                initialvalue=item.effort,
                parent=win,
            )
            if effort_raw is None:
                return
            line_start = f"{item.line_number}.0"
            line_end = f"{item.line_number}.end"
            current_line = self.editor.get(line_start, line_end)
            updated = set_action_effort(current_line, effort_raw.strip())
            if updated is None:
                info_lbl.config(text="Could not update effort on this line.")
                return
            self.editor.delete(line_start, line_end)
            self.editor.insert(line_start, updated)
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            info_lbl.config(text=f"Effort updated on line {item.line_number}.")
            _refresh()

        def _set_project_selected():
            item = _selected_item()
            if not item:
                info_lbl.config(text="Select an action item first.")
                return
            project_raw = simpledialog.askstring(
                "Action Hub",
                "Project/Client (leave blank to clear):",
                initialvalue=item.project or "",
                parent=win,
            )
            if project_raw is None:
                return
            line_start = f"{item.line_number}.0"
            line_end = f"{item.line_number}.end"
            current_line = self.editor.get(line_start, line_end)
            updated = set_action_project(current_line, project_raw.strip())
            if updated is None:
                info_lbl.config(text="Could not update project on this line.")
                return
            self.editor.delete(line_start, line_end)
            self.editor.insert(line_start, updated)
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            info_lbl.config(text=f"Project updated on line {item.line_number}.")
            _refresh()

        def _add_action():
            task = simpledialog.askstring("Action Hub", "Task:", parent=win)
            if task is None:
                return
            task = task.strip()
            if not task:
                info_lbl.config(text="Task is required.")
                return

            owner = simpledialog.askstring(
                "Action Hub",
                "Owner (optional):",
                parent=win,
            )
            if owner is None:
                return

            due_raw = simpledialog.askstring(
                "Action Hub",
                "Due date (optional: YYYY-MM-DD, MM/DD/YYYY, today, tomorrow, +7d):",
                parent=win,
            )
            if due_raw is None:
                return
            due_date = parse_due_input(due_raw)
            if due_raw.strip() and due_date is None:
                info_lbl.config(text="Invalid due date format.")
                return

            try:
                line = build_action_line(task=task, owner=owner.strip(), due_date=due_date)
            except ValueError as exc:
                info_lbl.config(text=str(exc))
                return

            current_text = self.editor.get("1.0", "end-1c")
            prefix = "" if not current_text.strip() else "\n"
            self.editor.insert("end-1c", f"{prefix}{line}\n")
            try:
                self.editor.edit_modified(True)
            except tk.TclError:
                pass
            info_lbl.config(text="New action item added.")
            _refresh()

        def _copy_summary():
            summary = build_action_dashboard(visible_items)
            self.root.clipboard_clear()
            self.root.clipboard_append(summary)
            info_lbl.config(text="Action summary copied from current filtered view.")

        def _insert_summary():
            summary = build_action_dashboard(visible_items)
            self.editor.insert("1.0", summary + "\n")
            self.editor.see("1.0")
            info_lbl.config(text="Action summary inserted from current filtered view.")
            _refresh()

        def _copy_focus_plan():
            summary = build_action_focus_plan(visible_items)
            self.root.clipboard_clear()
            self.root.clipboard_append(summary)
            info_lbl.config(text="Focus plan copied from current filtered view.")

        def _insert_focus_plan():
            summary = build_action_focus_plan(visible_items)
            self.editor.insert("1.0", summary + "\n")
            self.editor.see("1.0")
            info_lbl.config(text="Focus plan inserted from current filtered view.")
            _refresh()

        def _export_fancy():
            if self.export_fancy_todo_report(visible_items):
                info_lbl.config(text="Fancy to-do report exported.")
            else:
                info_lbl.config(text="Fancy to-do export canceled or failed.")

        tk.Button(btn_row_primary, text="Refresh", width=10, command=_refresh).pack(side=tk.LEFT)
        tk.Button(btn_row_primary, text="Focus Next", width=11, command=_focus_next).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_primary, text="Toggle Done", width=11, command=_toggle_done_selected).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_primary, text="Owner", width=9, command=_set_owner_selected).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_primary, text="Due", width=8, command=_set_due_selected).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_primary, text="Priority", width=9, command=_set_priority_selected).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_primary, text="Effort", width=8, command=_set_effort_selected).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_primary, text="Project", width=9, command=_set_project_selected).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_primary, text="Add Action", width=10, command=_add_action).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_primary, text="Jump", width=8, command=_jump_to_selected).pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(btn_row_secondary, text="Copy Summary", width=12, command=_copy_summary).pack(side=tk.LEFT)
        tk.Button(btn_row_secondary, text="Insert Dashboard", width=14, command=_insert_summary).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_secondary, text="Copy Focus Plan", width=13, command=_copy_focus_plan).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_secondary, text="Insert Focus Plan", width=14, command=_insert_focus_plan).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_secondary, text="Export Fancy", width=12, command=_export_fancy).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(btn_row_secondary, text="Close", width=10, command=win.destroy).pack(side=tk.RIGHT)

        status_box.bind("<<ComboboxSelected>>", lambda _e: _render_items())
        owner_box.bind("<<ComboboxSelected>>", lambda _e: _render_items())
        priority_box.bind("<<ComboboxSelected>>", lambda _e: _render_items())
        stream_box.bind("<<ComboboxSelected>>", lambda _e: _render_items())
        search_entry.bind("<KeyRelease>", lambda _e: _render_items())
        tree.bind("<Double-1>", lambda _e: _jump_to_selected())
        _refresh()
        return True

    def open_template_picker(self) -> Optional[dict[str, str]]:
        templates = list_templates()
        if not templates:
            messagebox.showinfo("Templates", "No templates are available.")
            return None

        style_options = list_template_style_presets()
        if not style_options:
            style_options = ["Professional Blue"]
        category_options = ["All"] + list_template_categories()
        result = {"template_id": None, "style": self.template_style}
        style_set_manually = {"value": False}
        selected_template_id = {"value": ""}

        win = Toplevel(self.root)
        win.title("Start From Template")
        win.geometry("1020x660")
        win.minsize(900, 560)
        win.transient(self.root)
        win.grab_set()

        outer = tk.Frame(win, padx=12, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_columnconfigure(1, weight=2)

        header = tk.Frame(outer)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)
        tk.Label(
            header,
            text="Template Gallery",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            header,
            text="Browse business-ready templates or import a polished Markdown template file.",
            font=("Segoe UI", 10),
            anchor="w",
            justify=tk.LEFT,
            fg="#4d5f7a",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

        list_frame = tk.LabelFrame(outer, text="Templates", padx=8, pady=8)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        list_frame.grid_rowconfigure(1, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        filter_row = tk.Frame(list_frame)
        filter_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        filter_row.grid_columnconfigure(1, weight=1)

        tk.Label(filter_row, text="Category:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        category_var = tk.StringVar(value="All")
        category_box = ttk.Combobox(
            filter_row,
            textvariable=category_var,
            values=category_options,
            state="readonly",
            width=17,
        )
        category_box.grid(row=0, column=1, sticky="ew", padx=(8, 8))

        tk.Label(filter_row, text="Search:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=(6, 0))
        search_var = tk.StringVar(value="")
        search_entry = ttk.Entry(filter_row, textvariable=search_var)
        search_entry.grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(6, 0))

        listbox = tk.Listbox(
            list_frame,
            exportselection=False,
            font=("Segoe UI", 11),
            activestyle="none",
            bd=2,
            relief=tk.SUNKEN,
        )
        listbox.grid(row=1, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        list_scroll.grid(row=1, column=1, sticky="ns")
        listbox.config(yscrollcommand=list_scroll.set)

        preview_frame = tk.LabelFrame(outer, text="Preview", padx=8, pady=8)
        preview_frame.grid(row=1, column=1, sticky="nsew")
        preview_frame.grid_rowconfigure(3, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        description_lbl = tk.Label(
            preview_frame,
            text="",
            justify=tk.LEFT,
            anchor="w",
            font=("Segoe UI", 11, "bold"),
        )
        description_lbl.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        metrics_lbl = tk.Label(
            preview_frame,
            text="",
            justify=tk.LEFT,
            anchor="w",
            font=("Segoe UI", 9),
            fg="#4d5f7a",
        )
        metrics_lbl.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        style_row = tk.Frame(preview_frame)
        style_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        tk.Label(style_row, text="Formatting style:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        style_var = tk.StringVar(value=self.template_style if self.template_style in style_options else style_options[0])
        style_box = ttk.Combobox(
            style_row,
            textvariable=style_var,
            values=style_options,
            state="readonly",
            width=22,
        )
        style_box.pack(side=tk.LEFT, padx=(8, 0))
        style_box.bind("<<ComboboxSelected>>", lambda _event: style_set_manually.update(value=True))

        preview = tk.Text(
            preview_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            state="disabled",
            padx=10,
            pady=10,
            relief=tk.SUNKEN,
            bd=2,
        )
        preview.grid(row=3, column=0, sticky="nsew")

        btn_row = tk.Frame(outer)
        btn_row.grid(row=2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        status_var = tk.StringVar(value="Tip: Markdown imports support YAML front matter for title/category/style.")
        tk.Label(
            outer,
            textvariable=status_var,
            justify=tk.LEFT,
            anchor="w",
            font=("Segoe UI", 9),
            fg="#4d5f7a",
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        filtered_templates: list = []

        def _render_template(tpl):
            meta = f"{tpl.category}  |  {'Built-in' if tpl.built_in else 'Custom'}  |  Default style: {tpl.preferred_style}"
            description_lbl.config(text=f"{tpl.description}\n{meta}")
            profile = summarize_template_markdown(tpl.body)
            metrics_lbl.config(
                text=(
                    f"Headings: {profile.headings}   Lists: {profile.list_items}   "
                    f"Checklists: {profile.checklist_items}   Tables: {profile.table_rows}   "
                    f"Words: {profile.words}"
                )
            )
            if (not style_set_manually["value"]) and tpl.preferred_style in style_options:
                style_var.set(tpl.preferred_style)
            preview.config(state="normal")
            preview.delete("1.0", tk.END)
            preview.insert(tk.END, tpl.body)
            preview.config(state="disabled")
            selected_template_id["value"] = tpl.template_id

        def _on_select(_event=None):
            sel = listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx >= len(filtered_templates):
                return
            _render_template(filtered_templates[idx])

        def _use_selected():
            sel = listbox.curselection()
            if not sel:
                messagebox.showinfo("Templates", "Select a template first.")
                return
            idx = sel[0]
            if idx >= len(filtered_templates):
                messagebox.showinfo("Templates", "Select a template first.")
                return
            result["template_id"] = filtered_templates[idx].template_id
            result["style"] = style_var.get().strip() or style_options[0]
            self.template_style = result["style"]
            win.destroy()

        def _apply_filters(_event=None, select_template_id: str | None = None):
            query = search_var.get().strip().casefold()
            category = category_var.get().strip()

            filtered_templates.clear()
            listbox.delete(0, tk.END)

            for tpl in templates:
                if category and category != "All" and tpl.category != category:
                    continue
                haystack = f"{tpl.title} {tpl.description} {tpl.category} {tpl.body[:800]}".casefold()
                if query and query not in haystack:
                    continue
                filtered_templates.append(tpl)
                source = "Custom" if not tpl.built_in else "Built-in"
                listbox.insert(tk.END, f"{tpl.title} [{tpl.category}] ({source})")

            if not filtered_templates:
                description_lbl.config(text="No templates match the current filters.")
                metrics_lbl.config(text="Adjust category/search filters or import a markdown template.")
                preview.config(state="normal")
                preview.delete("1.0", tk.END)
                preview.insert(tk.END, "Try clearing the search or switching category.")
                preview.config(state="disabled")
                return

            preferred_id = str(select_template_id or selected_template_id["value"] or "").strip()
            target_index = 0
            if preferred_id:
                for idx, tpl in enumerate(filtered_templates):
                    if tpl.template_id == preferred_id:
                        target_index = idx
                        break
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(target_index)
            listbox.activate(target_index)
            listbox.see(target_index)
            _render_template(filtered_templates[target_index])

        def _import_markdown():
            path = filedialog.askopenfilename(
                title="Import Markdown Template",
                parent=win,
                filetypes=[
                    ("Markdown", ("*.md", "*.markdown", "*.mdown", "*.mkd")),
                    ("Text", ("*.txt",)),
                    ("All Files", "*.*"),
                ],
            )
            if not path:
                return

            overwrite_choice = messagebox.askyesnocancel(
                "Import Markdown Template",
                "Replace an existing template with the same title if found?",
                parent=win,
            )
            if overwrite_choice is None:
                return

            category_hint = category_var.get().strip()
            if category_hint == "All":
                category_hint = ""
            style_hint = style_var.get().strip()

            try:
                imported = import_markdown_template_file(
                    path,
                    overwrite_existing=bool(overwrite_choice),
                    fallback_category=category_hint,
                    fallback_style=style_hint,
                )
            except (OSError, ValueError) as exc:
                messagebox.showerror(
                    "Import Markdown Template",
                    f"Could not import markdown template:\n{exc}",
                    parent=win,
                )
                return

            templates.clear()
            templates.extend(list_templates())
            if category_var.get().strip() != "All" and imported.category != category_var.get().strip():
                category_var.set("All")
            search_var.set("")
            _apply_filters(select_template_id=imported.template_id)
            status_var.set(
                f"Imported template: {imported.title} [{imported.category}] from {os.path.basename(path)}"
            )

        listbox.bind("<<ListboxSelect>>", _on_select)
        listbox.bind("<Double-1>", lambda _event: _use_selected())
        category_box.bind("<<ComboboxSelected>>", _apply_filters)
        search_entry.bind("<KeyRelease>", _apply_filters)

        tk.Button(
            btn_row,
            text="Import Markdown...",
            width=18,
            command=_import_markdown,
        ).pack(side=tk.LEFT)
        tk.Button(
            btn_row,
            text="Cancel",
            width=11,
            command=win.destroy,
        ).pack(side=tk.RIGHT)
        tk.Button(
            btn_row,
            text="Use Template",
            width=14,
            relief=tk.RAISED,
            bd=2,
            command=_use_selected,
        ).pack(side=tk.RIGHT, padx=(0, 8))

        _apply_filters()

        self.root.wait_window(win)
        if not result["template_id"]:
            return None
        return result

    def _hex_to_rgb(self, value: str) -> tuple[int, int, int] | None:
        text = str(value or "").strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
            return None
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)

    def _mix_hex(self, base_hex: str, target_hex: str, ratio: float) -> str:
        base_rgb = self._hex_to_rgb(base_hex)
        target_rgb = self._hex_to_rgb(target_hex)
        if not base_rgb or not target_rgb:
            return base_hex
        ratio = max(0.0, min(1.0, float(ratio)))
        mixed = []
        for idx in range(3):
            value = int(round(base_rgb[idx] + (target_rgb[idx] - base_rgb[idx]) * ratio))
            mixed.append(max(0, min(255, value)))
        return "#{:02x}{:02x}{:02x}".format(mixed[0], mixed[1], mixed[2])

    def _editor_background_is_dark(self) -> bool:
        try:
            bg = self.editor.cget("bg")
            red, green, blue = self.editor.winfo_rgb(bg)
            r = red / 65535.0
            g = green / 65535.0
            b = blue / 65535.0
            luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
            return luminance < 0.48
        except Exception:
            return False

    def _scaled_size(self, value: int, minimum: int = 8) -> int:
        scale = max(0.5, min(2.0, float(self._template_zoom) / 100.0))
        return max(minimum, int(round(int(value) * scale)))

    def _configure_template_tags(self, style_name: str):
        preset = get_template_style_preset(style_name)
        scale = max(0.5, min(2.0, float(self._template_zoom) / 100.0))
        body_font = preset.get("body_font", "Calibri")
        body_size = self._scaled_size(int(preset.get("body_size", 11)), minimum=9)
        body_color = preset.get("body_fg", "#1f2b3d")
        muted_color = preset.get("muted_fg", "#566278")
        accent = preset.get("accent", "#1f5eff")
        h1_color = preset.get("h1_fg", "#0f2b66")
        h2_color = preset.get("h2_fg", "#174899")
        h3_color = preset.get("h3_fg", "#2158a9")
        callout_bg = preset.get("callout_bg", "#eef4ff")
        table_bg = preset.get("table_bg", "#f7f9fd")
        placeholder_fg = preset.get("placeholder_fg", "#445b80")
        h1_size = self._scaled_size(22, minimum=14)
        h2_size = self._scaled_size(16, minimum=12)
        h3_size = self._scaled_size(13, minimum=11)
        rule_size = self._scaled_size(10, minimum=9)
        table_size = self._scaled_size(max(10, int(preset.get("body_size", 11))), minimum=9)

        if self._editor_background_is_dark():
            body_color = "#E6EDF8"
            muted_color = "#B5C3DA"
            accent = self._mix_hex(accent, "#A9C4FF", 0.36)
            h1_color = "#F2F6FF"
            h2_color = "#D8E6FF"
            h3_color = "#C4D9FF"
            placeholder_fg = "#AFC7F2"
            callout_bg = self._mix_hex(callout_bg, "#2A3A52", 0.72)
            table_bg = self._mix_hex(table_bg, "#1F2B40", 0.78)

        line_spacing = max(1, int(round(2 * scale)))
        heading_top = max(6, int(round(12 * scale)))
        heading_bottom = max(4, int(round(8 * scale)))

        self.editor.tag_configure(
            "tpl_body",
            font=(body_font, body_size),
            foreground=body_color,
            spacing1=line_spacing,
            spacing3=line_spacing,
        )
        self.editor.tag_configure(
            "tpl_h1",
            font=("Segoe UI", h1_size, "bold"),
            foreground=h1_color,
            spacing1=heading_top,
            spacing3=heading_bottom,
        )
        self.editor.tag_configure(
            "tpl_h2",
            font=("Segoe UI", h2_size, "bold"),
            foreground=h2_color,
            spacing1=max(5, int(round(10 * scale))),
            spacing3=max(4, int(round(6 * scale))),
        )
        self.editor.tag_configure(
            "tpl_h3",
            font=("Segoe UI", h3_size, "bold"),
            foreground=h3_color,
            spacing1=max(4, int(round(8 * scale))),
            spacing3=max(3, int(round(4 * scale))),
        )
        self.editor.tag_configure(
            "tpl_bullet",
            font=(body_font, body_size),
            foreground=body_color,
            lmargin1=18,
            lmargin2=36,
            spacing1=max(1, int(round(scale))),
            spacing3=max(1, int(round(scale))),
        )
        self.editor.tag_configure(
            "tpl_number",
            font=(body_font, body_size),
            foreground=body_color,
            lmargin1=18,
            lmargin2=36,
            spacing1=max(1, int(round(scale))),
            spacing3=max(1, int(round(scale))),
        )
        self.editor.tag_configure(
            "tpl_check",
            font=(body_font, body_size),
            foreground=body_color,
            lmargin1=18,
            lmargin2=36,
            spacing1=max(1, int(round(scale))),
            spacing3=max(1, int(round(scale))),
        )
        self.editor.tag_configure(
            "tpl_label",
            font=(body_font, body_size, "bold"),
            foreground=muted_color,
        )
        self.editor.tag_configure(
            "tpl_placeholder",
            font=(body_font, body_size, "italic"),
            foreground=placeholder_fg,
            underline=1,
        )
        self.editor.tag_configure(
            "tpl_callout",
            font=(body_font, body_size),
            foreground=body_color,
            background=callout_bg,
            lmargin1=20,
            lmargin2=20,
            rmargin=14,
            spacing1=max(2, int(round(4 * scale))),
            spacing3=max(2, int(round(4 * scale))),
        )
        self.editor.tag_configure(
            "tpl_table",
            font=("Consolas", table_size),
            foreground=body_color,
            background=table_bg,
            lmargin1=18,
            lmargin2=18,
            spacing1=max(1, int(round(2 * scale))),
            spacing3=max(1, int(round(2 * scale))),
        )
        self.editor.tag_configure(
            "tpl_rule",
            foreground=accent,
            font=("Segoe UI", rule_size, "bold"),
            spacing1=max(2, int(round(4 * scale))),
            spacing3=max(2, int(round(4 * scale))),
        )

    def _parse_template_line(self, raw_line: str) -> tuple[str, list[str], list[tuple[str, int, int]]]:
        line = (raw_line or "").rstrip("\n")
        if not line.strip():
            return "", [], []

        text = line
        line_tags = ["tpl_body"]
        spans: list[tuple[str, int, int]] = []

        if line.startswith("# "):
            return line[2:].strip(), ["tpl_h1"], []
        if line.startswith("## "):
            return line[3:].strip(), ["tpl_h2"], []
        if line.startswith("### "):
            return line[4:].strip(), ["tpl_h3"], []

        if re.match(r"^\s*[-*]{3,}\s*$", line):
            rule = "\u2500" * 46
            return rule, ["tpl_rule"], []

        if re.match(r"^\s*>\s+", line):
            text = re.sub(r"^\s*>\s+", "", line)
            line_tags = ["tpl_callout"]
        elif re.match(r"^\s*[-*]\s+\[[ xX]\]\s+", line):
            text = line
            line_tags = ["tpl_check"]
        elif re.match(r"^\s*[-*]\s+", line):
            indent = len(line) - len(line.lstrip())
            value = re.sub(r"^\s*[-*]\s+", "", line).strip()
            text = (" " * indent) + f"• {value}"
            line_tags = ["tpl_bullet"]
        elif re.match(r"^\s*\d+\.\s+", line):
            text = line
            line_tags = ["tpl_number"]
        elif line.count("|") >= 2:
            line_tags = ["tpl_table"]

        if line_tags == ["tpl_body"] and ":" in text:
            key, _rest = text.split(":", 1)
            label = key.strip()
            if 0 < len(label) <= 34 and re.match(r"^[A-Za-z0-9 /&()\-]+$", label):
                label_end = text.find(":") + 1
                spans.append(("tpl_label", 0, label_end))

        for match in re.finditer(r"\[[^\]\n]{1,80}\]", text):
            token = match.group(0)
            if token in {"[ ]", "[x]", "[X]"}:
                continue
            spans.append(("tpl_placeholder", match.start(), match.end()))

        return text, line_tags, spans

    def _insert_logo_header(self):
        path = (self.default_logo_path or "").strip()
        if not path:
            return
        if not os.path.exists(path):
            return
        try:
            if HAS_PIL:
                image = Image.open(path)
                image.thumbnail((240, 100))
                photo = ImageTk.PhotoImage(image)
                self.images.append(photo)
                self.editor.image_create(tk.INSERT, image=photo)
                self.editor.insert(tk.INSERT, "\n")
                return
        except Exception:
            pass
        # Fallback marker if image cannot be loaded.
        self.editor.insert(tk.INSERT, f"[Logo: {os.path.basename(path)}]\n")

    def apply_template(self, content: str, style: str = "Professional Blue"):
        if not content:
            return False
        style_name = (style or "Professional Blue").strip()
        self.template_style = style_name
        self._configure_template_tags(style_name)
        self.editor.delete("1.0", tk.END)
        self.editor.mark_set(tk.INSERT, "1.0")
        self._insert_logo_header()
        lines = content.rstrip("\n").splitlines()
        if not lines:
            lines = [""]
        for raw_line in lines:
            line_start = self.editor.index(tk.INSERT)
            text, line_tags, spans = self._parse_template_line(raw_line)
            self.editor.insert(tk.INSERT, text)
            line_end = self.editor.index(tk.INSERT)

            for tag in line_tags:
                self.editor.tag_add(tag, line_start, line_end)

            for tag, start_offset, end_offset in spans:
                if end_offset <= start_offset:
                    continue
                start_idx = f"{line_start}+{start_offset}c"
                end_idx = f"{line_start}+{end_offset}c"
                self.editor.tag_add(tag, start_idx, end_idx)

            self.editor.insert(tk.INSERT, "\n")

        self.editor.mark_set(tk.INSERT, "1.0")
        self.editor.see("1.0")
        return True
