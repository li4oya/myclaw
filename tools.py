from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from myclaw.config import DEFAULT_COMMAND_TIMEOUT, MAX_TOOL_OUTPUT, WORKDIR


def safe_path(path_str: str) -> Path:
    path = (WORKDIR / path_str).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {path_str}")
    return path


def run_bash(command: str, timeout: int = DEFAULT_COMMAND_TIMEOUT) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/", "mkfs", ":(){:|:&};:"]
    if any(token in command for token in dangerous):
        return "Error: Dangerous command blocked"
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
        return output[:MAX_TOOL_OUTPUT]
    except subprocess.TimeoutExpired:
        return f"Error: Timeout ({timeout}s)"
    except Exception as exc:
        return f"Error: {exc}"


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)[:MAX_TOOL_OUTPUT]
    except Exception as exc:
        return f"Error: {exc}"


def run_write(path: str, content: str) -> str:
    try:
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        target = safe_path(path)
        content = target.read_text(encoding="utf-8")
        if old_text not in content:
            return f"Error: Text not found in {path}"
        target.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_list_dir(path: str = ".") -> str:
    try:
        target = safe_path(path)
        if not target.exists():
            return f"Error: Path not found: {path}"
        if not target.is_dir():
            return f"Error: Not a directory: {path}"
        entries = []
        for child in sorted(target.iterdir()):
            marker = "/" if child.is_dir() else ""
            entries.append(child.name + marker)
        return "\n".join(entries)[:MAX_TOOL_OUTPUT] or "(empty directory)"
    except Exception as exc:
        return f"Error: {exc}"


@dataclass
class ToolContext:
    plan_store: Any
    task_store: Any
    skill_registry: Any
    background: Any
    current_mode: str = "direct"
    current_request: str = ""
    active_plan_id: int | None = None
    manual_compact_requested: bool = False
    manual_compact_focus: str = ""
    subagent_runner: Any = None
    evolution_engine: Any = None
    notes: dict[str, Any] = field(default_factory=dict)


BASE_TOOL_SCHEMAS = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "list_dir",
        "description": "List directory contents relative to workspace root.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    },
    {
        "name": "list_skills",
        "description": "List available skills.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "load_skill",
        "description": "Load a skill by name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
]

MANAGEMENT_TOOL_SCHEMAS = [
    {
        "name": "plan_create",
        "description": "Create and persist a plan for the current request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_request": {"type": "string"},
                "mode": {"type": "string", "enum": ["plan", "direct"]},
                "summary": {"type": "string"},
                "title": {"type": "string"},
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["user_request", "mode"],
        },
    },
    {
        "name": "plan_update",
        "description": "Update plan metadata or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "integer"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "status": {"type": "string"},
                "add_note": {"type": "string"},
                "acceptance_criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["plan_id"],
        },
    },
    {
        "name": "plan_get",
        "description": "Get a persisted plan by id.",
        "input_schema": {
            "type": "object",
            "properties": {"plan_id": {"type": "integer"}},
            "required": ["plan_id"],
        },
    },
    {
        "name": "plan_list",
        "description": "List saved plans.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "task_create",
        "description": "Create a task in the persistent task graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "prompt": {"type": "string"},
                "execution": {
                    "type": "string",
                    "enum": ["direct", "subagent", "background"],
                },
                "tools": {"type": "array", "items": {"type": "string"}},
                "verification": {"type": "string"},
                "add_blocked_by": {"type": "array", "items": {"type": "integer"}},
                "add_blocks": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["subject"],
        },
    },
    {
        "name": "task_update",
        "description": "Update task state, dependencies, or notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "failed", "cancelled"],
                },
                "summary": {"type": "string"},
                "verification_status": {"type": "string"},
                "verification_notes": {"type": "string"},
                "owner": {"type": "string"},
                "background_id": {"type": "string"},
                "last_error": {"type": "string"},
                "prompt": {"type": "string"},
                "description": {"type": "string"},
                "execution": {
                    "type": "string",
                    "enum": ["direct", "subagent", "background"],
                },
                "verification": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}},
                "artifacts": {"type": "array", "items": {"type": "string"}},
                "add_blocked_by": {"type": "array", "items": {"type": "integer"}},
                "add_blocks": {"type": "array", "items": {"type": "integer"}},
                "attempts_increment": {"type": "integer"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "task_get",
        "description": "Get a task by id.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "integer"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "task_list",
        "description": "List tasks, optionally filtered by plan.",
        "input_schema": {
            "type": "object",
            "properties": {"plan_id": {"type": "integer"}},
        },
    },
    {
        "name": "background_run",
        "description": "Run a command in the background.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "task_id": {"type": "integer"},
                "timeout": {"type": "integer"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "check_background",
        "description": "Check background task state.",
        "input_schema": {
            "type": "object",
            "properties": {"background_id": {"type": "string"}},
        },
    },
    {
        "name": "delegate_task",
        "description": "Run an isolated subagent and return only its summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "description": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "evolve_skill",
        "description": "Create or improve a skill based on experience.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "trigger": {"type": "string"},
                "goal": {"type": "string"},
                "observations": {"type": "string"},
                "validator_command": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["name", "trigger", "goal", "observations"],
        },
    },
    {
        "name": "compact",
        "description": "Request manual context compaction.",
        "input_schema": {
            "type": "object",
            "properties": {"focus": {"type": "string"}},
        },
    },
]


def build_tool_schemas(
    *,
    allowed_names: list[str] | None = None,
    include_management: bool = True,
) -> list[dict]:
    schemas = list(BASE_TOOL_SCHEMAS)
    if include_management:
        schemas.extend(MANAGEMENT_TOOL_SCHEMAS)
    if allowed_names is None:
        return schemas
    allowed = set(allowed_names)
    return [schema for schema in schemas if schema["name"] in allowed]


def build_tool_handlers(
    context: ToolContext,
    *,
    allowed_names: list[str] | None = None,
    include_management: bool = True,
) -> dict[str, Callable]:
    def _plan_create(**kw):
        plan = context.plan_store.create(
            kw["user_request"],
            kw["mode"],
            summary=kw.get("summary", ""),
            title=kw.get("title", ""),
            acceptance_criteria=kw.get("acceptance_criteria") or [],
        )
        context.active_plan_id = plan["id"]
        return json.dumps(plan, indent=2, ensure_ascii=False)

    def _plan_update(**kw):
        plan = context.plan_store.update(
            kw["plan_id"],
            title=kw.get("title"),
            summary=kw.get("summary"),
            status=kw.get("status"),
            add_note=kw.get("add_note"),
            acceptance_criteria=kw.get("acceptance_criteria"),
        )
        return json.dumps(plan, indent=2, ensure_ascii=False)

    def _plan_get(**kw):
        return json.dumps(context.plan_store.load(kw["plan_id"]), indent=2, ensure_ascii=False)

    def _task_create(**kw):
        plan_id = kw.get("plan_id") or context.active_plan_id
        task = context.task_store.create(
            kw["subject"],
            plan_id=plan_id,
            description=kw.get("description", ""),
            prompt=kw.get("prompt", ""),
            execution=kw.get("execution", "subagent"),
            tools=kw.get("tools") or [],
            verification=kw.get("verification", ""),
            blocked_by=kw.get("add_blocked_by") or [],
            blocks=kw.get("add_blocks") or [],
        )
        return json.dumps(task, indent=2, ensure_ascii=False)

    def _task_update(**kw):
        tid = kw["task_id"] if "task_id" in kw else kw["id"]
        task = context.task_store.update(
            tid,
            status=kw.get("status"),
            summary=kw.get("summary"),
            verification_status=kw.get("verification_status"),
            verification_notes=kw.get("verification_notes"),
            owner=kw.get("owner"),
            background_id=kw.get("background_id"),
            last_error=kw.get("last_error"),
            prompt=kw.get("prompt"),
            description=kw.get("description"),
            execution=kw.get("execution"),
            verification=kw.get("verification"),
            tools=kw.get("tools"),
            artifacts=kw.get("artifacts"),
            add_blocked_by=kw.get("add_blocked_by"),
            add_blocks=kw.get("add_blocks"),
            attempts_increment=kw.get("attempts_increment", 0),
        )
        return json.dumps(task, indent=2, ensure_ascii=False)

    def _task_get(**kw):
        tid = kw["task_id"] if "task_id" in kw else kw["id"]
        return json.dumps(context.task_store.load(tid), indent=2, ensure_ascii=False)

    def _task_list(**kw):
        return context.task_store.format_list(kw.get("plan_id"))

    def _background_run(**kw):
        background_id = context.background.run(
            kw["command"],
            source_task_id=kw.get("task_id"),
            timeout=kw.get("timeout"),
        )
        return f"Background task started: {background_id}"

    def _delegate_task(**kw):
        result = context.subagent_runner.run(
            prompt=kw["prompt"],
            description=kw.get("description", ""),
            allowed_tools=kw.get("tools"),
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _evolve_skill(**kw):
        result = context.evolution_engine.evolve(
            name=kw["name"],
            trigger=kw["trigger"],
            goal=kw["goal"],
            observations=kw["observations"],
            validator_command=kw.get("validator_command", ""),
            context=kw.get("context", ""),
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    def _compact(**kw):
        context.manual_compact_requested = True
        context.manual_compact_focus = kw.get("focus", "")
        return "Manual compaction requested."

    handlers = {
        "bash": lambda **kw: run_bash(kw["command"], kw.get("timeout", DEFAULT_COMMAND_TIMEOUT)),
        "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),
        "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
        "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
        "list_dir": lambda **kw: run_list_dir(kw.get("path", ".")),
        "list_skills": lambda **kw: context.skill_registry.list_summary(),
        "load_skill": lambda **kw: context.skill_registry.get_content(kw["name"]),
    }
    if include_management:
        handlers.update(
            {
                "plan_create": _plan_create,
                "plan_update": _plan_update,
                "plan_get": _plan_get,
                "plan_list": lambda **kw: context.plan_store.list_all(),
                "task_create": _task_create,
                "task_update": _task_update,
                "task_get": _task_get,
                "task_list": _task_list,
                "background_run": _background_run,
                "check_background": lambda **kw: context.background.check(kw.get("background_id")),
                "delegate_task": _delegate_task,
                "evolve_skill": _evolve_skill,
                "compact": _compact,
            }
        )

    if allowed_names is None:
        return handlers

    allowed = set(allowed_names)
    return {name: handler for name, handler in handlers.items() if name in allowed}
