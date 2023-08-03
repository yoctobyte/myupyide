import json
import os

class Settings:
    def __init__(self, filename='settings.json'):
        self.filename = filename
        self.settings = self.load_settings()

    def load_settings(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as file:
                    return json.load(file)
            except:
                return {}
        else:
            return {}

    def get_setting(self, name, default=None):
        self.settings = self.load_settings()
        return self.settings.get(name, default)

    def set_setting(self, name, value):
        self.settings = self.load_settings()
        self.settings[name] = value
        with open(self.filename, 'w') as file:
            json.dump(self.settings, file)