import json, os

APP_NAME = "PyWord Pro"
VERSION = "5.0 Modular"
CONFIG_FILE = "pyword_config.json"

THEME = {
    "light": {"ribbon": "#f3f3f3", "bg": "#e6e6e6", "paper": "#ffffff", "text": "#2d2d2d", "ruler": "#fcfcfc", "sidebar": "#f9f9f9", "primary": "#2b579a", "console": "#f0f0f0"},
    "dark": {"ribbon": "#2d2d2d", "bg": "#1e1e1e", "paper": "#3c3c3c", "text": "#e0e0e0", "ruler": "#333333", "sidebar": "#252526", "primary": "#007acc", "console": "#252526"}
}

class ConfigManager:
    def __init__(self):
        self.defaults = {"theme": "light", "recents": [], "geometry": "1600x1000", "zoom": 100}
        self.data = self.load()
    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f: return json.load(f)
            except: pass
        return self.defaults.copy()
    def save(self):
        try:
            with open(CONFIG_FILE, "w") as f: json.dump(self.data, f)
        except: pass
    def add_recent(self, path):
        if path in self.data["recents"]: self.data["recents"].remove(path)
        self.data["recents"].insert(0, path)
        self.data["recents"] = self.data["recents"][:8]
        self.save()
