from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def _now() -> float:
    return time.time()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, data: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


class PlanStore:
    def __init__(self, plans_dir: Path):
        self.dir = plans_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("plan_*.json")]
        return max(ids, default=0) + 1

    def _path(self, plan_id: int) -> Path:
        return self.dir / f"plan_{plan_id}.json"

    def load(self, plan_id: int) -> dict[str, Any]:
        path = self._path(plan_id)
        if not path.exists():
            raise ValueError(f"Plan {plan_id} not found")
        return _read_json(path)

    def save(self, plan: dict[str, Any]):
        plan["updated_at"] = _now()
        _write_json(self._path(plan["id"]), plan)

    def create(
        self,
        user_request: str,
        mode: str,
        summary: str = "",
        title: str = "",
        acceptance_criteria: list[str] | None = None,
    ) -> dict[str, Any]:
        now = _now()
        plan = {
            "id": self._next_id(),
            "title": title or f"Plan for: {user_request[:60]}",
            "user_request": user_request,
            "mode": mode,
            "summary": summary,
            "acceptance_criteria": acceptance_criteria or [],
            "status": "planned" if mode == "plan" else "executing",
            "verification_history": [],
            "notes": [],
            "iteration_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        self.save(plan)
        return plan

    def update(
        self,
        plan_id: int,
        *,
        title: str | None = None,
        summary: str | None = None,
        status: str | None = None,
        notes: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        add_note: str | None = None,
        verification_entry: dict[str, Any] | None = None,
        iteration_increment: int = 0,
    ) -> dict[str, Any]:
        plan = self.load(plan_id)
        if title is not None:
            plan["title"] = title
        if summary is not None:
            plan["summary"] = summary
        if status is not None:
            plan["status"] = status
        if notes is not None:
            plan["notes"] = list(notes)
        if acceptance_criteria is not None:
            plan["acceptance_criteria"] = list(acceptance_criteria)
        if add_note:
            plan.setdefault("notes", []).append(add_note)
        if verification_entry:
            plan.setdefault("verification_history", []).append(verification_entry)
        if iteration_increment:
            plan["iteration_count"] = int(plan.get("iteration_count", 0)) + iteration_increment
        self.save(plan)
        return plan

    def latest(self) -> dict[str, Any] | None:
        plans = sorted(self.dir.glob("plan_*.json"))
        if not plans:
            return None
        return _read_json(plans[-1])

    def list_all(self) -> str:
        plans = [_read_json(path) for path in sorted(self.dir.glob("plan_*.json"))]
        if not plans:
            return "No plans."
        lines = []
        for plan in plans:
            lines.append(
                f"#{plan['id']} [{plan['status']}] ({plan['mode']}) "
                f"{plan['title']}"
            )
        return "\n".join(lines)


class TaskStore:
    VALID_STATUSES = {"pending", "in_progress", "completed", "failed", "cancelled"}
    VALID_EXECUTIONS = {"direct", "subagent", "background"}

    def __init__(self, tasks_dir: Path):
        self.dir = tasks_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _next_id(self) -> int:
        ids = [int(f.stem.split("_")[1]) for f in self.dir.glob("task_*.json")]
        return max(ids, default=0) + 1

    def _path(self, task_id: int) -> Path:
        return self.dir / f"task_{task_id}.json"

    def load(self, task_id: int) -> dict[str, Any]:
        path = self._path(task_id)
        if not path.exists():
            raise ValueError(f"Task {task_id} not found")
        return _read_json(path)

    def save(self, task: dict[str, Any]):
        task["updated_at"] = _now()
        _write_json(self._path(task["id"]), task)

    def create(
        self,
        subject: str,
        *,
        plan_id: int | None = None,
        description: str = "",
        prompt: str = "",
        execution: str = "subagent",
        tools: list[str] | None = None,
        verification: str = "",
        blocked_by: list[int] | None = None,
        blocks: list[int] | None = None,
    ) -> dict[str, Any]:
        if execution not in self.VALID_EXECUTIONS:
            raise ValueError(f"Invalid execution mode: {execution}")
        now = _now()
        task = {
            "id": self._next_id(),
            "plan_id": plan_id,
            "subject": subject,
            "description": description,
            "prompt": prompt or description or subject,
            "execution": execution,
            "tools": tools or [],
            "verification": verification,
            "status": "pending",
            "blockedBy": list(blocked_by or []),
            "blocks": list(blocks or []),
            "summary": "",
            "verification_status": "pending",
            "verification_notes": "",
            "background_id": None,
            "attempts": 0,
            "owner": "",
            "artifacts": [],
            "last_error": "",
            "created_at": now,
            "updated_at": now,
        }
        self.save(task)
        for blocked_id in task["blocks"]:
            self._add_blocked_by(blocked_id, task["id"])
        return task

    def _add_blocked_by(self, task_id: int, blocked_by_id: int):
        task = self.load(task_id)
        if blocked_by_id not in task.get("blockedBy", []):
            task.setdefault("blockedBy", []).append(blocked_by_id)
            self.save(task)

    def _clear_dependency(self, completed_id: int):
        for path in self.dir.glob("task_*.json"):
            task = _read_json(path)
            if completed_id in task.get("blockedBy", []):
                task["blockedBy"].remove(completed_id)
                self.save(task)

    def update(
        self,
        task_id: int,
        *,
        status: str | None = None,
        summary: str | None = None,
        verification_status: str | None = None,
        verification_notes: str | None = None,
        owner: str | None = None,
        background_id: str | None = None,
        last_error: str | None = None,
        prompt: str | None = None,
        description: str | None = None,
        execution: str | None = None,
        verification: str | None = None,
        tools: list[str] | None = None,
        artifacts: list[str] | None = None,
        add_blocked_by: list[int] | None = None,
        add_blocks: list[int] | None = None,
        attempts_increment: int = 0,
    ) -> dict[str, Any]:
        task = self.load(task_id)
        if status is not None:
            if status not in self.VALID_STATUSES:
                raise ValueError(f"Invalid status: {status}")
            task["status"] = status
            if status == "completed":
                self._clear_dependency(task_id)
        if execution is not None:
            if execution not in self.VALID_EXECUTIONS:
                raise ValueError(f"Invalid execution mode: {execution}")
            task["execution"] = execution
        if summary is not None:
            task["summary"] = summary
        if verification_status is not None:
            task["verification_status"] = verification_status
        if verification_notes is not None:
            task["verification_notes"] = verification_notes
        if owner is not None:
            task["owner"] = owner
        if background_id is not None:
            task["background_id"] = background_id
        if last_error is not None:
            task["last_error"] = last_error
        if prompt is not None:
            task["prompt"] = prompt
        if description is not None:
            task["description"] = description
        if verification is not None:
            task["verification"] = verification
        if tools is not None:
            task["tools"] = list(tools)
        if artifacts is not None:
            task["artifacts"] = list(artifacts)
        if add_blocked_by:
            merged = set(task.get("blockedBy", []))
            merged.update(add_blocked_by)
            task["blockedBy"] = sorted(merged)
        if add_blocks:
            merged = set(task.get("blocks", []))
            merged.update(add_blocks)
            task["blocks"] = sorted(merged)
            for blocked_id in add_blocks:
                self._add_blocked_by(blocked_id, task_id)
        if attempts_increment:
            task["attempts"] = int(task.get("attempts", 0)) + attempts_increment
        self.save(task)
        return task

    def list_tasks(self, plan_id: int | None = None) -> list[dict[str, Any]]:
        tasks = [_read_json(path) for path in sorted(self.dir.glob("task_*.json"))]
        if plan_id is not None:
            tasks = [task for task in tasks if task.get("plan_id") == plan_id]
        return tasks

    def ready_tasks(self, plan_id: int | None = None) -> list[dict[str, Any]]:
        tasks = self.list_tasks(plan_id)
        return [
            task
            for task in tasks
            if task.get("status") == "pending" and not task.get("blockedBy")
        ]

    def has_open_tasks(self, plan_id: int | None = None) -> bool:
        tasks = self.list_tasks(plan_id)
        return any(task.get("status") not in ("completed", "cancelled") for task in tasks)

    def running_background_tasks(self, plan_id: int | None = None) -> list[dict[str, Any]]:
        tasks = self.list_tasks(plan_id)
        return [
            task
            for task in tasks
            if task.get("execution") == "background" and task.get("status") == "in_progress"
        ]

    def format_list(self, plan_id: int | None = None) -> str:
        tasks = self.list_tasks(plan_id)
        if not tasks:
            return "No tasks."
        lines = []
        for task in tasks:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]",
                "failed": "[!]",
                "cancelled": "[-]",
            }.get(task["status"], "[?]")
            blocked = f" blocked_by={task['blockedBy']}" if task.get("blockedBy") else ""
            lines.append(
                f"{marker} #{task['id']} ({task['execution']}) {task['subject']}{blocked}"
            )
        return "\n".join(lines)
