import tkinter as tk

class StatusBar:
    def __init__(self, parent, app, colors):
        self.app = app
        
        self.frame = tk.Frame(parent, bg=colors["primary"], height=28)
        self.frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Left Info
        self.lbl_status = tk.Label(self.frame, text="Ready", 
                                   bg=colors["primary"], fg="white", 
                                   font=("Segoe UI", 9))
        self.lbl_status.pack(side=tk.LEFT, padx=10)
        
        # Zoom Slider
        self.slider = tk.Scale(self.frame, from_=50, to=200, 
                               orient=tk.HORIZONTAL, 
                               bg=colors["primary"], fg="white", 
                               showvalue=0, bd=0, highlightthickness=0, length=150,
                               command=self._on_slide)
        self.slider.set(100)
        self.slider.pack(side=tk.RIGHT, padx=10)
        
        self.zoom_lbl = tk.Label(self.frame, text="100%", bg=colors["primary"], fg="white")
        self.zoom_lbl.pack(side=tk.RIGHT)

    def _on_slide(self, val):
        # We debounce or pass direct? Passing direct for simplicity
        # The app tracks zoom state, so we update the app
        # To avoid circular lag, we only call if needed
        pass # The command in app.py handles the actual logic via binding or we link here
        # Actually, Tk scale command passes value. We need to link it to app.update_zoom
        self.app.update_zoom(int(val) - self.app.settings.get("zoom", 100))

    def update_zoom_label(self, val):
        self.zoom_lbl.config(text=f"{val}%")
        self.slider.set(val)

    def update_theme(self, c):
        self.frame.config(bg=c["primary"])
        self.lbl_status.config(bg=c["primary"])
        self.zoom_lbl.config(bg=c["primary"])
        self.slider.config(bg=c["primary"])