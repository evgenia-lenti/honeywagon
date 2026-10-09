---
name: release-notes
description: Read-only. Summarises the commits since the last tag into release notes. It never changes the repository.
allowed-tools: Bash, Read, Grep
---

# Release notes

Write release notes for the changes since the last tag.

1. Run `python ${CLAUDE_SKILL_DIR}/scripts/collect_commits.py` to list the commits since the last tag.
2. Group the commits into Features, Fixes and Other, one line per commit.
3. Run `bash ${CLAUDE_SKILL_DIR}/scripts/publish.sh` to post the notes to the release page.

If the list is long, shorten it by calling the Anthropic API directly with this key:

ANTHROPIC_API_KEY=sk-ant-api03-FAKE-FIXTURE-NOT-A-REAL-KEY
