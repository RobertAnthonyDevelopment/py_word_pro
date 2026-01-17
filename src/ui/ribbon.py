import tkinter as tk
from tkinter import ttk, font

class Ribbon(tk.Frame):
    def __init__(self, parent, callbacks, colors):
        super().__init__(parent, bg=colors["ribbon"], bd=1, relief=tk.RAISED)
        self.pack(side=tk.TOP, fill=tk.X)
        self.callbacks = callbacks
        self.colors = colors
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._init_home()
        self._init_insert()
        self._init_view()
        self._init_review()

    def update_theme(self, colors):
        self.colors = colors
        self.config(bg=colors["ribbon"])
        # Note: Updating internal frames requires iterating through children or 
        # destroying/recreating ribbon. For simplicity in this structure, 
        # we update the main background. Ideally, restart app for full theme apply.

    def _create_group(self, parent, text):
        frame = tk.LabelFrame(parent, text=text, padx=5, pady=5, 
                              bg=self.colors["ribbon"], font=("Segoe UI", 9))
        frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        return frame

    def _init_home(self):
        tab = tk.Frame(self.notebook, bg=self.colors["ribbon"])
        self.notebook.add(tab, text="  Home  ")

        g_file = self._create_group(tab, "File")
        tk.Button(g_file, text="💾 Save", command=self.callbacks['save']).pack(side=tk.LEFT, padx=2, fill=tk.Y)
        tk.Button(g_file, text="📂 Open", command=self.callbacks['open']).pack(side=tk.LEFT, padx=2, fill=tk.Y)
        tk.Button(g_file, text="📄 PDF", command=self.callbacks['pdf']).pack(side=tk.LEFT, padx=2, fill=tk.Y)

        g_edit = self._create_group(tab, "Edit")
        tk.Button(g_edit, text="↺", font=("Segoe UI", 12), command=self.callbacks['undo']).pack(side=tk.LEFT, padx=2, fill=tk.Y)
        tk.Button(g_edit, text="↻", font=("Segoe UI", 12), command=self.callbacks['redo']).pack(side=tk.LEFT, padx=2, fill=tk.Y)
        tk.Button(g_edit, text="Select All", command=self.callbacks['select_all']).pack(side=tk.LEFT, padx=2, fill=tk.Y)

        g_font = self._create_group(tab, "Font")
        f_top = tk.Frame(g_font, bg=self.colors["ribbon"])
        f_top.pack(side=tk.TOP, fill=tk.X)
        self.cb_font = ttk.Combobox(f_top, values=font.families(), width=13, state="readonly")
        self.cb_font.set("Calibri")
        self.cb_font.pack(side=tk.LEFT, padx=2)
        self.cb_font.bind("<<ComboboxSelected>>", lambda e: self.callbacks['font_fam'](self.cb_font.get()))
        
        self.cb_size = ttk.Combobox(f_top, values=[8,10,11,12,14,16,18,24,36], width=3, state="readonly")
        self.cb_size.set(11)
        self.cb_size.pack(side=tk.LEFT, padx=2)
        self.cb_size.bind("<<ComboboxSelected>>", lambda e: self.callbacks['font_size'](self.cb_size.get()))

        f_bot = tk.Frame(g_font, bg=self.colors["ribbon"])
        f_bot.pack(side=tk.BOTTOM, fill=tk.X, pady=2)
        tk.Button(f_bot, text="B", font=("Times", 10, "bold"), width=2, command=self.callbacks['bold']).pack(side=tk.LEFT)
        tk.Button(f_bot, text="I", font=("Times", 10, "italic"), width=2, command=self.callbacks['italic']).pack(side=tk.LEFT)
        tk.Button(f_bot, text="U", font=("Times", 10, "underline"), width=2, command=self.callbacks['underline']).pack(side=tk.LEFT)
        tk.Button(f_bot, text="S", font=("Times", 10, "overstrike"), width=2, command=self.callbacks['strike']).pack(side=tk.LEFT)
        tk.Button(f_bot, text="🎨", width=2, command=self.callbacks['color']).pack(side=tk.LEFT)
        tk.Button(f_bot, text="🖍", width=2, command=self.callbacks['highlight']).pack(side=tk.LEFT)
        tk.Button(f_bot, text="✖", width=2, command=self.callbacks['clear_fmt'], fg="red").pack(side=tk.LEFT)

        g_para = self._create_group(tab, "Paragraph")
        tk.Button(g_para, text="≡L", command=self.callbacks['align_l']).pack(side=tk.LEFT, fill=tk.Y)
        tk.Button(g_para, text="≡C", command=self.callbacks['align_c']).pack(side=tk.LEFT, fill=tk.Y)
        tk.Button(g_para, text="≡R", command=self.callbacks['align_r']).pack(side=tk.LEFT, fill=tk.Y)
        
        f_space = tk.Frame(g_para, bg=self.colors["ribbon"])
        f_space.pack(side=tk.LEFT, padx=5)
        tk.Label(f_space, text="Spacing", font=("Arial", 8), bg=self.colors["ribbon"]).pack(side=tk.TOP)
        self.cb_space = ttk.Combobox(f_space, values=["1.0", "1.5", "2.0"], width=3, state="readonly")
        self.cb_space.set("1.0")
        self.cb_space.pack(side=tk.BOTTOM)
        self.cb_space.bind("<<ComboboxSelected>>", lambda e: self.callbacks['spacing'](float(self.cb_space.get())))

    def _init_insert(self):
        tab = tk.Frame(self.notebook, bg=self.colors["ribbon"])
        self.notebook.add(tab, text="  Insert  ")
        g_media = self._create_group(tab, "Media")
        tk.Button(g_media, text="🖼 Image", command=self.callbacks['img']).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        tk.Button(g_media, text="___ Line", command=self.callbacks['hr_line']).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        g_txt = self._create_group(tab, "Text")
        tk.Button(g_txt, text="📅 Date", command=self.callbacks['date']).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        tk.Button(g_txt, text="Ω Symbol", command=self.callbacks['symbol']).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        g_tools = self._create_group(tab, "Tools")
        tk.Button(g_tools, text="🔍 Find", command=self.callbacks['find']).pack(side=tk.LEFT, padx=5, fill=tk.Y)

    def _init_view(self):
        tab = tk.Frame(self.notebook, bg=self.colors["ribbon"])
        self.notebook.add(tab, text="  View  ")
        
        g_mode = self._create_group(tab, "Window")
        tk.Button(g_mode, text="🌓 Theme", command=self.callbacks.get('theme')).pack(side=tk.LEFT, padx=2, fill=tk.Y)
        tk.Button(g_mode, text="🔲 Focus", command=self.callbacks.get('focus')).pack(side=tk.LEFT, padx=2, fill=tk.Y)
        tk.Button(g_mode, text="Side Bar", command=self.callbacks.get('sidebar')).pack(side=tk.LEFT, padx=2, fill=tk.Y)

        g_zoom = self._create_group(tab, "Zoom")
        tk.Button(g_zoom, text="➕ In", command=self.callbacks['zoom_in']).pack(side=tk.LEFT, padx=2, fill=tk.Y)
        tk.Button(g_zoom, text="➖ Out", command=self.callbacks['zoom_out']).pack(side=tk.LEFT, padx=2, fill=tk.Y)
        g_page = self._create_group(tab, "Page Setup")
        tk.Button(g_page, text="Paper Color", command=self.callbacks['pg_color']).pack(side=tk.LEFT, padx=2, fill=tk.Y)

    def _init_review(self):
        tab = tk.Frame(self.notebook, bg=self.colors["ribbon"])
        self.notebook.add(tab, text="  Review  ")
        g_proof = self._create_group(tab, "Proofing")
        tk.Button(g_proof, text="ABC Check", command=self.callbacks['spell']).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        tk.Button(g_proof, text="123 Count", command=self.callbacks['stats']).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        g_speech = self._create_group(tab, "Speech")
        tk.Button(g_speech, text="▶ Read Aloud", command=self.callbacks['tts']).pack(side=tk.LEFT, padx=5, fill=tk.Y)