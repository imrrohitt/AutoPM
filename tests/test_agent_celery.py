"""Unit tests for Celery agent task wiring."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from modules.agent.celery_app import celery_app
from modules.agent.tasks import dispatch_agent_run, run_agent_task


def test_run_agent_task_routed_to_agent_queue():
    routes = celery_app.conf.task_routes or {}
    assert routes.get("run_agent_task") == {"queue": "agent"}
    assert celery_app.conf.task_default_queue == "agent"


@patch("modules.agent.tasks.run_agent_task.apply_async")
def test_dispatch_agent_run_uses_agent_queue(mock_apply: MagicMock):
    run_id = UUID("28904300-e8ad-445b-b2fb-5869ee858829")
    dispatch_agent_run(run_id)
    mock_apply.assert_called_once_with(args=[str(run_id)], queue="agent")


@patch("modules.agent.tasks._execute_run")
def test_run_agent_task_invokes_execute(mock_execute: MagicMock):
    run_id = "28904300-e8ad-445b-b2fb-5869ee858829"
    run_agent_task.run(run_id)
    mock_execute.assert_called_once_with(UUID(run_id))


@patch("modules.agent.tasks._execute_run", side_effect=RuntimeError("boom"))
@patch("modules.agent.tasks._execute_mark_failed")
def test_run_agent_task_marks_failed_on_error(mock_mark: MagicMock, _mock_execute: MagicMock):
    run_id = "28904300-e8ad-445b-b2fb-5869ee858829"
    with pytest.raises(RuntimeError, match="boom"):
        run_agent_task.run(run_id)
    mock_mark.assert_called_once()


def test_gevent_worker_detected_from_env(monkeypatch):
    from modules.agent import tasks as agent_tasks

    monkeypatch.setenv("AUTOPM_CELERY_GEVENT", "1")
    assert agent_tasks._gevent_worker() is True
    monkeypatch.delenv("AUTOPM_CELERY_GEVENT", raising=False)
    assert agent_tasks._gevent_worker() is False


@patch("modules.agent.tasks._run_in_subprocess")
def test_gevent_execute_uses_subprocess(mock_subprocess: MagicMock, monkeypatch):
    from modules.agent import tasks as agent_tasks

    monkeypatch.setenv("AUTOPM_CELERY_GEVENT", "1")
    run_id = UUID("53fe062d-5828-49dc-81b9-4cc20f7f50dd")
    agent_tasks._execute_run(run_id)
    mock_subprocess.assert_called_once_with(run_id)
