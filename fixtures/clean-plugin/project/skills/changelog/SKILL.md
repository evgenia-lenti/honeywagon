---
name: changelog
description: Drafts a changelog entry from the git commits since the last tag. Use it when the user asks for a changelog, release notes or a summary of recent commits.
allowed-tools: Read, Bash(git log *), Bash(git describe *)
---

# Changelog

Draft a changelog entry for the commits since the last tag. Only read the repository.

1. Find the last tag with `git describe --tags --abbrev=0`.
2. List the commits since that tag with `git log <tag>..HEAD --oneline`.
3. Fill in [template.md](template.md) with one line per commit.
4. Show the draft to the user. Do not write it to a file unless the user asks.

If there is no tag yet, say so and list the last twenty commits instead.
