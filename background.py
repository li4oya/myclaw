from __future__ import annotations

import subprocess
import threading
import uuid
from queue import Queue
from typing import Any

from myclaw.config import BACKGROUND_COMMAND_TIMEOUT, MAX_TOOL_OUTPUT, WORKDIR


class BackgroundManager:
    def __init__(self):
        self.tasks: dict[str, dict[str, Any]] = {}
        self.notifications: Queue = Queue()

    def run(self, command: str, *, source_task_id: int | None = None, timeout: int | None = None) -> str:
        background_id = str(uuid.uuid4())[:8]
        self.tasks[background_id] = {
            "status": "running",
            "command": command,
            "result": None,
            "source_task_id": source_task_id,
        }
        thread = threading.Thread(
            target=self._execute,
            args=(background_id, command, timeout or BACKGROUND_COMMAND_TIMEOUT),
            daemon=True,
        )
        thread.start()
        return background_id

    def _execute(self, background_id: str, command: str, timeout: int):
        status = "completed"
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=WORKDIR,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = (result.stdout + result.stderr).strip() or "(no output)"
        except subprocess.TimeoutExpired:
            status = "timeout"
            output = f"Error: Timeout ({timeout}s)"
        except Exception as exc:
            status = "error"
            output = f"Error: {exc}"

        output = output[:MAX_TOOL_OUTPUT]
        task = self.tasks[background_id]
        task["status"] = status
        task["result"] = output
        self.notifications.put(
            {
                "background_id": background_id,
                "source_task_id": task.get("source_task_id"),
                "status": status,
                "command": command[:120],
                "result": output[:1000],
            }
        )

    def check(self, background_id: str | None = None) -> str:
        if background_id:
            task = self.tasks.get(background_id)
            if not task:
                return f"Unknown background task: {background_id}"
            return (
                f"{background_id}: [{task['status']}] {task['command']}\n"
                f"{task.get('result') or '(running)'}"
            )
        if not self.tasks:
            return "No background tasks."
        lines = []
        for bg_id, task in self.tasks.items():
            lines.append(f"{bg_id}: [{task['status']}] {task['command'][:80]}")
        return "\n".join(lines)

    def drain(self) -> list[dict[str, Any]]:
        items = []
        while not self.notifications.empty():
            items.append(self.notifications.get_nowait())
        return items

    def has_running(self) -> bool:
        return any(task.get("status") == "running" for task in self.tasks.values())
