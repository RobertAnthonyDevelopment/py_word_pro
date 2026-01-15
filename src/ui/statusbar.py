import tkinter as tk

class StatusBar:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=app.colors["primary"], height=28)
        self.lbl = tk.Label(self.frame, text="Ready", bg=app.colors["primary"], fg="white", font=("Segoe UI", 9))
        self.lbl.pack(side=tk.LEFT, padx=10)
        
        self.slider = tk.Scale(self.frame, from_=50, to=200, orient=tk.HORIZONTAL, bg=app.colors["primary"], fg="white", showvalue=0, command=self.zoom)
        self.slider.set(100)
        self.slider.pack(side=tk.RIGHT, padx=5)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def zoom(self, v):
        s = int(v)/100
        self.app.workspace.editor.config(font=("Calibri", int(12*s)), padx=int(40*s))

    def update_theme(self, c):
        self.frame.config(bg=c["primary"])
        self.lbl.config(bg=c["primary"])
        self.slider.config(bg=c["primary"])
