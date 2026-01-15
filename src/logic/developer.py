import sys, subprocess, threading, queue, tkinter as tk

class DeveloperEngine:
    def __init__(self, app):
        self.app = app
        self.console_queue = queue.Queue()
        self.console_widget = None
        self._console_loop()

    def run_threaded(self):
        code = self.app.workspace.editor.get("1.0", tk.END)
        self.write_console(">>> Running...\n")
        threading.Thread(target=self._exec, args=(code,), daemon=True).start()

    def _exec(self, code):
        try:
            process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out, err = process.communicate()
            self.console_queue.put(out + "\n")
            if err: self.console_queue.put(f"Error:\n{err}\n")
        except Exception as e:
            self.console_queue.put(str(e))

    def write_console(self, text):
        if self.console_widget:
            self.console_widget.config(state='normal')
            self.console_widget.insert(tk.END, text)
            self.console_widget.see(tk.END)
            self.console_widget.config(state='disabled')

    def _console_loop(self):
        try:
            while not self.console_queue.empty():
                self.write_console(self.console_queue.get_nowait())
        except: pass
        self.app.root.after(100, self._console_loop)
