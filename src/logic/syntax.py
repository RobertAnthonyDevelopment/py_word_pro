import tkinter as tk
import re

class SyntaxHighlighter:
    def __init__(self, editor, colors):
        self.editor = editor
        self.timer = None
        self.setup_tags()
        self.rules = [
            (r'\b(def|class|if|else|return|import|from|print)\b', 'keyword'),
            (r'#.*', 'comment'),
            (r'(".*?"|\'.*?\')', 'string'),
        ]

    def setup_tags(self):
        self.editor.tag_configure('keyword', foreground='#d73a49', font=('Consolas', 11, 'bold'))
        self.editor.tag_configure('comment', foreground='#6a737d', font=('Consolas', 11, 'italic'))
        self.editor.tag_configure('string', foreground='#032f62')
        self.editor.tag_configure('codeblock', background='#f6f8fa', font=('Consolas', 11))

    def update_theme(self, is_dark):
        bg = "#2d2d2d" if is_dark else "#f6f8fa"
        self.editor.tag_configure('codeblock', background=bg)

    def trigger(self):
        if self.timer: self.editor.after_cancel(self.timer)
        self.timer = self.editor.after(500, self.highlight)

    def highlight(self):
        for tag in ['codeblock', 'keyword', 'comment', 'string']:
            self.editor.tag_remove(tag, "1.0", tk.END)
        content = self.editor.get("1.0", tk.END)
        for match in re.finditer(r'```(.*?)```', content, re.DOTALL):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.editor.tag_add('codeblock', start, end)
            block_content = match.group(1)
            start_offset = match.start() + 3
            for pattern, tag in self.rules:
                for m in re.finditer(pattern, block_content):
                    s = f"1.0 + {start_offset + m.start()} chars"
                    e = f"1.0 + {start_offset + m.end()} chars"
                    self.editor.tag_add(tag, s, e)
