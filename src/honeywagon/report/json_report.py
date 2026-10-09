"""The whole result of a run as JSON."""

import json

from honeywagon.models import RunResult


def render_json(result: RunResult) -> str:
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
