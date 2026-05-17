# AutoPM — Agent instructions

This repository powers **AutoPM**, an AI-native project management system. The story agent follows the [OpenHands](https://github.com/OpenHands/OpenHands) pattern:

- **Event log** — actions and observations appended each step
- **Agent context** — repo skills + triggered knowledge skills
- **Rolling condenser** — compresses history when context grows
- **Tool loop** — `read_file` → `write_file` → `finish` (GitHub API)
- **Security analyzer** — blocks placeholder or invalid file content before commit

Agent implementation: `modules/agent/` (see `AGENTS.md` there for coding rules).

## For target repositories (WebLLM, etc.)

Add an `AGENTS.md` at the repo root with your project conventions. AutoPM loads it automatically on every agent run.
