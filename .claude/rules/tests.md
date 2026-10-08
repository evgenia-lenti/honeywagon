---
paths:
  - "tests/**/*.py"
---

# Tests

- Tests use `pytest`. One behaviour per test, named for what it checks.
- Unit tests use no network, no model and no Docker.
- Tests never modify `fixtures/`. Anything written goes to `tmp_path`.
- A check is not done until a fixture exercises it and the clean fixture stays clean.
