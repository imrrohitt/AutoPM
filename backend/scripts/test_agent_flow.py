#!/usr/bin/env python3
"""Manual end-to-end test: login → story agent run → Celery execution."""

import asyncio
import sys
import time
import uuid

import httpx

API = "http://127.0.0.1:8000/api/v1"
EMAIL = "admin@autopm.com"
PASSWORD = "changeme123"


async def main() -> int:
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("1. Login...")
        login = await client.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            print("LOGIN FAILED", login.status_code, login.text)
            return 1
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        print("2. List projects...")
        projects = await client.get(f"{API}/projects", headers=headers)
        if projects.status_code != 200 or not projects.json():
            print("No projects — create one in the UI first")
            return 1
        project = projects.json()[0]
        project_id = project["id"]
        print(f"   Project: {project['name']} ({project_id})")

        print("3. List stories...")
        stories = await client.get(f"{API}/projects/{project_id}/stories", headers=headers)
        if stories.status_code != 200 or not stories.json():
            print("No stories — create one with open tickets first")
            return 1
        story = stories.json()[0]
        story_id = story["id"]
        print(f"   Story: {story['title']} ({story_id})")

        tickets = await client.get(f"{API}/stories/{story_id}/tickets", headers=headers)
        ticket_list = tickets.json() if tickets.status_code == 200 else []
        open_tickets = [t for t in ticket_list if t.get("status") in ("open", "in_progress")]
        if not open_tickets:
            print("   No open tickets — creating one for the test...")
            created = await client.post(
                f"{API}/stories/{story_id}/tickets",
                headers=headers,
                json={
                    "title": "AutoPM E2E test ticket",
                    "description": "Automated test: update README with a short project note.",
                    "type": "task",
                    "priority": "medium",
                },
            )
            if created.status_code not in (200, 201):
                print("CREATE TICKET FAILED", created.status_code, created.text)
                return 1
            open_tickets = [created.json()]
        print(f"   Open tickets: {len(open_tickets)}")

        print("4. Start story agent run...")
        run_resp = await client.post(
            f"{API}/stories/{story_id}/agent/run",
            params={"project_id": project_id},
            headers=headers,
        )
        if run_resp.status_code not in (200, 201):
            print("START RUN FAILED", run_resp.status_code, run_resp.text)
            return 1
        run = run_resp.json()
        run_id = run["id"]
        print(f"   Run queued: {run_id} status={run['status']}")

        print("5. Poll run status (max 90s)...")
        for i in range(45):
            await asyncio.sleep(2)
            detail = await client.get(f"{API}/agent/runs/{run_id}", headers=headers)
            if detail.status_code != 200:
                print("   poll error", detail.status_code)
                continue
            data = detail.json()
            status = data["status"]
            print(f"   [{i*2}s] status={status}")
            if status in ("completed", "failed", "cancelled"):
                logs = data.get("logs") or []
                print(f"   Logs: {len(logs)} entries")
                if data.get("pr_url"):
                    print(f"   PR: {data['pr_url']}")
                if data.get("error_message"):
                    print(f"   Error: {data['error_message']}")
                for log in logs[-5:]:
                    print(f"      [{log['level']}] {log.get('step')}: {log['message'][:80]}")
                return 0 if status == "completed" else 1

        print("   Timed out waiting for agent")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
