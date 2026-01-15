import tkinter as tk
from tkinter import scrolledtext

class ConsolePane:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=app.colors["console"], height=150)
        self.lbl = tk.Label(self.frame, text="Output Console", font=("Segoe UI", 8, "bold"), bg="#ddd", anchor="w")
        self.lbl.pack(fill=tk.X)
        self.text_area = scrolledtext.ScrolledText(self.frame, height=8, font=("Consolas", 9), state="disabled")
        self.text_area.pack(fill=tk.BOTH, expand=True)

    def update_theme(self, c):
        self.frame.config(bg=c["console"])
        self.text_area.config(bg=c["console"], fg=c["text"])
