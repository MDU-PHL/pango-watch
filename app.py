from datetime import datetime
import typer
from watch import File, DB
import requests

def main(
    url: str = typer.Argument(
        "https://api.github.com/repos/cov-lineages/pango-designation/contents/lineage_notes.txt?ref=master"
    ),
    slack: str = typer.Option("", help="Hook to post the results to."),
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
        for change in changes[::-1]:
            f.write(f"### {change['datetime']}\n")
            f.write(f"*{change['sha']}*\n")
            for c in change["changes"]:
                f.write(f"- \{c}\n")

    # send slack
    if slack:
        typer.echo('Sending update to slack!')
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
        r = requests.post(slack, json=data)


if __name__ == "__main__":
    typer.run(main)
