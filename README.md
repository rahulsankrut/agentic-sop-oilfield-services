# Oilfield Services Domain Pack

Agentic S&OP demo for oilfield services on Gemini Enterprise + Gemini Enterprise Agent Platform.

See `SPECS.md` for the master specification. See `tasks/` for build instructions.

## Quick start

```bash
source venv/bin/activate
poetry install         # install dependencies
make auth              # GCP auth
make deploy            # deploy everything (TASK-13)
make demo-cargo-plane  # run the centerpiece demo (TASK-11)
```
