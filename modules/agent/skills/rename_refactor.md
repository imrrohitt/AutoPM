# Skill: rename_refactor
triggers: rename, rebrand, whole project, entire project, all files, webllm, browserllm, project name
---

## Project-wide rename / rebrand

1. Call `list_tree` with `{"prefix": ""}` to see every path.
2. For **each file** that must change (package.json, README, src/*.jsx, etc.):
   - `read_file` with repo path (e.g. `package.json`, not an absolute path)
   - `write_file` with the **complete** updated file (replace old name with new name inside content)
3. Stage one file per `write_file` call. Repeat until all relevant files are updated.
4. Call `finish` with summary and verification vs acceptance criteria.

**Paths:** Use paths exactly as shown in the tree (`README.md` vs `src/README.md` are different files).

**Scope:** Project-wide renames may touch many files — that is expected. Do not skip `package.json`, `index.html`, or source files that reference the old name.
