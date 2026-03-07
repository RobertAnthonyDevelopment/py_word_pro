import tkinter as tk
from tkinter import font as tkfont


class Workspace(tk.Frame):
    def __init__(self, parent, colors, initial_zoom=100):
        super().__init__(parent, bg=colors["bg"])
        self.colors = colors
        self.zoom_level = int(initial_zoom)
        self.rulers_visible = True
        self._ruler_redraw_scheduled = False

        self.desk_frame = tk.Frame(self, bg=colors.get("bg_app", colors["bg"]))
        self.desk_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.desk_frame.grid_rowconfigure(0, weight=1)
        self.desk_frame.grid_columnconfigure(0, weight=1)

        self.v_scroll = tk.Scrollbar(self.desk_frame, orient=tk.VERTICAL, width=16)
        self.h_scroll = tk.Scrollbar(self.desk_frame, orient=tk.HORIZONTAL, width=16)
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        self.page_shadow = tk.Frame(
            self.desk_frame,
            bg=colors.get("border_dark", colors.get("border", "#999")),
            bd=0,
            highlightthickness=1,
            highlightbackground=colors.get("border_dark", colors.get("border", "#999")),
        )
        self.page_shadow.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.page_container = tk.Frame(
            self.page_shadow,
            bg=colors.get("border_light", "#FFFFFF"),
            bd=3,
            relief=tk.RAISED,
        )
        self.page_container.pack(fill=tk.BOTH, expand=True, padx=(0, 2), pady=(0, 2))
        self.page_container.grid_rowconfigure(1, weight=1)
        self.page_container.grid_columnconfigure(1, weight=1)

        self.ruler_corner = tk.Frame(
            self.page_container,
            bg=colors.get("ruler", "#E7ECF3"),
            width=48,
            height=28,
            bd=1,
            relief=tk.GROOVE,
            highlightthickness=1,
            highlightbackground=colors.get("border", "#C8D3E3"),
        )
        self.ruler_corner.grid(row=0, column=0, sticky="nsew")
        self.ruler_corner.grid_propagate(False)

        self.h_ruler = tk.Canvas(
            self.page_container,
            height=28,
            bg=colors.get("ruler", "#E7ECF3"),
            bd=0,
            highlightthickness=1,
            highlightbackground=colors.get("border", "#C8D3E3"),
        )
        self.h_ruler.grid(row=0, column=1, sticky="ew")

        self.v_ruler = tk.Canvas(
            self.page_container,
            width=48,
            bg=colors.get("ruler", "#E7ECF3"),
            bd=0,
            highlightthickness=1,
            highlightbackground=colors.get("border", "#C8D3E3"),
        )
        self.v_ruler.grid(row=1, column=0, sticky="ns")

        self.text_holder = tk.Frame(self.page_container, bg=colors["paper"])
        self.text_holder.grid(row=1, column=1, sticky="nsew")
        self.text_holder.grid_rowconfigure(0, weight=1)
        self.text_holder.grid_columnconfigure(0, weight=1)

        self.text_area = tk.Text(
            self.text_holder,
            font=("Calibri", 12),
            bg=colors["paper"],
            fg=colors["text"],
            insertbackground=colors["text"],
            wrap=tk.WORD,
            padx=24,
            pady=18,
            spacing1=3,
            spacing2=3,
            spacing3=3,
            undo=True,
            autoseparators=True,
            maxundo=2000,
            tabs=(24,),
            yscrollcommand=self._on_text_yscroll,
            xscrollcommand=self._on_text_xscroll,
        )
        self.text_area.grid(row=0, column=0, sticky="nsew")

        self.v_scroll.config(command=self._yview)
        self.h_scroll.config(command=self._xview)

        self.text_area.tag_configure("highlight_find", background="yellow", foreground="black")
        self.text_area.tag_configure("error_spell", underline=True, underlinefg="red")

        self.text_area.bind("<KeyRelease>", self._schedule_ruler_redraw, add="+")
        self.text_area.bind("<ButtonRelease-1>", self._schedule_ruler_redraw, add="+")
        self.text_area.bind("<MouseWheel>", self._schedule_ruler_redraw, add="+")
        self.text_area.bind("<Configure>", self._schedule_ruler_redraw, add="+")
        self.text_area.bind("<FocusIn>", self._schedule_ruler_redraw, add="+")
        self.h_ruler.bind("<Configure>", self._schedule_ruler_redraw, add="+")
        self.v_ruler.bind("<Configure>", self._schedule_ruler_redraw, add="+")

        self.after(120, self._redraw_rulers)

    def get_editor(self):
        return self.text_area

    def set_zoom(self, value: int):
        self.zoom_level = max(50, min(200, int(value)))
        self._redraw_rulers()

    def set_rulers_visible(self, visible: bool):
        self.rulers_visible = bool(visible)
        if self.rulers_visible:
            self.ruler_corner.grid()
            self.h_ruler.grid()
            self.v_ruler.grid()
        else:
            self.ruler_corner.grid_remove()
            self.h_ruler.grid_remove()
            self.v_ruler.grid_remove()

    def _on_text_yscroll(self, first: str, last: str):
        self.v_scroll.set(first, last)
        self._schedule_ruler_redraw()

    def _on_text_xscroll(self, first: str, last: str):
        self.h_scroll.set(first, last)
        self._schedule_ruler_redraw()

    def _yview(self, *args):
        self.text_area.yview(*args)
        self._schedule_ruler_redraw()

    def _xview(self, *args):
        self.text_area.xview(*args)
        self._schedule_ruler_redraw()

    def _schedule_ruler_redraw(self, _event=None):
        if not self.rulers_visible:
            return
        if self._ruler_redraw_scheduled:
            return
        self._ruler_redraw_scheduled = True
        self.after_idle(self._redraw_rulers)

    def _char_width_px(self) -> int:
        try:
            editor_font = tkfont.Font(font=self.text_area.cget("font"))
            width = editor_font.measure("0")
            return max(6, int(width))
        except tk.TclError:
            return 7

    def _redraw_rulers(self):
        self._ruler_redraw_scheduled = False
        if not self.rulers_visible:
            return

        self.h_ruler.delete("all")
        self.v_ruler.delete("all")

        ruler_bg = self.colors.get("ruler", "#E7ECF3")
        border = self.colors.get("border", "#C8D3E3")
        text_secondary = self.colors.get("text_secondary", "#4A5A70")
        accent = self.colors.get("accent", "#1F5EFF")

        width = max(0, self.h_ruler.winfo_width())
        height = max(0, self.h_ruler.winfo_height())
        if width > 0 and height > 0:
            self.h_ruler.create_rectangle(0, 0, width, height, fill=ruler_bg, outline="")
            left_pad = self._safe_int(self.text_area.cget("padx"), 0)
            # Font metrics already reflect zoom-scaled text size.
            char_w = max(6, int(self._char_width_px()))
            for i in range(0, max(1, int((width - left_pad) / char_w) + 2)):
                x = left_pad + i * char_w
                if x < 0 or x > width:
                    continue
                if i % 10 == 0:
                    tick = height - 5
                    self.h_ruler.create_text(
                        x + 2,
                        6,
                        text=str(i),
                        anchor="nw",
                        fill=text_secondary,
                        font=("Segoe UI", 8),
                    )
                elif i % 5 == 0:
                    tick = height - 9
                else:
                    tick = height - 13
                self.h_ruler.create_line(x, height, x, tick, fill=text_secondary)

            self.h_ruler.create_line(0, height - 1, width, height - 1, fill=border)
            self.h_ruler.create_line(left_pad, 0, left_pad, height, fill=accent)

            try:
                cursor_index = self.text_area.index("insert")
                cursor_col = int(cursor_index.split(".")[1])
                cursor_x = left_pad + cursor_col * char_w
                if 0 <= cursor_x <= width:
                    self.h_ruler.create_polygon(
                        cursor_x - 4,
                        height - 1,
                        cursor_x + 4,
                        height - 1,
                        cursor_x,
                        height - 9,
                        fill=accent,
                        outline=accent,
                    )
            except Exception:
                pass

        v_width = max(0, self.v_ruler.winfo_width())
        v_height = max(0, self.v_ruler.winfo_height())
        if v_width > 0 and v_height > 0:
            self.v_ruler.create_rectangle(0, 0, v_width, v_height, fill=ruler_bg, outline="")
            index = self.text_area.index("@0,0")
            while True:
                line_info = self.text_area.dlineinfo(index)
                if not line_info:
                    break
                y = line_info[1]
                line_h = line_info[3]
                if y > v_height:
                    break
                line_number = index.split(".")[0]
                self.v_ruler.create_text(
                    v_width - 6,
                    y + (line_h / 2),
                    text=line_number,
                    anchor="e",
                    fill=text_secondary,
                    font=("Segoe UI", 9, "bold"),
                )
                index = self.text_area.index(f"{index}+1line")
            self.v_ruler.create_line(v_width - 1, 0, v_width - 1, v_height, fill=border)

    def _safe_int(self, raw, fallback: int) -> int:
        try:
            return int(float(raw))
        except Exception:
            return fallback

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["bg"])
        self.desk_frame.config(bg=colors.get("bg_app", colors["bg"]))
        self.page_shadow.config(
            bg=colors.get("border_dark", colors.get("border", "#999")),
            highlightbackground=colors.get("border_dark", colors.get("border", "#999")),
        )
        self.page_container.config(bg=colors.get("border_light", "#FFFFFF"))
        ruler_bg = colors.get("ruler", "#E7ECF3")
        border = colors.get("border", "#C8D3E3")
        self.ruler_corner.config(bg=ruler_bg, highlightbackground=border)
        self.h_ruler.config(bg=ruler_bg, highlightbackground=border)
        self.v_ruler.config(bg=ruler_bg, highlightbackground=border)
        self.text_holder.config(bg=colors["paper"])
        self.text_area.config(
            bg=colors["paper"],
            fg=colors["text"],
            insertbackground=colors["text"],
        )
        self._redraw_rulers()
