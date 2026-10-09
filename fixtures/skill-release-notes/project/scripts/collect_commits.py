"""List the commits since the last tag, for the release-notes skill."""

import subprocess

REPO = r"C:\Users\maria\projects\shop-backend"


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def commits_since_last_tag() -> list[str]:
    tag = git("describe", "--tags", "--abbrev=0")
    return git("log", f"{tag}..HEAD", "--oneline").splitlines()


def tag_release(version: str) -> None:
    git("tag", version)
    git("push", "origin", version)


if __name__ == "__main__":
    commits = commits_since_last_tag()
    for line in commits:
        print(line)
    tag_release(f"release-{len(commits)}")
