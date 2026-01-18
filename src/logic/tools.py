import tkinter as tk
from tkinter import Toplevel, messagebox, filedialog, Button
import datetime

# Safe import for Pillow
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class ToolManager:
    def __init__(self, editor, root):
        self.editor = editor
        self.root = root
        self.images = []  # Prevent garbage collection

    def select_all(self):
        self.editor.tag_add("sel", "1.0", "end")
        self.editor.mark_set("insert", "1.0")
        self.editor.see("insert")
        return "break"

    def insert_horizontal_line(self):
        self.editor.insert(tk.INSERT, "\n" + "_" * 40 + "\n")

    def insert_date_time(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.editor.insert(tk.INSERT, now)

    def insert_image(self):
        if not HAS_PIL:
            messagebox.showerror("Error", "Pillow library not installed.\nRun: pip install Pillow")
            return

        # IMPORTANT (macOS/Tk): do NOT use semicolon-separated patterns like "*.png;*.jpg"
        # Use a tuple (or space-separated string) so Tk can safely map to allowed file types.
        path = filedialog.askopenfilename(
            parent=self.root,
            filetypes=[
                ("Images", ("*.png", "*.jpg", "*.jpeg", "*.gif")),
                ("All Files", "*"),
            ],
        )
        if not path:
            return

        try:
            img = Image.open(path)
            # Resize giant images to prevent UI freeze
            img.thumbnail((500, 500))
            photo = ImageTk.PhotoImage(img)

            self.images.append(photo)  # Keep reference
            self.editor.image_create(tk.INSERT, image=photo, padx=10, pady=10)
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not load image:\n{e}")

    def open_symbol_picker(self):
        win = Toplevel(self.root)
        win.title("Symbols")
        win.geometry("350x250")
        win.transient(self.root)

        symbols = [
            "©", "®", "™", "€", "£", "¥", "¢", "§",
            "¶", "∞", "≠", "≈", "±", "≤", "≥", "÷",
            "×", "°", "α", "β", "π", "Ω", "Σ", "★",
            "•", "→", "←", "↑", "↓", "✓"
        ]

        row = 0
        col = 0
        for s in symbols:
            btn = Button(
                win,
                text=s,
                width=4,
                font=("Segoe UI", 12),
                command=lambda char=s: self.editor.insert(tk.INSERT, char),
            )
            btn.grid(row=row, column=col, padx=3, pady=3)
            col += 1
            if col > 5:
                col = 0
                row += 1

    def open_find_replace(self):
        win = Toplevel(self.root)
        win.title("Find & Replace")
        win.geometry("300x160")
        win.transient(self.root)

        tk.Label(win, text="Find:").pack(pady=(5, 0))
        e_find = tk.Entry(win, width=25)
        e_find.pack()

        tk.Label(win, text="Replace with:").pack(pady=(5, 0))
        e_rep = tk.Entry(win, width=25)
        e_rep.pack()

        def do_replace():
            find_str = e_find.get()
            rep_str = e_rep.get()
            if not find_str:
                return

            # NON-DESTRUCTIVE SEARCH ALGORITHM
            start_pos = "1.0"
            count = 0

            while True:
                # Search specifically for the string
                pos = self.editor.search(find_str, start_pos, stopindex=tk.END)
                if not pos:
                    break

                # Calculate end position of match
                end_pos = f"{pos}+{len(find_str)}c"

                # Replace ONLY the text found (preserves formatting elsewhere)
                self.editor.delete(pos, end_pos)
                self.editor.insert(pos, rep_str)

                # Move pointer forward
                start_pos = f"{pos}+{len(rep_str)}c"
                count += 1

            if count > 0:
                messagebox.showinfo("Result", f"Replaced {count} occurrences.")
                win.destroy()
            else:
                messagebox.showinfo("Result", "No matches found.")

        tk.Button(win, text="Replace All", command=do_replace).pack(pady=15)

    def show_stats(self):
        try:
            text = self.editor.get("1.0", tk.END)
            words = len(text.split())
            chars = len(text) - 1
            lines = int(self.editor.index("end-1c").split(".")[0])
            messagebox.showinfo("Stats", f"Words: {words}\nCharacters: {chars}\nLines: {lines}")
        except:
            pass