---
paths:
  - "src/**/*.py"
---

# Core code

- Every function and method has complete type hints. `mypy` must pass.
- Nothing in `src/honeywagon/` imports or assumes Claude Code.
- The core never calls a model and never writes inside the audited project.
- User-facing report text lives in data files, not in Python strings.
