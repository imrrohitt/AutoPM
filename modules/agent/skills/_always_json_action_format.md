# Skill: json_action_format
always: true
---

## JSON action format (every loop step)

Respond with **one JSON object only** — no markdown fences, no prose before/after.

```json
{
  "thought": "one short sentence",
  "action": "read_file",
  "args": { "path": "src/App.jsx" }
}
```

### Allowed `action` values (exact strings only)

| action | args |
|--------|------|
| `read_file` | `{"path": "repo/relative/path"}` |
| `write_file` | `{"path": "...", "content": "FULL file body", "commit_message": "..."}` |
| `list_tree` | `{"prefix": ""}` optional |
| `search_files` | `{"query": "keywords"}` |
| `think` | `{"note": "planning only"}` |
| `finish` | `{"summary": "...", "verification": "..."}` |

### Forbidden

- Do **not** invent actions (`rename`, `refactor`, `update_project`, etc.) — they do not exist.
- Do **not** use absolute paths (`/Users/...`, `C:\...`) — only repo-relative paths from `list_tree`.
- Do **not** put the task description in `action` — only use the six tools above.

### Rename / rebrand stories

There is no bulk-rename tool. Workflow: `list_tree` → for each file: `read_file` → `write_file` with updated content → `finish` when done with the batch you staged.
