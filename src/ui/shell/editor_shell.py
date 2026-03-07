import tkinter as tk

from src.ui.contracts import UiViewState
from src.ui.shell.command_bar import CommandBar
from src.ui.shell.dev_console import DevConsole
from src.ui.shell.inspector_panel import InspectorPanel
from src.ui.shell.navigation_panel import NavigationPanel
from src.ui.shell.status_strip import StatusStrip
from src.ui.shell.top_strip import TopStrip
from src.ui.theme.ttk_styles import apply_ttk_styles
from src.ui.workspace import Workspace


class EditorShell(tk.Frame):
    def __init__(self, parent, app, colors, view_state: UiViewState):
        super().__init__(parent, bg=colors["bg_app"], relief=tk.GROOVE, bd=2)
        self.app = app
        self.colors = colors
        self.view_state = view_state
        self.right_panel_visible = False
        self._pane_capture_pending = False
        self._sash_clamp_pending = False

        self.nav_min_width = 220
        self.center_min_width = 520
        self.inspector_min_width = 240

        ui_settings = getattr(app, "ui_settings", {})
        if not isinstance(ui_settings, dict):
            ui_settings = {}

        self.left_panel_width = self._safe_int(
            ui_settings.get("left_panel_width", 264),
            fallback=264,
            minimum=self.nav_min_width,
            maximum=1200,
        )
        self.right_panel_width = self._safe_int(
            ui_settings.get("right_panel_width", 320),
            fallback=320,
            minimum=self.inspector_min_width,
            maximum=1200,
        )
        self.main_sash_left = self._safe_int(ui_settings.get("main_sash_left", 0), fallback=0, minimum=0, maximum=20000)
        self.main_sash_right = self._safe_int(ui_settings.get("main_sash_right", 0), fallback=0, minimum=0, maximum=20000)
        self.command_bar_collapsed = self._safe_bool(ui_settings.get("command_bar_collapsed"), fallback=False)
        self.density = ui_settings.get("density", "comfortable")
        if self.density not in {"comfortable", "compact"}:
            self.density = "comfortable"

        self.top_height = 58 if self.density == "comfortable" else 50
        self.command_min_height = 96 if self.density == "comfortable" else 84
        self.command_max_height = 420
        self.command_height = self._safe_int(
            ui_settings.get("command_bar_height", 132 if self.density == "comfortable" else 112),
            fallback=132 if self.density == "comfortable" else 112,
            minimum=self.command_min_height,
            maximum=self.command_max_height,
        )
        self.status_height = 30 if self.density == "comfortable" else 28
        self.grid_rowconfigure(0, minsize=self.top_height)
        self.grid_rowconfigure(1, minsize=self.command_height)
        self.grid_rowconfigure(2, minsize=6)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, minsize=self.status_height)
        self.grid_columnconfigure(0, weight=1)
        self._command_drag_start_y = 0
        self._command_drag_start_height = self.command_height

        self.top_strip = TopStrip(self, colors)
        self.top_strip.grid(row=0, column=0, sticky="ew")

        self.command_bar = CommandBar(self, colors)
        self.command_bar.grid(row=1, column=0, sticky="nsew")
        self.command_bar.grid_propagate(False)
        self.command_bar.configure(height=self.command_height)

        self.command_resize_grip = tk.Frame(
            self,
            bg=colors["border"],
            height=6,
            cursor="sb_v_double_arrow",
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.command_resize_grip.grid(row=2, column=0, sticky="ew")
        self.command_resize_line = tk.Frame(
            self.command_resize_grip,
            bg=colors["text_secondary"],
            height=2,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.command_resize_line.place(relx=0.5, rely=0.5, relwidth=0.18, anchor="center")
        self.command_resize_grip.bind("<ButtonPress-1>", self._on_command_resize_start, add="+")
        self.command_resize_grip.bind("<B1-Motion>", self._on_command_resize_drag, add="+")
        self.command_resize_grip.bind("<ButtonRelease-1>", self._on_command_resize_end, add="+")

        self.content_host = tk.Frame(self, bg=colors["bg_app"])
        self.content_host.grid(row=3, column=0, sticky="nsew", padx=4, pady=4)
        self.content_host.grid_rowconfigure(0, weight=1)
        self.content_host.grid_columnconfigure(0, weight=1)

        self.content_pane = tk.PanedWindow(
            self.content_host,
            orient=tk.HORIZONTAL,
            bg=colors["border"],
            sashwidth=12,
            sashpad=2,
            sashrelief=tk.RAISED,
            showhandle=True,
            handlesize=12,
            bd=0,
            relief=tk.FLAT,
        )
        self.content_pane.grid(row=0, column=0, sticky="nsew")
        self.content_pane.bind("<B1-Motion>", self._on_main_pane_interaction, add="+")
        self.content_pane.bind("<ButtonRelease-1>", self._on_main_pane_interaction, add="+")
        self.content_pane.bind("<Configure>", self._on_content_pane_configure, add="+")

        self.nav_panel = NavigationPanel(self.content_pane, colors, width=self.left_panel_width)

        self.center_column = tk.Frame(self.content_pane, bg=colors["bg_app"])
        self.center_column.grid_rowconfigure(0, weight=1)
        self.center_column.grid_columnconfigure(0, weight=1)

        self.workspace = Workspace(self.center_column, colors, initial_zoom=view_state.zoom)
        self.workspace.grid(row=0, column=0, sticky="nsew")

        self.dev_console = DevConsole(self.center_column, colors)
        self.dev_console.grid(row=1, column=0, sticky="ew")

        self.inspector_panel = InspectorPanel(self.content_pane, colors, width=self.right_panel_width)

        self.content_pane.add(self.nav_panel, minsize=self.nav_min_width, width=self.left_panel_width, stretch="never")
        self.content_pane.add(self.center_column, minsize=self.center_min_width, stretch="always")
        self.content_pane.add(
            self.inspector_panel,
            minsize=self.inspector_min_width,
            width=self.right_panel_width,
            stretch="never",
        )

        self.status_strip = StatusStrip(self, colors)
        self.status_strip.grid(row=4, column=0, sticky="ew")

        apply_ttk_styles(self, colors, density=self.density)
        self.after_idle(self._restore_main_sashes)
        self.set_view_state(view_state)
        self.set_right_panel_visible(bool(ui_settings.get("right_panel_visible", False)))
        if self.command_bar_collapsed and not self.view_state.focus_mode:
            self.command_bar.grid_remove()
        self._update_command_row_minsize()

    def bind_commands(self, handler):
        self.top_strip.bind_commands(handler)
        self.command_bar.bind_commands(handler)
        self.nav_panel.bind_commands(handler)
        self.status_strip.bind_commands(handler)

    def set_view_state(self, state: UiViewState):
        self.view_state = state
        self.top_strip.set_document(self.top_strip.doc_title.cget("text"), state.dirty)
        self.top_strip.set_focus_mode(state.focus_mode)
        self.set_zoom(state.zoom)

        if state.focus_mode:
            self.top_strip.grid()
            self.command_bar.grid_remove()
            self.command_resize_grip.grid_remove()
            self.status_strip.grid()
            self._set_sidebar_visible(False)
            self._set_inspector_visible(False)
            self.dev_console.grid_remove()
            self._update_command_row_minsize()
            return

        self.top_strip.grid()
        if self.command_bar_collapsed:
            self.command_bar.grid_remove()
            self.command_resize_grip.grid_remove()
        else:
            self.command_bar.grid()
            self.command_resize_grip.grid()
        self.status_strip.grid()

        self._set_sidebar_visible(state.sidebar_visible)
        self._set_inspector_visible(self.right_panel_visible)

        if state.show_console:
            self.dev_console.grid()
        else:
            self.dev_console.grid_remove()
        self._update_command_row_minsize()

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["bg_app"])
        self.content_host.config(bg=colors["bg_app"])
        self.content_pane.config(bg=colors["border"])
        self.center_column.config(bg=colors["bg_app"])
        self.command_resize_grip.config(bg=colors["border"])
        self.command_resize_line.config(bg=colors["text_secondary"])
        apply_ttk_styles(self, colors, density=self.density)
        self.top_strip.update_theme(colors)
        self.command_bar.update_theme(colors)
        self.nav_panel.update_theme(colors)
        self.inspector_panel.update_theme(colors)
        self.workspace.update_theme(colors)
        self.status_strip.update_theme(colors)
        self.dev_console.update_theme(colors)

    def set_status(self, text: str):
        self.status_strip.set_status(text)

    def set_zoom(self, value: int):
        self.status_strip.set_zoom(value)
        self.inspector_panel.set_zoom(value)
        self.workspace.set_zoom(value)

    def set_document_title(self, title: str, dirty: bool):
        self.top_strip.set_document(title, dirty)

    def set_navigation_items(self, items):
        self.nav_panel.set_items(items)

    def set_recent_files(self, recents):
        self.nav_panel.set_recents(recents)

    def set_document_meta(self, words: int, chars: int, lines: int):
        self.inspector_panel.set_document_stats(words, chars, lines)

    def append_console(self, message: str):
        self.dev_console.append(message)

    def set_right_panel_visible(self, visible: bool):
        self.right_panel_visible = bool(visible)
        if self.view_state.focus_mode:
            self._set_inspector_visible(False)
            return
        self._set_inspector_visible(self.right_panel_visible)

    def set_rulers_visible(self, visible: bool):
        self.workspace.set_rulers_visible(visible)

    def get_editor(self):
        return self.workspace.get_editor()

    def capture_layout_preferences(self) -> dict:
        self._capture_layout_values()
        return {
            "left_panel_width": self.left_panel_width,
            "right_panel_width": self.right_panel_width,
            "main_sash_left": self.main_sash_left,
            "main_sash_right": self.main_sash_right,
            "command_bar_collapsed": self.command_bar_collapsed,
            "command_bar_height": self.command_height,
        }

    def set_command_bar_collapsed(self, collapsed: bool):
        self.command_bar_collapsed = bool(collapsed)
        if self.view_state.focus_mode:
            self.command_bar.grid_remove()
            self.command_resize_grip.grid_remove()
            self._update_command_row_minsize()
            return
        if self.command_bar_collapsed:
            self.command_bar.grid_remove()
            self.command_resize_grip.grid_remove()
        else:
            self.command_bar.grid()
            self.command_resize_grip.grid()
        self._update_command_row_minsize()

    def _on_main_pane_interaction(self, _event=None):
        if self._pane_capture_pending:
            return
        self._pane_capture_pending = True
        self.after(120, self._capture_layout_values)

    def _on_content_pane_configure(self, _event=None):
        if self._sash_clamp_pending:
            return
        self._sash_clamp_pending = True
        self.after_idle(self._clamp_sashes_to_bounds)

    def _update_command_row_minsize(self):
        should_show = not self.view_state.focus_mode and not self.command_bar_collapsed
        if should_show:
            self.command_height = self._coerce_command_height(self.command_height)
            self.command_bar.configure(height=self.command_height)
            self.grid_rowconfigure(1, minsize=self.command_height)
            self.grid_rowconfigure(2, minsize=6)
        else:
            self.grid_rowconfigure(1, minsize=0)
            self.grid_rowconfigure(2, minsize=0)

    def _capture_layout_values(self):
        self._pane_capture_pending = False
        try:
            if str(self.command_bar.winfo_manager()).strip():
                cmd_height = int(self.command_bar.winfo_height())
                if cmd_height > 0:
                    self.command_height = self._coerce_command_height(cmd_height)

            if self._pane_present(self.nav_panel):
                width = int(self.nav_panel.winfo_width())
                if width > 0:
                    self.left_panel_width = max(self.nav_min_width, width)
            if self._pane_present(self.inspector_panel):
                width = int(self.inspector_panel.winfo_width())
                if width > 0:
                    self.right_panel_width = max(self.inspector_min_width, width)

            pane_count = self._pane_count()
            if pane_count >= 2:
                self.main_sash_left = max(0, int(self.content_pane.sash_coord(0)[0]))
            if pane_count >= 3:
                self.main_sash_right = max(0, int(self.content_pane.sash_coord(1)[0]))
        except tk.TclError:
            return

    def _restore_main_sashes(self):
        try:
            pane_count = self._pane_count()
            if pane_count >= 2 and self.main_sash_left > 0:
                self.content_pane.sash_place(0, self.main_sash_left, 0)
            if pane_count >= 3 and self.main_sash_right > 0:
                self.content_pane.sash_place(1, self.main_sash_right, 0)
            self._clamp_sashes_to_bounds()
        except tk.TclError:
            return

    def _clamp_sashes_to_bounds(self):
        self._sash_clamp_pending = False
        try:
            pane_count = self._pane_count()
            if pane_count < 2:
                return

            total_width = int(self.content_pane.winfo_width())
            if total_width <= 0:
                return

            if pane_count == 2:
                left_min = self.nav_min_width if self._pane_present(self.nav_panel) else self.center_min_width
                right_min = self.center_min_width if self._pane_present(self.nav_panel) else self.inspector_min_width
                min_left = left_min
                max_left = max(min_left, total_width - right_min)
                left_x = int(self.content_pane.sash_coord(0)[0])
                clamped_left = max(min_left, min(max_left, left_x))
                if clamped_left != left_x:
                    self.content_pane.sash_place(0, clamped_left, 0)
                self.main_sash_left = max(0, clamped_left)
                return

            if pane_count >= 3:
                left_x = int(self.content_pane.sash_coord(0)[0])
                right_x = int(self.content_pane.sash_coord(1)[0])
                min_left = self.nav_min_width
                max_left = max(min_left, total_width - self.center_min_width - self.inspector_min_width)
                clamped_left = max(min_left, min(max_left, left_x))

                min_right = clamped_left + self.center_min_width
                max_right = max(min_right, total_width - self.inspector_min_width)
                clamped_right = max(min_right, min(max_right, right_x))

                if clamped_left != left_x:
                    self.content_pane.sash_place(0, clamped_left, 0)
                if clamped_right != right_x:
                    self.content_pane.sash_place(1, clamped_right, 0)

                self.main_sash_left = max(0, clamped_left)
                self.main_sash_right = max(0, clamped_right)
        except tk.TclError:
            return

    def _set_sidebar_visible(self, visible: bool):
        if visible:
            if not self._pane_present(self.nav_panel):
                self.content_pane.add(
                    self.nav_panel,
                    before=self.center_column,
                    minsize=self.nav_min_width,
                    width=self.left_panel_width,
                    stretch="never",
                )
                self.after_idle(self._restore_main_sashes)
            else:
                self.content_pane.paneconfigure(
                    self.nav_panel,
                    minsize=self.nav_min_width,
                    width=self.left_panel_width,
                    stretch="never",
                )
            return

        if self._pane_present(self.nav_panel):
            self._capture_layout_values()
            self.content_pane.forget(self.nav_panel)

    def _set_inspector_visible(self, visible: bool):
        if visible:
            if not self._pane_present(self.inspector_panel):
                self.content_pane.add(
                    self.inspector_panel,
                    after=self.center_column,
                    minsize=self.inspector_min_width,
                    width=self.right_panel_width,
                    stretch="never",
                )
                self.after_idle(self._restore_main_sashes)
            else:
                self.content_pane.paneconfigure(
                    self.inspector_panel,
                    minsize=self.inspector_min_width,
                    width=self.right_panel_width,
                    stretch="never",
                )
            return

        if self._pane_present(self.inspector_panel):
            self._capture_layout_values()
            self.content_pane.forget(self.inspector_panel)

    def _pane_count(self):
        try:
            return len(self.content_pane.panes())
        except tk.TclError:
            return 0

    def _pane_present(self, widget):
        try:
            return str(widget) in self.content_pane.panes()
        except tk.TclError:
            return False

    def _safe_int(self, value, fallback, minimum=None, maximum=None):
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = int(fallback)
        if minimum is not None:
            result = max(int(minimum), result)
        if maximum is not None:
            result = min(int(maximum), result)
        return int(result)

    def _safe_bool(self, value, fallback=False):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off", ""}:
            return False
        return bool(fallback)

    def _coerce_command_height(self, height: int) -> int:
        viewport_height = int(self.winfo_height())
        dynamic_max = self.command_max_height
        minimum_layout_height = self.top_height + self.status_height + self.command_min_height + 120
        if viewport_height >= minimum_layout_height:
            dynamic_max = max(
                self.command_min_height,
                viewport_height - self.top_height - self.status_height - 180,
            )
        max_height = max(self.command_min_height, min(self.command_max_height, dynamic_max))
        return self._safe_int(height, self.command_height, minimum=self.command_min_height, maximum=max_height)

    def _on_command_resize_start(self, event):
        if self.command_bar_collapsed or self.view_state.focus_mode:
            return "break"
        self._command_drag_start_y = int(getattr(event, "y_root", 0))
        self._command_drag_start_height = int(self.command_height)
        self.command_resize_grip.configure(bg=self.colors["accent_hover"])
        return "break"

    def _on_command_resize_drag(self, event):
        if self.command_bar_collapsed or self.view_state.focus_mode:
            return "break"
        current_y = int(getattr(event, "y_root", self._command_drag_start_y))
        delta = current_y - self._command_drag_start_y
        self.command_height = self._coerce_command_height(self._command_drag_start_height + delta)
        self._update_command_row_minsize()
        return "break"

    def _on_command_resize_end(self, _event=None):
        self.command_resize_grip.configure(bg=self.colors["border"])
        self._capture_layout_values()
        return "break"
