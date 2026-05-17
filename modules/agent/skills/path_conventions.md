# Skill: path_conventions
triggers: path, write_file, read_file, blocked, out of scope
---

## Path rules

- Paths are **repo-relative** only: `src/main.jsx`, `package.json`, `README.md`.
- Never use machine paths like `/Users/...` or `C:\...` — they will be rejected or mis-resolved.
- If `read_file` fails, run `list_tree` and copy an exact path from the output.
- Root `README.md` and `src/README.md` are different — pick the one the story needs.
- Before `write_file`, you must `read_file` the same path (unless creating a brand-new file listed in the tree).
