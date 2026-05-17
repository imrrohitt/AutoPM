"""Tests for story-driven work scope (no hardcoded CSS/docs kinds)."""

from types import SimpleNamespace

from modules.agent.work_scope import build_work_scope


def make_story(**kwargs):
    defaults = {
        "title": "Improve homepage styles",
        "description": "Update web/styles/home.css for better contrast.",
        "acceptance_criteria": "Homepage uses darker background in home.css",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_ticket(**kwargs):
    defaults = {
        "title": "Style homepage",
        "description": "Edit web/styles/home.css",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_build_work_scope_resolves_mentioned_paths():
    tree = ["web/styles/home.css", "web/styles/global.css", "README.md"]
    scope = build_work_scope(make_story(), make_ticket(), tree)
    assert "web/styles/home.css" in scope.focus_paths
    assert scope.restrict_to_story_paths is True


def test_is_path_allowed_same_extension_when_story_names_file():
    tree = ["web/styles/home.css", "web/styles/theme.css", "src/app.js"]
    scope = build_work_scope(make_story(), make_ticket(), tree)
    assert scope.is_path_allowed("web/styles/home.css", tree)
    assert scope.is_path_allowed("web/styles/theme.css", tree)
    assert not scope.is_path_allowed("src/app.js", tree)


def test_scope_hint_includes_story_title():
    scope = build_work_scope(make_story(title="Add API docs"), make_ticket(), ["README.md"])
    assert "Add API docs" in scope.hint
    assert "SCOPE" in scope.hint
