#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from myclaw.background import BackgroundManager
from myclaw.compression import auto_compact, estimate_tokens, micro_compact
from myclaw.config import (
    AUTO_COMPACT_THRESHOLD,
    CLIENT,
    MAX_PARALLEL_SUBAGENTS,
    MAX_REPAIR_ITERATIONS,
    MODEL,
    PLANS_DIR,
    SAME_FAILURE_THRESHOLD,
    SKILLS_DIR,
    SKILL_SOURCE_DIR,
    TASKS_DIR,
    TRANSCRIPTS_DIR,
    WORKDIR,
    ensure_runtime_dirs,
)
from myclaw.evaluator import AcceptanceEvaluator
from myclaw.llm_utils import extract_text_blocks
from myclaw.skill_evolution import SkillEvolutionEngine
from myclaw.skills import SkillRegistry
from myclaw.subagents import SubagentRunner
from myclaw.tasks import PlanStore, TaskStore
from myclaw.tools import ToolContext, build_tool_handlers, build_tool_schemas, run_bash


class MyClawApp:
    def __init__(self, mode: str = "direct"):
        ensure_runtime_dirs()
        self.mode = mode
        self.history: list[dict] = []
        self.plan_store = PlanStore(PLANS_DIR)
        self.task_store = TaskStore(TASKS_DIR)
        self.skill_registry = SkillRegistry(SKILLS_DIR, SKILL_SOURCE_DIR)
        self.skills_init_result = self.skill_registry.initialize_from_source()
        self.background = BackgroundManager()
        self.evaluator = AcceptanceEvaluator(client=CLIENT, model=MODEL, command_runner=run_bash)
        self.context = ToolContext(
            plan_store=self.plan_store,
            task_store=self.task_store,
            skill_registry=self.skill_registry,
            background=self.background,
            current_mode=self.mode,
            notes={"skills_init": self.skills_init_result},
        )
        self.subagent_runner = SubagentRunner(
            client=CLIENT,
            model=MODEL,
            schema_builder=lambda allowed: build_tool_schemas(
                allowed_names=allowed,
                include_management=False,
            ),
            handler_builder=lambda allowed: build_tool_handlers(
                self.context,
                allowed_names=allowed,
                include_management=False,
            ),
        )
        self.evolution_engine = SkillEvolutionEngine(
            client=CLIENT,
            model=MODEL,
            registry=self.skill_registry,
            command_runner=run_bash,
        )
        self.context.subagent_runner = self.subagent_runner
        self.context.evolution_engine = self.evolution_engine

    def system_prompt(self) -> str:
        return f"""You are myclaw, a compact self-improving coding agent at {WORKDIR}.
Operating mode: {self.mode}.

Behavior rules:
- The workspace root for all tool paths is exactly: {WORKDIR}
- Treat user paths as relative to that workspace root, not to the shell directory that launched python.
- If a path is uncertain, inspect the workspace first instead of guessing a prefixed path like ./myclaw/...
- For multi-step work, persist a plan first with plan_create and then create task graph entries with task_create/task_update.
- In plan mode, stop after the plan and task graph are saved and summarized.
- In direct mode, first create the plan and task graph, then stop the planning turn. The harness will auto-run ready tasks, verify outcomes, and ask you to repair failures.
- Capture acceptance criteria from the user's request.
- Prefer load_skill before unfamiliar workflows.
- Use evolve_skill when repeated failure suggests missing reusable knowledge.
- Use delegate_task for isolated subtasks that should return only a summary.

Available skills:
{self.skill_registry.descriptions()}
"""

    def _persistent_state_summary(self) -> str:
        plan_text = ""
        if self.context.active_plan_id:
            try:
                plan = self.plan_store.load(self.context.active_plan_id)
                tasks = self.task_store.list_tasks(self.context.active_plan_id)
                plan_text = (
                    f"Active plan:\n{json.dumps(plan, ensure_ascii=False)}\n\n"
                    f"Tasks:\n{json.dumps(tasks, ensure_ascii=False)}"
                )
            except ValueError:
                pass
        skill_text = self.skill_registry.loaded_skill_summaries_text()
        return f"{plan_text}\n\nLoaded skill summaries:\n{skill_text}".strip()

    def _append_background_notifications(self) -> bool:
        notifications = self.background.drain()
        if not notifications:
            return False

        lines = []
        for notif in notifications:
            source_task_id = notif.get("source_task_id")
            if source_task_id:
                task_status = "completed" if notif["status"] == "completed" else "failed"
                self.task_store.update(
                    source_task_id,
                    status=task_status,
                    summary=notif["result"][:2000],
                    last_error="" if task_status == "completed" else notif["result"][:2000],
                )
            lines.append(
                f"[bg:{notif['background_id']}] task={source_task_id} "
                f"status={notif['status']}: {notif['result']}"
            )

        self.history.append(
            {
                "role": "user",
                "content": "<background-results>\n" + "\n".join(lines) + "\n</background-results>",
            }
        )
        self.history.append({"role": "assistant", "content": "Noted background results."})
        return True

    def agent_loop(self) -> str:
        while True:
            micro_compact(self.history)
            if estimate_tokens(self.history) > AUTO_COMPACT_THRESHOLD:
                self.skill_registry.summarize_loaded_skills(CLIENT, MODEL)
                self.history[:] = auto_compact(
                    self.history,
                    client=CLIENT,
                    model=MODEL,
                    transcript_dir=TRANSCRIPTS_DIR,
                    preserved_context=self._persistent_state_summary(),
                )

            self._append_background_notifications()

            response = CLIENT.messages.create(
                model=MODEL,
                system=self.system_prompt(),
                messages=self.history,
                tools=build_tool_schemas(),
                max_tokens=8000,
            )
            self.history.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                return extract_text_blocks(response.content)

            results = []
            handlers = build_tool_handlers(self.context)
            self.context.manual_compact_requested = False
            self.context.manual_compact_focus = ""

            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                handler = handlers.get(block.name)
                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as exc:
                    output = f"Error: {exc}"
                print(f"> {block.name}: {str(output)[:200]}")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output),
                    }
                )

            self.history.append({"role": "user", "content": results})

            if self.context.manual_compact_requested:
                self.skill_registry.summarize_loaded_skills(CLIENT, MODEL)
                self.history[:] = auto_compact(
                    self.history,
                    client=CLIENT,
                    model=MODEL,
                    transcript_dir=TRANSCRIPTS_DIR,
                    preserved_context=self._persistent_state_summary(),
                    focus=self.context.manual_compact_focus,
                )

    def _ensure_active_plan(self, query: str) -> int:
        if self.context.active_plan_id:
            return self.context.active_plan_id
        plan = self.plan_store.create(
            query,
            self.mode,
            summary="Auto-created fallback plan because the model did not persist one explicitly.",
            acceptance_criteria=[query],
        )
        self.context.active_plan_id = plan["id"]
        return plan["id"]

    def _ensure_initial_task(self, plan_id: int, query: str):
        if self.task_store.list_tasks(plan_id):
            return
        self.task_store.create(
            "Complete the user request",
            plan_id=plan_id,
            description=query,
            prompt=query,
            execution="subagent",
            verification="",
        )

    def _normalize_planned_tasks_for_execution(self, plan_id: int):
        for task in self.task_store.list_tasks(plan_id):
            if task.get("status") != "in_progress":
                continue
            if task.get("owner") or task.get("attempts") or task.get("summary"):
                continue
            self.task_store.update(
                task["id"],
                status="pending",
                verification_notes="Reset from planner-owned in_progress to scheduler-owned pending.",
            )

    def _task_prompt(self, task: dict) -> str:
        plan = self.plan_store.load(task["plan_id"]) if task.get("plan_id") else None
        parts = [
            f"Workspace root: {WORKDIR}",
            "All file paths and shell commands should assume that workspace root.",
            f"User request:\n{self.context.current_request}",
            f"Task subject: {task['subject']}",
            f"Task description: {task.get('description', '')}",
            f"Expected execution mode: {task.get('execution')}",
        ]
        if plan:
            parts.append(f"Plan summary: {plan.get('summary', '')}")
            if plan.get("acceptance_criteria"):
                parts.append("Acceptance criteria:\n" + "\n".join(plan["acceptance_criteria"]))
        if task.get("verification"):
            parts.append(f"Verification guidance: {task['verification']}")
        return "\n\n".join(parts).strip()

    def _execute_direct_task(self, task: dict) -> dict:
        self.task_store.update(
            task["id"],
            status="in_progress",
            owner="lead",
            attempts_increment=1,
        )
        self.history.append(
            {
                "role": "user",
                "content": (
                    f"<direct-task id=\"{task['id']}\">\n{self._task_prompt(task)}\n"
                    "</direct-task>"
                ),
            }
        )
        result_text = self.agent_loop()
        latest_task = self.task_store.load(task["id"])
        if latest_task.get("status") == "in_progress":
            latest_task = self.task_store.update(
                task["id"],
                status="completed",
                summary=result_text or "(no direct-task summary)",
                last_error="",
            )
        return {
            "task_id": task["id"],
            "subject": task["subject"],
            "status": latest_task.get("status", "completed"),
            "summary": latest_task.get("summary") or result_text or "(no direct-task summary)",
        }

    def _execute_agent_task(self, task: dict) -> dict:
        self.task_store.update(
            task["id"],
            status="in_progress",
            owner="subagent",
            attempts_increment=1,
        )
        result = self.subagent_runner.run(
            prompt=self._task_prompt(task),
            description=task["subject"],
            allowed_tools=task.get("tools") or None,
        )
        success = result["status"] == "completed"
        self.task_store.update(
            task["id"],
            status="completed" if success else "failed",
            summary=result["summary"],
            last_error="" if success else result["summary"],
        )
        return {
            "task_id": task["id"],
            "subject": task["subject"],
            "status": "completed" if success else "failed",
            "summary": result["summary"],
        }

    def _run_ready_batch(self, plan_id: int) -> list[dict]:
        ready = self.task_store.ready_tasks(plan_id)
        if not ready:
            return []

        immediate_results = []
        direct_tasks = []
        agent_tasks = []
        for task in ready:
            if task.get("execution") == "background":
                self.task_store.update(
                    task["id"],
                    status="in_progress",
                    owner="background",
                    attempts_increment=1,
                )
                background_id = self.background.run(
                    task.get("prompt") or task.get("description") or task["subject"],
                    source_task_id=task["id"],
                )
                self.task_store.update(
                    task["id"],
                    background_id=background_id,
                    summary=f"Started background task {background_id}",
                )
                immediate_results.append(
                    {
                        "task_id": task["id"],
                        "subject": task["subject"],
                        "status": "started",
                        "summary": f"Started background task {background_id}",
                    }
                )
            elif task.get("execution") == "direct":
                direct_tasks.append(task)
            else:
                agent_tasks.append(task)

        if direct_tasks:
            immediate_results.append(self._execute_direct_task(direct_tasks[0]))
            return immediate_results

        if agent_tasks:
            with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_SUBAGENTS, len(agent_tasks))) as pool:
                futures = [pool.submit(self._execute_agent_task, task) for task in agent_tasks]
                for future in as_completed(futures):
                    immediate_results.append(future.result())
        return immediate_results

    def _tasks_are_stalled(self, plan_id: int) -> bool:
        tasks = self.task_store.list_tasks(plan_id)
        if not tasks:
            return False
        if self.task_store.ready_tasks(plan_id):
            return False
        if self.background.has_running():
            return False
        return True

    def _mark_open_tasks_cancelled(self, plan_id: int, note: str):
        for task in self.task_store.list_tasks(plan_id):
            if task.get("status") == "completed":
                continue
            self.task_store.update(
                task["id"],
                status="cancelled",
                verification_notes=note,
            )

    def _apply_repair_tasks(self, plan_id: int, evaluation: dict):
        self._mark_open_tasks_cancelled(plan_id, "Superseded by repair iteration.")
        repair_tasks = evaluation.get("repair_tasks") or []
        if not repair_tasks:
            repair_tasks = [
                {
                    "subject": "Repair unmet requirements",
                    "description": evaluation.get("summary", "Fix the remaining issues."),
                    "prompt": "\n".join(evaluation.get("failures", [])) or evaluation.get("summary", ""),
                    "execution": "subagent",
                    "verification": "",
                }
            ]
        _valid_exec = {"direct", "subagent", "background"}
        for repair in repair_tasks:
            execution = repair.get("execution", "subagent")
            if execution not in _valid_exec:
                execution = "subagent"
            self.task_store.create(
                repair.get("subject", "Repair task"),
                plan_id=plan_id,
                description=repair.get("description", ""),
                prompt=repair.get("prompt", repair.get("description", "")),
                execution=execution,
                verification=repair.get("verification", ""),
            )

    def _maybe_evolve_skill(self, evaluation: dict, failure_count: int):
        if failure_count < SAME_FAILURE_THRESHOLD and not evaluation.get("needs_skill_evolution"):
            return None
        skill_name = evaluation.get("suggested_skill") or "self-repair"
        observations = "\n".join(evaluation.get("failures", [])) or evaluation.get("summary", "")
        return self.evolution_engine.evolve(
            name=skill_name,
            trigger="Repeated verification failure",
            goal=self.context.current_request,
            observations=observations,
            context=self._persistent_state_summary(),
        )

    def _append_scheduler_results(self, results: list[dict]):
        if not results:
            return
        self.history.append(
            {
                "role": "user",
                "content": "<scheduled-results>\n"
                + json.dumps(results, indent=2, ensure_ascii=False)
                + "\n</scheduled-results>",
            }
        )

    def _run_verification_cycle(self, plan_id: int) -> bool:
        plan = self.plan_store.load(plan_id)
        tasks = self.task_store.list_tasks(plan_id)
        evaluation = self.evaluator.evaluate(
            user_request=self.context.current_request,
            plan=plan,
            tasks=tasks,
        )
        self.plan_store.update(
            plan_id,
            verification_entry=evaluation,
            iteration_increment=1,
            add_note=evaluation.get("summary", ""),
        )
        self.history.append(
            {
                "role": "user",
                "content": "<verification-result>\n"
                + json.dumps(evaluation, indent=2, ensure_ascii=False)
                + "\n</verification-result>",
            }
        )
        if evaluation.get("passed"):
            self.plan_store.update(plan_id, status="verified")
            self.agent_loop()
            return True

        self.plan_store.update(plan_id, status="repairing")
        return False

    def run_direct_mode(self, plan_id: int):
        repair_count = 0
        failure_count = 0
        last_failure_signature = ""
        while True:
            results = self._run_ready_batch(plan_id)
            if results:
                self._append_scheduler_results(results)
                self.agent_loop()
                continue

            if self.background.has_running():
                time.sleep(1)
                if self._append_background_notifications():
                    self.agent_loop()
                continue

            if not self._tasks_are_stalled(plan_id):
                time.sleep(0.2)
                continue

            success = self._run_verification_cycle(plan_id)
            if success:
                return

            repair_count += 1
            if repair_count >= MAX_REPAIR_ITERATIONS:
                break

            plan = self.plan_store.load(plan_id)
            evaluation = plan.get("verification_history", [])[-1]
            signature = evaluation.get("summary", "")
            if signature == last_failure_signature:
                failure_count += 1
            else:
                failure_count = 1
                last_failure_signature = signature

            evolution_result = self._maybe_evolve_skill(evaluation, failure_count)
            if evolution_result:
                self.history.append(
                    {
                        "role": "user",
                        "content": "<skill-evolution>\n"
                        + json.dumps(evolution_result, indent=2, ensure_ascii=False)
                        + "\n</skill-evolution>",
                    }
                )

            self._apply_repair_tasks(plan_id, evaluation)
            self.agent_loop()

        self.history.append(
            {
                "role": "user",
                "content": (
                    "<repair-loop-stopped>\nReached the maximum repair iterations. "
                    "Summarize the current state and remaining issues.\n</repair-loop-stopped>"
                ),
            }
        )
        self.agent_loop()

    def handle_query(self, query: str):
        self.context.current_request = query
        self.context.current_mode = self.mode
        self.context.active_plan_id = None

        self.history.append(
            {
                "role": "user",
                "content": (
                    f"<request mode=\"{self.mode}\" phase=\"planning\">\n{query}\n"
                    "If mode is direct, only create/update the plan and task graph in this turn. "
                    "Do not execute task bodies yet.\n</request>"
                ),
            }
        )
        self.agent_loop()
        plan_id = self._ensure_active_plan(query)
        self._ensure_initial_task(plan_id, query)
        self._normalize_planned_tasks_for_execution(plan_id)

        if self.mode == "plan":
            return

        self.run_direct_mode(plan_id)

    def run_repl(self):
        if self.skills_init_result:
            print(f"[skills] {self.skills_init_result}")
        while True:
            try:
                query = input(f"\033[36mmyclaw[{self.mode}] >> \033[0m")
            except (EOFError, KeyboardInterrupt):
                break

            stripped = query.strip()
            if stripped.lower() in ("q", "quit", "exit", ""):
                break
            if stripped.startswith("/mode "):
                new_mode = stripped.split(" ", 1)[1].strip()
                if new_mode in ("plan", "direct"):
                    self.mode = new_mode
                    self.context.current_mode = new_mode
                else:
                    print("Mode must be 'plan' or 'direct'.")
                continue
            if stripped == "/plans":
                print(self.plan_store.list_all())
                continue
            if stripped == "/tasks":
                plan_id = self.context.active_plan_id
                print(self.task_store.format_list(plan_id))
                continue
            if stripped == "/skills":
                print(self.skill_registry.list_summary())
                continue
            if stripped == "/compact":
                self.skill_registry.summarize_loaded_skills(CLIENT, MODEL)
                self.history[:] = auto_compact(
                    self.history,
                    client=CLIENT,
                    model=MODEL,
                    transcript_dir=TRANSCRIPTS_DIR,
                    preserved_context=self._persistent_state_summary(),
                )
                print("[manual compact complete]")
                continue

            self.handle_query(query)
            print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the myclaw agent.")
    parser.add_argument("--mode", choices=["plan", "direct"], default="direct")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = MyClawApp(mode=args.mode)
    app.run_repl()
