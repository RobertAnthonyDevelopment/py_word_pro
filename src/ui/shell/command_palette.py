import tkinter as tk
from typing import Any

from src.ui.contracts import UiCommandRequest


def _command_item_key(item: dict[str, Any]) -> str:
    command_id = str(item.get("command_id", "")).strip()
    payload = item.get("payload")
    if not isinstance(payload, dict) or not payload:
        return command_id
    pairs = [f"{k}={payload[k]}" for k in sorted(payload)]
    return f"{command_id}|{'&'.join(pairs)}"


def _is_subsequence(needle: str, haystack: str) -> bool:
    if not needle:
        return True
    pos = 0
    for char in haystack:
        if pos < len(needle) and char == needle[pos]:
            pos += 1
            if pos == len(needle):
                return True
    return pos == len(needle)


def rank_command_items(items: list[dict[str, Any]], query: str, recent_keys: list[str] | None = None, limit: int = 80):
    normalized = str(query or "").strip().lower()
    tokens = [token for token in normalized.split(" ") if token]
    recency = {str(key): index for index, key in enumerate(recent_keys or [])}

    ranked = []
    for item in items:
        label = str(item.get("label", "")).strip()
        command_id = str(item.get("command_id", "")).strip()
        if not label or not command_id:
            continue

        group = str(item.get("group", "")).strip()
        shortcut = str(item.get("shortcut", "")).strip()
        keywords = item.get("keywords", [])
        if isinstance(keywords, str):
            keywords_text = keywords
        elif isinstance(keywords, (list, tuple, set)):
            keywords_text = " ".join(str(value) for value in keywords)
        else:
            keywords_text = ""

        label_lower = label.lower()
        search_blob = " ".join([label, command_id, group, shortcut, keywords_text]).lower()
        item_key = _command_item_key(item)
        recency_rank = recency.get(item_key, 10_000)

        if not tokens:
            score = 0
            ranked.append((recency_rank, -score, label_lower, item))
            continue

        score = 0
        if normalized in label_lower:
            score += 120
            if label_lower.startswith(normalized):
                score += 100
        elif normalized in search_blob:
            score += 50

        compact_query = normalized.replace(" ", "")
        compact_label = label_lower.replace(" ", "")
        if compact_query and _is_subsequence(compact_query, compact_label):
            score += 35

        missing_token = False
        for token in tokens:
            if token in label_lower:
                score += 40
            elif token in search_blob:
                score += 14
            else:
                missing_token = True
                break
        if missing_token:
            continue

        ranked.append((recency_rank, -score, label_lower, item))

    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in ranked[: max(1, int(limit))]]


class CommandPalette:
    def __init__(self, root, handler):
        self.root = root
        self._handler = handler
        self._win = None
        self._query_var = tk.StringVar(master=root, value="")
        self._status_var = tk.StringVar(master=root, value="")
        self._listbox = None
        self._commands = []
        self._rows = []
        self._recent_keys = []
        self._colors = {}

    def open(self, commands: list[dict[str, Any]], colors: dict[str, str]):
        self._commands = [item for item in commands if isinstance(item, dict)]
        self._colors = dict(colors or {})
        if self._win is None or not self._win.winfo_exists():
            self._build_window()
        self.update_theme(self._colors)
        self._query_var.set("")
        self._refresh_results()
        self._center_window()
        self._win.deiconify()
        self._win.lift()
        self._search_entry.focus_set()
        self._search_entry.select_range(0, tk.END)

    def update_theme(self, colors: dict[str, str]):
        self._colors = dict(colors or {})
        if self._win is None or not self._win.winfo_exists():
            return
        bg = self._colors.get("bg_panel", "#EFF3F9")
        surface = self._colors.get("bg_surface", "#FFFFFF")
        text = self._colors.get("text_primary", "#152033")
        secondary = self._colors.get("text_secondary", "#3D4F68")
        border = self._colors.get("border", "#C8D3E5")
        accent = self._colors.get("accent", "#2A63F6")

        self._win.config(bg=bg)
        self._container.config(bg=bg, highlightbackground=border)
        self._header.config(bg=bg, fg=text)
        self._hint.config(bg=bg, fg=secondary)
        self._query_row.config(bg=bg)
        self._query_label.config(bg=bg, fg=secondary)
        self._result_frame.config(bg=bg)
        self._listbox.config(
            bg=surface,
            fg=text,
            selectbackground=accent,
            selectforeground="#FFFFFF",
            highlightbackground=border,
            highlightcolor=accent,
        )
        self._status.config(bg=bg, fg=secondary)

    def _build_window(self):
        self._win = tk.Toplevel(self.root)
        self._win.title("Command Palette")
        self._win.geometry("760x480")
        self._win.minsize(640, 380)
        self._win.transient(self.root)

        self._container = tk.Frame(self._win, bd=1, relief=tk.SOLID)
        self._container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._container.grid_columnconfigure(0, weight=1)
        self._container.grid_rowconfigure(2, weight=1)

        self._header = tk.Label(
            self._container,
            text="Command Palette",
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        self._header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 2))

        self._hint = tk.Label(
            self._container,
            text="Search actions by name, shortcut, or keyword. Press Enter to run.",
            font=("Segoe UI", 10),
            anchor="w",
        )
        self._hint.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

        self._query_row = tk.Frame(self._container)
        self._query_row.grid(row=2, column=0, sticky="new", padx=12, pady=(0, 0))
        self._query_row.grid_columnconfigure(1, weight=1)

        self._query_label = tk.Label(self._query_row, text="Command", font=("Segoe UI", 10, "bold"))
        self._query_label.grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))

        self._search_entry = tk.Entry(
            self._query_row,
            textvariable=self._query_var,
            relief=tk.SUNKEN,
            bd=1,
            font=("Segoe UI", 12),
        )
        self._search_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self._search_entry.bind("<KeyRelease>", self._on_entry_keyrelease, add="+")
        self._search_entry.bind("<Down>", lambda _e: self._move_selection(1), add="+")
        self._search_entry.bind("<Up>", lambda _e: self._move_selection(-1), add="+")
        self._search_entry.bind("<Return>", lambda _e: self._execute_selected(), add="+")
        self._search_entry.bind("<Escape>", lambda _e: self._close(), add="+")

        self._result_frame = tk.Frame(self._container)
        self._result_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 0))
        self._result_frame.grid_columnconfigure(0, weight=1)
        self._result_frame.grid_rowconfigure(0, weight=1)

        self._listbox = tk.Listbox(
            self._result_frame,
            activestyle="none",
            relief=tk.SOLID,
            bd=1,
            font=("Consolas", 11),
            exportselection=False,
        )
        self._listbox.grid(row=0, column=0, sticky="nsew")
        self._listbox.bind("<Double-Button-1>", lambda _e: self._execute_selected(), add="+")
        self._listbox.bind("<Return>", lambda _e: self._execute_selected(), add="+")
        self._listbox.bind("<Escape>", lambda _e: self._close(), add="+")
        self._listbox.bind("<<ListboxSelect>>", lambda _e: self._update_status(), add="+")

        scroll = tk.Scrollbar(self._result_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._listbox.configure(yscrollcommand=scroll.set)

        self._status = tk.Label(self._container, textvariable=self._status_var, anchor="w", font=("Segoe UI", 10))
        self._status.grid(row=4, column=0, sticky="ew", padx=12, pady=(8, 12))

        self._win.bind("<Escape>", lambda _e: self._close(), add="+")
        self._win.protocol("WM_DELETE_WINDOW", self._close)

    def _on_entry_keyrelease(self, event):
        if event.keysym in {"Up", "Down", "Return", "Escape"}:
            return
        self._refresh_results()

    def _refresh_results(self):
        if self._listbox is None:
            return
        query = self._query_var.get()
        self._rows = rank_command_items(self._commands, query, recent_keys=self._recent_keys, limit=120)
        self._listbox.delete(0, tk.END)
        for item in self._rows:
            self._listbox.insert(tk.END, self._format_row(item))
        if self._rows:
            self._listbox.selection_set(0)
            self._listbox.activate(0)
            self._listbox.see(0)
        self._update_status()

    def _format_row(self, item: dict[str, Any]) -> str:
        label = str(item.get("label", "")).strip()
        shortcut = str(item.get("shortcut", "")).strip()
        group = str(item.get("group", "")).strip()
        return f"{label:<34} {shortcut:<18} {group}"

    def _move_selection(self, delta: int):
        if self._listbox is None or not self._rows:
            return "break"
        selected = self._listbox.curselection()
        index = selected[0] if selected else 0
        next_index = max(0, min(len(self._rows) - 1, index + int(delta)))
        self._listbox.selection_clear(0, tk.END)
        self._listbox.selection_set(next_index)
        self._listbox.activate(next_index)
        self._listbox.see(next_index)
        self._update_status()
        return "break"

    def _selected_item(self) -> dict[str, Any] | None:
        if self._listbox is None:
            return None
        selected = self._listbox.curselection()
        if not selected:
            return None
        index = int(selected[0])
        if index < 0 or index >= len(self._rows):
            return None
        return self._rows[index]

    def _execute_selected(self):
        item = self._selected_item()
        if not item:
            return "break"
        request = UiCommandRequest(
            command_id=str(item.get("command_id", "")).strip(),
            payload=item.get("payload") if isinstance(item.get("payload"), dict) else None,
        )
        if not request.command_id:
            return "break"
        self._remember(_command_item_key(item))
        if callable(self._handler):
            self._handler(request)
        self._close()
        return "break"

    def _remember(self, command_key: str):
        key = str(command_key or "").strip()
        if not key:
            return
        self._recent_keys = [value for value in self._recent_keys if value != key]
        self._recent_keys.insert(0, key)
        self._recent_keys = self._recent_keys[:20]

    def _update_status(self):
        count = len(self._rows)
        item = self._selected_item()
        if not item:
            self._status_var.set(f"{count} command(s)")
            return
        label = str(item.get("label", "")).strip() or "Command"
        shortcut = str(item.get("shortcut", "")).strip()
        if shortcut:
            self._status_var.set(f"{label}  [{shortcut}]")
        else:
            self._status_var.set(label)

    def _center_window(self):
        if self._win is None or not self._win.winfo_exists():
            return
        self._win.update_idletasks()
        width = self._win.winfo_width()
        height = self._win.winfo_height()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 4)
        self._win.geometry(f"{width}x{height}+{x}+{y}")

    def _close(self):
        if self._win is None or not self._win.winfo_exists():
            return
        self._win.withdraw()
