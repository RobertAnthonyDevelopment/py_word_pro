import tkinter as tk
# We changed the class name to 'App' in the new script, so we must import 'App'
from src.app import App 

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()