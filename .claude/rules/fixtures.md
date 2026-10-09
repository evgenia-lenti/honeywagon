---
paths:
  - "fixtures/**"
---

# Fixtures

- The mistakes in the fixtures are planted on purpose. Never fix them.
- The code in a fixture is never installed, imported or run.
- When a file in `project/` changes, update the line numbers in that fixture's
  `expected.json`, then run the tests.
- Nothing inside `project/` may say that it is a fixture or name a planted mistake.
- Every key or token is fake, with a real-looking prefix and an obviously fake rest.
  `expected.json` names the variable, never the value.
- `clean-plugin` must stay free of mistakes. A finding there is a false finding.
