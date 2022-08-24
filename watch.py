from dataclasses import dataclass
from datetime import datetime
from difflib import Differ
import json
from pathlib import Path
import requests
import typer
import base64


@dataclass
class File:
    data: dict 

    @property
    def sha(self):
        return self.data['sha']

    @property
    def text(self):
        return base64.b64decode(self.data['content']).decode('utf-8')
        

    @classmethod
    def from_url(cls, url):
        r = requests.get(url)
        data = r.json()
        return cls(data)


    def diff(self, text):
        differ = Differ()
        result = differ.compare(text.splitlines(), self.text.splitlines())
        return [l for l in result if l.startswith('- ') or l.startswith('+ ')]
        


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
        with open(self.path, 'w') as f:  
            json.dump(self.data, f, indent = 6)

    def get_last(self):
        return File(self.get('last'))

    @transaction
    def get(self, key):
        return self.data.get(key)

    @transaction
    def put(self, key, data):
        self.data[key] = data
    

def main(url: str = typer.Argument("https://api.github.com/repos/cov-lineages/pango-designation/contents/lineage_notes.txt?ref=master")):
    # load the db 
    db = DB(path='db.json')

    new_file = File.from_url(url)
   
    last_file = db.get_last()
    
    # check for sha in db 
    if last_file.sha == new_file.sha:
        # if sha in db no change
        typer.echo("No change!")
        return typer.Exit()

    last_text = last_file.text
    diff = new_file.diff(last_text)
    changes: list = db.get('changes')
    changes.append({'sha':new_file.sha, 'datetime':str(datetime.now()), 'changes': diff})
    db.put('changes', changes)
    db.put('last', new_file.data)

    readme = []
    with open('README.md') as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith("## Changes"):
                print('## Changes')
                break
            readme.append(line)

    # update README
    with open('README.md', 'w') as f:
        f.writelines(readme)
        f.write("## Changes\n")
        for change in changes[::-1]:
            f.write(f"### {change['datetime']}\n")
            f.write(f"*{change['sha']}*\n")
            for c in change['changes']:
                f.write(f"- \{c}\n")

    # send slack 

if __name__ == "__main__":
    typer.run(main)