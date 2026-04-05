from __future__ import annotations

import json
import re
import time
from typing import Callable

from myclaw.config import EVOLUTION_DIR
from myclaw.llm_utils import extract_text_blocks


def _slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "evolved-skill"


class SkillEvolutionEngine:
    def __init__(self, *, client, model: str, registry, command_runner: Callable[[str, int], str]):
        self.client = client
        self.model = model
        self.registry = registry
        self.command_runner = command_runner
        EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)

    def evolve(
        self,
        *,
        name: str,
        trigger: str,
        goal: str,
        observations: str,
        validator_command: str = "",
        context: str = "",
    ) -> dict:
        skill_name = _slugify(name)
        existing_body = self.registry.get_existing_body(skill_name)
        skill_creator = self.registry.get_existing_body("skill-creator")

        prompt = (
            "Create or improve an Agent Skill. Return only the full SKILL.md content.\n\n"
            f"Skill name: {skill_name}\n"
            f"Trigger/problem: {trigger}\n"
            f"Goal: {goal}\n"
            f"Observations: {observations}\n"
        )
        if existing_body:
            prompt += f"\nExisting skill body:\n{existing_body}\n"
        if context:
            prompt += f"\nAdditional context:\n{context}\n"
        if skill_creator:
            prompt += (
                "\nReference guidance from skill-creator (follow this style, but be concise):\n"
                f"{skill_creator[:12000]}\n"
            )

        response = self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
        )
        content = extract_text_blocks(response.content).strip()
        if not content.startswith("---"):
            content = (
                f"---\nname: {skill_name}\ndescription: Auto-evolved skill for {goal[:80]}\n---\n\n"
                + content
            )

        path = self.registry.write_skill(skill_name, content)
        validation_output = "No validator command."
        validation_status = "passed"
        if validator_command:
            validation_output = self.command_runner(validator_command, 120)
            lowered = validation_output.lower()
            if "error" in lowered or "traceback" in lowered or "failed" in lowered:
                validation_status = "failed"

        log = {
            "skill_name": skill_name,
            "trigger": trigger,
            "goal": goal,
            "validator_command": validator_command,
            "validation_status": validation_status,
            "validation_output": validation_output[:2000],
            "path": str(path),
            "timestamp": time.time(),
        }
        log_path = EVOLUTION_DIR / f"{int(time.time())}_{skill_name}.json"
        log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
        self.registry.reload()
        return log
