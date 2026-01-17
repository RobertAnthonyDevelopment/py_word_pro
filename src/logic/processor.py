import threading
import tkinter as tk
from tkinter import messagebox

try:
    import pyttsx3
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

try:
    from spellchecker import SpellChecker
    HAS_SPELL = True
except ImportError:
    HAS_SPELL = False

class TextProcessor:
    def __init__(self, editor_widget):
        self.editor = editor_widget
        self.spell = SpellChecker() if HAS_SPELL else None
        self.tts_engine = pyttsx3.init() if HAS_TTS else None

    def run_spell_check(self):
        if not HAS_SPELL:
            messagebox.showerror("Error", "pyspellchecker library is missing.")
            return
        
        # Clear old error tags
        self.editor.tag_remove("error_spell", "1.0", tk.END)
        self.editor.tag_configure("error_spell", underline=True, underlinefg="red")

        text = self.editor.get("1.0", tk.END)
        # Filter out non-alphanumeric to avoid checking punctuation
        words = text.split()
        clean_words = [w.strip(".,!?\"'") for w in words]
        
        misspelled = self.spell.unknown(clean_words)

        if not misspelled:
            messagebox.showinfo("Spell Check", "No spelling errors found.")
            return

        for word in misspelled:
            if not word: continue
            idx = "1.0"
            while True:
                idx = self.editor.search(word, idx, stopindex=tk.END)
                if not idx: break
                lastidx = f"{idx}+{len(word)}c"
                self.editor.tag_add("error_spell", idx, lastidx)
                idx = lastidx
        
        messagebox.showinfo("Spell Check", f"Found {len(misspelled)} potential errors.")

    def read_aloud(self):
        if not HAS_TTS: 
            messagebox.showerror("Error", "pyttsx3 library is missing.")
            return
        
        # Get selected text or all text
        try:
            text = self.editor.get("sel.first", "sel.last")
        except tk.TclError:
            text = self.editor.get("1.0", tk.END)
            
        if not text.strip(): 
            return

        # Run in a separate thread so the UI doesn't freeze
        threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    def _speak(self, text):
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()