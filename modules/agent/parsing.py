"""JSON extraction from LLM responses (handles truncation from small models)."""

import json
import re


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

    preview = text[:300].replace("\n", " ")
    raise ValueError(
        f"LLM did not return valid JSON. Response preview: {preview!r}"
    ) from None
