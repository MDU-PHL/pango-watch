from dataclasses import dataclass
from difflib import Differ
from pathlib import Path
import requests
import base64


@dataclass
class File:
    data: dict

    @property
    def sha(self):
        return self.data["sha"]

    @property
    def text(self):
        return base64.b64decode(self.data["content"]).decode("utf-8")

    @classmethod
    def from_url(cls, url):
        r = requests.get(url)
        data = r.json()
        return cls(data)

    def diff(self, text):
        differ = Differ()
        result = differ.compare(text.splitlines(), self.text.splitlines())
        return [l for l in result if l.startswith("- ") or l.startswith("+ ")]
