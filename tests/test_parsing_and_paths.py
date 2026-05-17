"""Tests for stable agent step JSON parsing and repo path normalization."""

from modules.agent.parsing import parse_agent_step
from modules.agent.path_utils import normalize_repo_path
from modules.agent.work_scope import _is_project_wide_task


def test_parse_valid_step():
    raw = '{"thought":"read pkg","action":"read_file","args":{"path":"package.json"}}'
    action, args, thought, err = parse_agent_step(raw)
    assert err is None
    assert action == "read_file"
    assert args["path"] == "package.json"
    assert "read" in thought.lower()


def test_parse_rejects_rename_action():
    raw = '{"thought":"go","action":"rename all files to browserllm","args":{}}'
    action, args, thought, err = parse_agent_step(raw)
    assert action == ""
    assert err and "rename" in err.lower()


def test_parse_partial_json():
    raw = '{"thought":"x","action":"list_tree","args":{"prefix":""'
    action, args, thought, err = parse_agent_step(raw)
    assert action == "list_tree"
    assert err is None


def test_normalize_absolute_path():
    tree = ["package.json", "src/README.md", "src/App.jsx"]
    raw = "/Users/pavel/Documents/workspace/BrowserLLM/src/README.md"
    assert normalize_repo_path(raw, tree) == "src/README.md"


def test_project_wide_rename_story():
    text = "rename whole project to WebLLM to BrowserLLM"
    assert _is_project_wide_task(text) is True
