from dataclasses import dataclass
import json
from pathlib import Path
from .file import File

@dataclass
class DB:
    path: Path

    def transaction(func):
        def wrapper(self, *args, **kwargs):
            self.load()
            res = func(self, *args, **kwargs)
            self.save()
            return res

        return wrapper

    def load(self):
        with open(self.path) as f:
            data = json.load(f)
            self.data = data

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=6)

    def get_last(self):
        return File(self.get("last"))

    @transaction
    def get(self, key):
        return self.data.get(key)

    @transaction
    def put(self, key, data):
        self.data[key] = data
