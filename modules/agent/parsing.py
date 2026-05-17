"""JSON extraction from LLM responses (handles truncation from small models)."""

import json
import re

VALID_ACTIONS = frozenset(
    {"read_file", "write_file", "list_tree", "search_files", "think", "finish"}
)

ACTION_ALIASES = {
    "read": "read_file",
    "write": "write_file",
    "list": "list_tree",
    "search": "search_files",
    "complete": "finish",
    "done": "finish",
    "list_files": "list_tree",
    "list_directory": "list_tree",
    "grep": "search_files",
    "find": "search_files",
}

# Model sometimes puts a sentence in "action" — map keywords to a real tool
_ACTION_INTENT = (
    (re.compile(r"\bread\b", re.I), "read_file"),
    (re.compile(r"\bwrite\b|\bedit\b|\bupdate\b", re.I), "write_file"),
    (re.compile(r"\blist\b.*\btree\b|\blist_tree\b|\blist_files\b", re.I), "list_tree"),
    (re.compile(r"\bsearch\b|\bfind\b", re.I), "search_files"),
    (re.compile(r"\bfinish\b|\bdone\b|\bcomplete\b", re.I), "finish"),
    (re.compile(r"\bthink\b|\bplan\b", re.I), "think"),
)


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def _repair_truncated_object(text: str) -> str:
    """Best-effort close for JSON cut off mid-stream (common with small Ollama models)."""
    start = text.find("{")
    if start < 0:
        return text
    text = text[start:]

    # Drop trailing incomplete key/value fragment (e.g. `"dep` or `, "foo": "bar`)
    text = re.sub(r',?\s*"[^"]*$', "", text)
    text = re.sub(r",\s*$", "", text)

    in_string = False
    escape = False
    stack: list[str] = []
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            if ch == stack[-1]:
                stack.pop()

    if in_string:
        text += '"'
    text += "".join(reversed(stack))
    return text


def _extract_partial_fields(text: str) -> dict | None:
    """Pull known fields from broken JSON when repair fails."""
    result: dict = {}

    def _parse_string(match: re.Match[str]) -> str:
        try:
            return json.loads(f'"{match.group(1)}"')
        except json.JSONDecodeError:
            return match.group(1)

    reasoning = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if reasoning:
        result["reasoning"] = _parse_string(reasoning)

    approach = re.search(r'"approach"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if approach:
        result["approach"] = _parse_string(approach)

    paths_block = re.search(r'"relevant_paths"\s*:\s*\[([^\]]*)\]', text, re.DOTALL)
    if paths_block:
        paths = re.findall(r'"([^"]+)"', paths_block.group(1))
        if paths:
            result["relevant_paths"] = paths

    deps_block = re.search(r'"dependencies"\s*:\s*\[([^\]]*)\]', text, re.DOTALL)
    if deps_block:
        result["dependencies"] = re.findall(r'"([^"]+)"', deps_block.group(1))

    risks_block = re.search(r'"risks"\s*:\s*\[([^\]]*)\]', text, re.DOTALL)
    if risks_block:
        result["risks"] = re.findall(r'"([^"]+)"', risks_block.group(1))

    return result if result.get("relevant_paths") or result.get("reasoning") else None


def _extract_step_fields(text: str) -> dict | None:
    """Pull action/thought/args from broken step JSON."""
    result: dict = {}

    for key in ("thought", "reasoning", "analysis"):
        m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
        if m:
            try:
                result["thought"] = json.loads(f'"{m.group(1)}"')
            except json.JSONDecodeError:
                result["thought"] = m.group(1)
            break

    action_m = re.search(r'"action"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if action_m:
        try:
            result["action"] = json.loads(f'"{action_m.group(1)}"')
        except json.JSONDecodeError:
            result["action"] = action_m.group(1)

    tool_m = re.search(r'"(?:tool|name)"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if tool_m and "action" not in result:
        try:
            result["action"] = json.loads(f'"{tool_m.group(1)}"')
        except json.JSONDecodeError:
            result["action"] = tool_m.group(1)

    args_m = re.search(r'"args"\s*:\s*(\{[\s\S]*?\})\s*[,}]', text)
    if args_m:
        try:
            result["args"] = json.loads(args_m.group(1))
        except json.JSONDecodeError:
            try:
                result["args"] = json.loads(_repair_truncated_object(args_m.group(1)))
            except json.JSONDecodeError:
                pass

    path_m = re.search(r'"path"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    if path_m and "args" not in result:
        try:
            path = json.loads(f'"{path_m.group(1)}"')
        except json.JSONDecodeError:
            path = path_m.group(1)
        result["args"] = {"path": path}

    return result if result.get("action") else None


def _normalize_action_name(raw: str) -> str:
    action = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if action in VALID_ACTIONS:
        return action
    if action in ACTION_ALIASES:
        return ACTION_ALIASES[action]
    # Long invalid action string — infer intent
    if len(raw) > 30 or " " in raw.strip():
        for pattern, name in _ACTION_INTENT:
            if pattern.search(raw):
                return name
    return action


def parse_agent_step(raw: str) -> tuple[str, dict, str, str | None]:
    """
    Parse one agent loop step. Returns (action, args, thought, error_message).
    error_message is set when the step cannot be recovered.
    """
    if not raw or not raw.strip():
        return "", {}, "", "Empty model response."

    try:
        data = extract_json(raw)
    except ValueError as e:
        partial = _extract_step_fields(_strip_fences(raw))
        if partial:
            data = partial
        else:
            return "", {}, "", str(e)

    action_raw = (
        data.get("action") or data.get("tool") or data.get("name") or ""
    )
    if isinstance(action_raw, dict):
        action_raw = action_raw.get("name") or action_raw.get("action") or ""

    action = _normalize_action_name(str(action_raw)) if action_raw else ""

    args = data.get("args") or data.get("arguments") or data.get("parameters") or {}
    if not isinstance(args, dict):
        args = {}

    # Flatten common mistake: path/content at top level
    if "path" in data and "path" not in args:
        args["path"] = data["path"]
    if "content" in data and "content" not in args:
        args["content"] = data["content"]
    if "query" in data and "query" not in args:
        args["query"] = data["query"]

    thought = (
        data.get("thought")
        or data.get("reasoning")
        or data.get("analysis")
        or ""
    )
    thought = str(thought)[:500]

    if not action:
        return "", args, thought, (
            'Missing "action". Use exactly: read_file, write_file, list_tree, '
            "search_files, think, or finish."
        )

    if action not in VALID_ACTIONS:
        hint = (
            f'Invalid action "{action_raw}". There is no rename/refactor tool. '
            "Use list_tree → read_file → write_file per file → finish."
        )
        if re.search(r"rename|rebrand|all files", str(action_raw), re.I):
            hint += " For renames: one write_file per file with full updated content."
        return "", args, thought, hint

    return action, args, thought, None


def extract_json(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError(
            "LLM returned an empty response. Use a stronger model "
            "(e.g. llama3.2, qwen2.5-coder) in project LLM settings."
        )

    text = _strip_fences(text)

    for candidate in (text, _repair_truncated_object(text)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", candidate)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    try:
                        return json.loads(_repair_truncated_object(match.group()))
                    except json.JSONDecodeError:
                        pass

    partial = _extract_partial_fields(text)
    if partial:
        partial.setdefault("dependencies", [])
        partial.setdefault("risks", [])
        partial.setdefault("approach", partial.get("reasoning", "Proceed with implementation"))
        return partial

    step_partial = _extract_step_fields(text)
    if step_partial:
        return step_partial

    preview = text[:300].replace("\n", " ")
    raise ValueError(
        f"LLM did not return valid JSON. Response preview: {preview!r}"
    ) from None
