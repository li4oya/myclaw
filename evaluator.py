from __future__ import annotations

import json
import re
from typing import Callable

from myclaw.llm_utils import extract_text_blocks


_SHELL_FIRST_TOKENS = {
    "python", "python3", "bash", "sh", "zsh", "ls", "cat", "test",
    "grep", "rg", "wc", "echo", "find", "[", "curl", "wget", "jq",
    "head", "tail", "file", "stat", "diff", "md5", "shasum",
}


def _looks_like_shell_cmd(s: str) -> bool:
    stripped = s.strip()
    if not stripped:
        return False
    first = stripped.split()[0]
    return first.startswith("/") or first.startswith("./") or first in _SHELL_FIRST_TOKENS


def _extract_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


class AcceptanceEvaluator:
    def __init__(self, *, client, model: str, command_runner: Callable[[str, int], str]):
        self.client = client
        self.model = model
        self.command_runner = command_runner

    def evaluate(self, *, user_request: str, plan: dict, tasks: list[dict]) -> dict:
        verification_results = []
        seen_commands = set()
        for task in tasks:
            command = (task.get("verification") or "").strip()
            if not command or command in seen_commands:
                continue
            seen_commands.add(command)
            if _looks_like_shell_cmd(command):
                output = self.command_runner(command, 120)
            else:
                output = command
                command = "(natural language - not executed)"
            verification_results.append(
                {
                    "task_id": task["id"],
                    "subject": task["subject"],
                    "command": command,
                    "output": output[:3000],
                }
            )

        prompt = (
            "Evaluate whether the work satisfies the user request. "
            "Return JSON only with keys: passed, summary, failures, repair_tasks, "
            "needs_skill_evolution, suggested_skill.\n"
            "repair_tasks must be an array of objects with keys: subject, description, prompt, "
            "execution, verification. "
            "execution must be one of: direct, subagent, background.\n\n"
            f"User request:\n{user_request}\n\n"
            f"Plan:\n{json.dumps(plan, ensure_ascii=False)}\n\n"
            f"Tasks:\n{json.dumps(tasks, ensure_ascii=False)}\n\n"
            f"Verification results:\n{json.dumps(verification_results, ensure_ascii=False)}"
        )
        try:
            response = self.client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2500,
            )
            raw_text = extract_text_blocks(response.content)
        except Exception as exc:
            return {
                "passed": False,
                "summary": "Evaluator request failed.",
                "failures": [f"Evaluator error: {exc}"],
                "repair_tasks": [
                    {
                        "subject": "Recover from evaluator failure",
                        "description": "Re-check the produced results and verify them manually.",
                        "prompt": f"Evaluator failed with: {exc}",
                        "execution": "direct",
                        "verification": "",
                    }
                ],
                "needs_skill_evolution": False,
                "suggested_skill": "",
                "verification_results": verification_results,
            }

        if not raw_text.strip():
            raw_text = '{"passed": false, "summary": "Evaluator returned no text.", "failures": ["No evaluator text output."], "repair_tasks": [], "needs_skill_evolution": false, "suggested_skill": ""}'
        try:
            result = _extract_json_object(raw_text)
        except Exception:
            result = {
                "passed": False,
                "summary": "Failed to parse evaluator output.",
                "failures": [raw_text[:1000]],
                "repair_tasks": [
                    {
                        "subject": "Inspect evaluator output",
                        "description": "Review the evaluator failure and fix the unmet requirement.",
                        "prompt": raw_text[:1000],
                        "execution": "subagent",
                        "verification": "",
                    }
                ],
                "needs_skill_evolution": False,
                "suggested_skill": "",
            }

        result.setdefault("passed", False)
        result.setdefault("summary", "")
        result.setdefault("failures", [])
        result.setdefault("repair_tasks", [])
        result.setdefault("needs_skill_evolution", False)
        result.setdefault("suggested_skill", "")
        result["verification_results"] = verification_results
        return result
