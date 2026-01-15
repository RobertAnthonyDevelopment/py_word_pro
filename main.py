import tkinter as tk
from src.app import PyWordEnterprise

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    
    app = PyWordEnterprise(root)
    root.mainloop()
