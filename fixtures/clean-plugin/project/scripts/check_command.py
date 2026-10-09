"""PreToolUse hook: block shell commands that delete files recursively."""

import json
import sys

BLOCKED = ("rm -rf", "rm -fr", "git clean -fdx")


def main() -> int:
    event = json.load(sys.stdin)
    command = event.get("tool_input", {}).get("command", "")
    for pattern in BLOCKED:
        if pattern in command:
            print(f"Blocked by team-notes: '{pattern}' is not allowed.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
