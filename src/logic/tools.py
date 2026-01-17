import tkinter as tk
from tkinter import Toplevel, messagebox, filedialog, Button
import datetime

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class ToolManager:
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.images = []

    def select_all(self):
        self.editor.tag_add("sel", "1.0", "end")
        self.editor.mark_set("insert", "1.0")
        self.editor.see("insert")
        return "break" # Prevent default behavior

    def insert_horizontal_line(self):
        # Inserts a visual separator line
        self.editor.insert(tk.INSERT, "\n" + "_"*40 + "\n")

    def open_symbol_picker(self):
        win = Toplevel(self.root)
        win.title("Symbols")
        win.geometry("300x300")
        win.transient(self.root)
        
        symbols = [
            "©", "®", "™", "€", "£", "¥", 
            "¢", "§", "¶", "∞", "≠", "≈", 
            "±", "≤", "≥", "÷", "×", "°", 
            "α", "β", "π", "Ω", "Σ", "★"
        ]
        
        # Grid layout for symbols
        row = 0
        col = 0
        for s in symbols:
            btn = Button(win, text=s, width=4, font=("Segoe UI", 12),
                         command=lambda char=s: [self.editor.insert(tk.INSERT, char), win.destroy()])
            btn.grid(row=row, column=col, padx=2, pady=2)
            col += 1
            if col > 5:
                col = 0
                row += 1

    # --- Preserved Features ---
    def insert_date_time(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.editor.insert(tk.INSERT, now)

    def insert_image(self):
        if not HAS_PIL:
            messagebox.showerror("Error", "Pillow (PIL) library not installed.")
            return
        
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if path:
            try:
                img = Image.open(path)
                img.thumbnail((400, 400))
                photo = ImageTk.PhotoImage(img)
                self.images.append(photo)
                self.editor.image_create(tk.INSERT, image=photo, padx=10, pady=10)
            except Exception as e:
                messagebox.showerror("Image Error", str(e))

    def show_stats(self):
        text = self.editor.get("1.0", tk.END)
        words = len(text.split())
        chars = len(text) - 1
        lines = int(self.editor.index('end-1c').split('.')[0])
        messagebox.showinfo("Document Statistics", f"Words: {words}\nCharacters: {chars}\nLines: {lines}")

    def open_find_replace(self):
        win = Toplevel(self.root)
        win.title("Find & Replace")
        win.geometry("350x180")
        win.transient(self.root)
        
        tk.Label(win, text="Find what:").pack(pady=(10,0))
        e_find = tk.Entry(win, width=30)
        e_find.pack(pady=5)
        
        tk.Label(win, text="Replace with:").pack(pady=(5,0))
        e_rep = tk.Entry(win, width=30)
        e_rep.pack(pady=5)

        def do_replace():
            s = e_find.get()
            r = e_rep.get()
            if s:
                data = self.editor.get("1.0", tk.END)
                if s in data:
                    newdata = data.replace(s, r)
                    self.editor.delete("1.0", tk.END)
                    self.editor.insert("1.0", newdata)
                    messagebox.showinfo("Success", f"Replaced '{s}' with '{r}'.")
                    win.destroy()
                else:
                    messagebox.showinfo("Result", f"'{s}' not found.")

        tk.Button(win, text="Replace All", command=do_replace).pack(pady=15)