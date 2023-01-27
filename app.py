from datetime import datetime
from typing import List, Optional
import typer
from watch import File, DB, toot
import requests

def send_slack_msg(hook_url, diff):
    data = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "There has been an update to the <https://github.com/cov-lineages/pango-designation/blob/master/lineage_notes.txt|Pango-lineage designations>:"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "\n".join(diff)
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "https://mdu-phl.github.io/pango-watch/"
                    }
                }
            ]
        }
    r = requests.post(hook_url, json=data)

app = typer.Typer()


@app.command()
def check(
    url: str = typer.Argument(
        "https://api.github.com/repos/cov-lineages/pango-designation/contents/lineage_notes.txt?ref=master"
    ),
    slack: Optional[List[str]] = typer.Option(None, help="Hook to post the results to."),
    mastodon_access_token: Optional[str] = typer.Option(None, help="Access_token for mastodon api."),
    mastodon_api_base_url: Optional[str] = typer.Option(None, help="base url for mastodon api."),
):
    # load the db
    db = DB(path="db.json")

    new_file = File.from_url(url)

    last_file = db.get_last()

    # check for sha in db
    if last_file.sha == new_file.sha:
        # if sha in db no change
        typer.echo("No change!")
        return typer.Exit()

    last_text = last_file.text
    diff = new_file.diff(last_text)
    changes: list = db.get("changes")
    changes.append(
        {"sha": new_file.sha, "datetime": str(datetime.now()), "changes": diff}
    )
    db.put("changes", changes)
    db.put("last", new_file.data)

    readme = []
    with open("README.md") as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith("## Changes"):
                break
            readme.append(line)

    # update README
    with open("README.md", "w") as f:
        f.writelines(readme)
        f.write("## Changes\n")
        f.write("> Note: Links to lineages on https://cov-lineages.org will not work until the site is updated to include the changes.\n\n")
        for change in changes[::-1]:
            f.write(f"### {change['datetime'].split()[0]}\n")
            # f.write(f"*{change['sha']}*\n")
            for c in change["changes"]:
                op, lineage, *note = c.split() # +/- lineage note
                esc = ""
                if lineage.startswith('*'):
                    esc = "\\"
                f.write(f"- \{op} [{esc}{lineage}](https://cov-lineages.org/lineage.html?lineage={lineage}) {' '.join(note)}\n")
            f.write("\n" )

    # send slack
    if slack:
        typer.echo('Sending update to slack!')
        for hook_url in slack:
            send_slack_msg(hook_url, diff)
    
    if mastodon_access_token and mastodon_api_base_url:
        typer.echo(f'Tooting to {mastodon_api_base_url}!')
        text = "There has been an update to the pango-lineage designations!\n\n-> https://mdu-phl.github.io/pango-watch/ <- \n\n"
        text += "\n".join(diff)
        toot(access_token=mastodon_access_token, api_base_url=mastodon_api_base_url, text=text)



def insertNodeIntoTree(node, parentName, newNode):
  if node['name'] == parentName:
    node['children'].append(newNode)
  elif node['children']:
    for child in node['children']:
      insertNodeIntoTree(child, parentName, newNode)

def load_alias_key():
    import urllib.request, json

    with urllib.request.urlopen(
        "https://raw.githubusercontent.com/cov-lineages/pango-designation/master/pango_designation/alias_key.json"
    ) as data:
        file = json.load(data)
    return file 


def clean_parents(lineages, uncompressor):
    parents = []
    for lineage in lineages:
        lineage = lineage.replace('*', '')
        if '/' in lineage:
            # "BA.4/5"
            first, second = lineage.split('/')
            parents.append(first)
            parents.append(f"{first[:-1]}{second}")
        else:
            parents.append(lineage)
    return [uncompressor(p) for p in parents]
    
def treeTograph(node, nodes=[], links=[]):
    if node['children']:
        for child in node['children']:
            links.append({'source':node['name'], 'target': child['name']})
            if 'otherParents' in child:
                for source in child['otherParents']:
                    links.append({'source':source, 'target': child['name']})
            treeTograph(child, nodes=nodes, links=links)
    nodes.append(dict(id=node['name'], label=node['compressed_name'], group=node['group']))
    return nodes, links

@app.command()
def tree():
    from pango_aliasor.aliasor import Aliasor
    import json 
    aliasor = Aliasor()
    db = DB(path="db.json")
    last_file = db.get_last()
    last_text = last_file.text
    lineages = []
    groups = []
    alias_key = load_alias_key()
    for i, line in enumerate(last_text.split('\n')):
        if not line or i == 0:
            # skip header and EOF
            continue
        lineage = line.split('\t')[0].split()[0]
        if lineage.startswith('*'): # remove withdrawn
            continue
        if lineage.startswith('X'): # process recombinants 
            parents = lineage.split('.')
            if len(parents) == 1:
                parents = clean_parents(alias_key[parents[0]], uncompressor=aliasor.uncompress)
            else:
                parents = [lineage]
            lineages.append({"compressed_name":lineage,"name":aliasor.uncompress(lineage), "recombinant": True, "parents": parents})
        else:
            lineages.append({"compressed_name":lineage,"name":aliasor.uncompress(lineage), "recombinant": False})

    root = {'name':'root', 'children':[], 'compressed_name': 'SARS-CoV-2', 'group': None}
    # build tree
    for i, lineage in enumerate(lineages):
        if lineage['recombinant']:
            # recombinant
            *parent, end = lineage['parents'][0].split(".")
            node = {
                    'name': lineage['name'], 
                    'children': [], 
                    'compressed_name':lineage['compressed_name'], 
                    'otherParents': lineage['parents'][1:],
                }
        else:
            parts = lineage['name'].split(".")
            *parent, end = parts
            node = {'name': lineage['name'], 'children': [], 'compressed_name':lineage['compressed_name']}
        group: str = node['compressed_name'].split('.')[0]
        if group.startswith('X'):
            group = 'Recombinant'
        if group not in groups:
            groups.append(group)
        node['group'] = groups.index(group)
        if not parent:
            print(lineage)
            insertNodeIntoTree(root, 'root', node)
            continue
        insertNodeIntoTree(root, ".".join(parent), node)

    with open('tree/data.json', 'w') as f:
        json.dump(root, f)

    nodes, links = treeTograph(root)
    with open('graph/data.json', 'w') as f:
        json.dump({'nodes':nodes, 'links':links}, f)

if __name__ == "__main__":
    app()
