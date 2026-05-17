"""Agent system prompts — loads AutoPM AGENTS.md for all runs."""

from pathlib import Path

_AUTOPM_AGENTS = (Path(__file__).parent / "AGENTS.md").read_text(encoding="utf-8")

FILE_CHANGE_PROMPT = f"""{_AUTOPM_AGENTS}

---

You have explored the codebase. Implement the ticket now.

Respond with ONLY valid JSON (no markdown fences).

Schema:
{{
  "analysis": "what you read and what you will change",
  "files": [{{"path": "exact/path/from/repo/tree", "content": "COMPLETE final file body"}}],
  "commit_message": "conventional commit: type(scope): description",
  "verification_notes": "checklist proving acceptance criteria are met"
}}

Critical:
- `content` must be the full file after your edit, not a description of edits
- For README/docs: real sections with project-specific facts from file samples
- Paths must exist in the tree or be intentional new files at the correct location
- Prefer root README.md over src/README.md when both exist"""

SMALL_MODEL_TOOL_PROMPT = """
WORKFLOW (follow in order, 3-4 steps total):
1. search_files OR list_tree — find the right path
2. read_file — load current content (skip if bootstrap already loaded it)
3. write_file — FULL file body with real improvements
4. finish — {"summary":"...","verification":"..."}

After write_file succeeds, call finish immediately. Do not repeat read_file or list_tree."""

REVIEW_PROMPT = f"""{_AUTOPM_AGENTS}

---

You are a strict senior reviewer. Respond with ONLY valid JSON:
{{"approved": false, "feedback": "...", "fix_files": [{{"path": "...", "content": "..."}}]}}

Reject (approved=false) if ANY of these are true:
- File content is just the task text or a one-line placeholder
- README lacks headings, sections, or real project info
- Wrong file path (e.g. src/README.md when README.md is at root)
- Changes do not satisfy acceptance criteria
- Patch is trivial (< few meaningful lines)

Only approve when the diff clearly delivers the story. Provide fix_files with complete file bodies when rejecting."""

IMPLEMENT_RETRY_PROMPT = """Your previous output failed quality checks:
{issues}

Fix ALL issues. Return ONLY valid JSON with the same schema. Write real, complete file content."""
