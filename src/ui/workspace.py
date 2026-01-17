import tkinter as tk

class Workspace(tk.Frame):
    def __init__(self, parent, colors, initial_zoom=100):
        super().__init__(parent, bg=colors["bg"])
        self.pack(fill=tk.BOTH, expand=True)

        # 1. Desk Frame (The gray background area)
        self.desk_frame = tk.Frame(self, bg=colors["bg"])
        self.desk_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Grid layout for scrollbars
        self.desk_frame.grid_rowconfigure(0, weight=1)
        self.desk_frame.grid_columnconfigure(0, weight=1)

        # 2. Scrollbars
        self.v_scroll = tk.Scrollbar(self.desk_frame, orient=tk.VERTICAL)
        self.h_scroll = tk.Scrollbar(self.desk_frame, orient=tk.HORIZONTAL)

        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")

        # 3. Page Container (Border effect)
        self.page_container = tk.Frame(self.desk_frame, bg="#999", bd=1)
        self.page_container.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)

        # 4. Text Editor (The Paper)
        self.text_area = tk.Text(self.page_container, 
                                 font=("Calibri", 11),
                                 bg=colors["paper"], 
                                 fg=colors["text"],
                                 insertbackground=colors["text"],
                                 wrap=tk.WORD,
                                 padx=50, pady=50,
                                 spacing1=2, spacing2=2,
                                 undo=True,
                                 yscrollcommand=self.v_scroll.set,
                                 xscrollcommand=self.h_scroll.set)
        
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # Link scrollbars
        self.v_scroll.config(command=self.text_area.yview)
        self.h_scroll.config(command=self.text_area.xview)

        # Apply initial formatting tags
        self.text_area.tag_configure("highlight_find", background="yellow", foreground="black")
        self.text_area.tag_configure("error_spell", underline=True, underlinefg="red")

    def get_editor(self):
        return self.text_area

    def update_theme(self, colors):
        self.config(bg=colors["bg"])
        self.desk_frame.config(bg=colors["bg"])
        self.text_area.config(
            bg=colors["paper"], 
            fg=colors["text"], 
            insertbackground=colors["text"]
        )