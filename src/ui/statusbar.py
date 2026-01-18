import tkinter as tk

class StatusBar:
    def __init__(self, parent, app, colors):
        self.app = app
        
        self.frame = tk.Frame(parent, bg=colors["primary"], height=28)
        self.frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl = tk.Label(self.frame, text="Ready", bg=colors["primary"], fg="white")
        self.lbl.pack(side=tk.LEFT, padx=10)
        
        # ZOOM SLIDER
        self.slider = tk.Scale(self.frame, from_=50, to=200, 
                               orient=tk.HORIZONTAL, 
                               bg=colors["primary"], fg="white", 
                               highlightthickness=0, showvalue=0,
                               command=self._on_slide)
        self.slider.set(100)
        self.slider.pack(side=tk.RIGHT, padx=10)
        
        self.zoom_lbl = tk.Label(self.frame, text="100%", bg=colors["primary"], fg="white")
        self.zoom_lbl.pack(side=tk.RIGHT)

    def _on_slide(self, val):
        # Pass ABSOLUTE value to app
        self.app.update_zoom(absolute=int(val))

    def update_zoom_label(self, val):
        self.zoom_lbl.config(text=f"{val}%")
        self.slider.set(val)

    def update_theme(self, c):
        self.frame.config(bg=c["primary"])
        self.lbl.config(bg=c["primary"])
        self.slider.config(bg=c["primary"])
        self.zoom_lbl.config(bg=c["primary"])