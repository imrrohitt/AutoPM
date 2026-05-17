"""Tests for OpenHands-style project intelligence."""

from modules.agent.project_intelligence import build_project_intelligence


class _Project:
    name = "WebLLM"
    goals = "Browser-based LLM client"
    tech_stack = "React, Vite"


def test_build_project_intelligence_detects_structure():
    tree = [
        "README.md",
        "package.json",
        "vite.config.js",
        "src/App.jsx",
        "src/index.css",
        "src/main.jsx",
    ]
    brief = build_project_intelligence(_Project(), tree)
    assert "WebLLM" in brief
    assert "react" in brief.lower() or "vite" in brief.lower()
    assert "src/index.css" in brief
    assert "Explore" in brief


def test_build_project_intelligence_includes_agent_docs():
    tree = ["README.md"]
    brief = build_project_intelligence(
        _Project(),
        tree,
        agent_instructions="## Custom\nUse pnpm.",
    )
    assert "Custom" in brief
    assert "pnpm" in brief
