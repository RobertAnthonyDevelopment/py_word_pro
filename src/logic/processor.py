import threading
import re
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
        self._custom_dictionary_words: set[str] = set()

    def set_custom_dictionary_words(self, words):
        values = set()
        if isinstance(words, (list, tuple, set)):
            for item in words:
                token = str(item or "").strip().lower()
                if token:
                    values.add(token)
        elif isinstance(words, dict):
            for key in words.keys():
                token = str(key or "").strip().lower()
                if token:
                    values.add(token)
        self._custom_dictionary_words = values
        return True

    def run_spell_check(self):
        if not HAS_SPELL:
            messagebox.showerror("Error", "pyspellchecker library is missing.")
            return False

        self.editor.tag_remove("error_spell", "1.0", tk.END)
        self.editor.tag_configure("error_spell", underline=True, underlinefg="red")

        text = self.editor.get("1.0", tk.END)
        words = text.split()
        clean_words = [word.strip(".,!?\"'") for word in words]
        misspelled = self.spell.unknown(clean_words)
        if self._custom_dictionary_words:
            misspelled = {
                word
                for word in misspelled
                if str(word or "").strip().lower() not in self._custom_dictionary_words
            }

        if not misspelled:
            messagebox.showinfo("Spell Check", "No spelling errors found.")
            return True

        for word in misspelled:
            if not word:
                continue
            idx = "1.0"
            pattern = rf"\\m{re.escape(word)}\\M"
            while True:
                idx = self.editor.search(pattern, idx, stopindex=tk.END, regexp=True, nocase=True)
                if not idx:
                    break
                lastidx = f"{idx}+{len(word)}c"
                self.editor.tag_add("error_spell", idx, lastidx)
                idx = lastidx

        messagebox.showinfo("Spell Check", f"Found {len(misspelled)} potential errors.")
        return True

    def read_aloud(self):
        if not HAS_TTS:
            messagebox.showerror("Error", "pyttsx3 library is missing.")
            return False

        try:
            text = self.editor.get("sel.first", "sel.last")
        except tk.TclError:
            text = self.editor.get("1.0", tk.END)

        if not text.strip():
            return False

        threading.Thread(target=self._speak, args=(text,), daemon=True).start()
        return True

    def _speak(self, text):
        self.tts_engine.say(text)
        self.tts_engine.runAndWait()
