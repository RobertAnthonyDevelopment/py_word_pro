import tkinter as tk
from tkinter import filedialog, messagebox, Toplevel
import os, sys, threading, time
from docx import Document
import fitz 
from PIL import Image, ImageTk

class FileManager:
    def __init__(self, app):
        self.app = app
        self.current_file = None
        self.images_ref = []

    def start_autosave(self):
        def loop():
            while True:
                time.sleep(60)
                try:
                    with open("autosave.tmp", "w", encoding="utf-8") as f:
                        f.write(self.app.workspace.editor.get("1.0", tk.END))
                except: pass
        threading.Thread(target=loop, daemon=True).start()

    def open_backstage(self):
        top = Toplevel(self.app.root)
        top.geometry("400x500")
        tk.Button(top, text="Open", command=lambda:[self.open_file(), top.destroy()]).pack(pady=20)
        tk.Button(top, text="Save", command=lambda:[self.save_file(), top.destroy()]).pack(pady=20)

    def open_file(self):
        p = filedialog.askopenfilename()
        if p:
            self.app.workspace.editor.delete("1.0", tk.END)
            if p.endswith(".docx"):
                d = Document(p)
                for para in d.paragraphs: self.app.workspace.editor.insert(tk.END, para.text + "\n")
            elif p.endswith(".pdf"):
                d = fitz.open(p)
                for page in d: self.app.workspace.editor.insert(tk.END, page.get_text())
            else:
                with open(p, "r", encoding="utf-8") as f: self.app.workspace.editor.insert(tk.END, f.read())
            self.current_file = p
            self.scan_nav()

    def save_file(self):
        if not self.current_file:
            self.current_file = filedialog.asksaveasfilename(defaultextension=".txt")
        if self.current_file:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(self.app.workspace.editor.get("1.0", tk.END))

    def ins_img(self):
        p = filedialog.askopenfilename()
        if p:
            img = Image.open(p)
            img.thumbnail((400, 400))
            ph = ImageTk.PhotoImage(img)
            self.images_ref.append(ph)
            self.app.workspace.editor.image_create(tk.INSERT, image=ph)

    def scan_nav(self):
        tree = self.app.sidebar.tree
        tree.delete(*tree.get_children())
        lines = self.app.workspace.editor.get("1.0", tk.END).split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("# ") or (line.isupper() and len(line) < 30):
                tree.insert("", "end", iid=f"{i+1}.0", text=line)
