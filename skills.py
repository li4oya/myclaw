from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from myclaw.config import EVOLUTION_DIR
from myclaw.llm_utils import extract_text_blocks


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text.strip()
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta, match.group(2).strip()


class SkillRegistry:
    def __init__(self, skills_dir: Path, source_dir: Path):
        self.skills_dir = skills_dir
        self.source_dir = source_dir
        self.skills: dict[str, dict[str, Any]] = {}
        self.loaded_skill_state: dict[str, dict[str, Any]] = {}
        self.duplicate_skill_names: dict[str, list[str]] = {}
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)

    def initialize_from_source(self, force: bool = False) -> str:
        if not self.source_dir.exists():
            self.reload()
            return f"Skill source not found: {self.source_dir}"

        existing_catalog = list(self.skills_dir.rglob("SKILL.md"))
        if existing_catalog and not force:
            self.reload()
            return f"Using existing skill catalog ({len(existing_catalog)} skills)."

        copied = []
        skipped = []
        for item in sorted(self.source_dir.iterdir()):
            if item.name.startswith("."):
                continue
            target = self.skills_dir / item.name
            if item.is_dir():
                if target.exists() and not force:
                    skipped.append(item.name)
                    continue
                shutil.copytree(item, target, dirs_exist_ok=force)
                copied.append(item.name)
            else:
                if target.exists() and not force:
                    skipped.append(item.name)
                    continue
                shutil.copy2(item, target)
                copied.append(item.name)

        self.reload()
        parts = []
        if copied:
            parts.append(f"Copied: {', '.join(copied)}")
        if skipped:
            parts.append(f"Skipped existing: {', '.join(skipped)}")
        return " | ".join(parts) if parts else "No skills copied."

    def reload(self):
        self.skills = {}
        self.duplicate_skill_names = {}
        for skill_file in sorted(self.skills_dir.rglob("SKILL.md")):
            text = skill_file.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(text)
            name = meta.get("name", skill_file.parent.name)
            if name in self.skills:
                self.duplicate_skill_names.setdefault(name, []).append(str(skill_file))
                continue
            self.skills[name] = {
                "name": name,
                "meta": meta,
                "body": body,
                "path": skill_file,
                "relative_path": str(skill_file.relative_to(self.skills_dir)),
                "mtime": skill_file.stat().st_mtime,
            }

    def descriptions(self) -> str:
        if not self.skills:
            return "(no skills available)"
        lines = []
        for name, skill in sorted(self.skills.items()):
            desc = skill["meta"].get("description", "No description")
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)

    def list_summary(self) -> str:
        if not self.skills:
            return "No skills."
        lines = []
        for name, skill in sorted(self.skills.items()):
            state = self.loaded_skill_state.get(name)
            suffix = " [loaded]" if state else ""
            if name in self.duplicate_skill_names:
                suffix += " [duplicate-names-skipped]"
            lines.append(f"- {name}{suffix}: {skill['meta'].get('description', '')}")
        return "\n".join(lines)

    def get_content(self, name: str) -> str:
        skill = self.skills.get(name)
        if not skill:
            return f"Error: Unknown skill '{name}'. Available: {', '.join(sorted(self.skills.keys()))}"
        self.loaded_skill_state[name] = {
            "body": skill["body"],
            "summary": self.loaded_skill_state.get(name, {}).get("summary", ""),
            "loaded_at": time.time(),
            "path": str(skill["path"]),
        }
        return f"<skill name=\"{name}\">\n{skill['body']}\n</skill>"

    def get_existing_body(self, name: str) -> str:
        skill = self.skills.get(name)
        return skill["body"] if skill else ""

    def write_skill(self, name: str, content: str) -> Path:
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / "SKILL.md"
        path.write_text(content, encoding="utf-8")
        self.reload()
        return path

    def summarize_loaded_skills(self, client, model) -> str:
        bodies = {
            name: info["body"]
            for name, info in self.loaded_skill_state.items()
            if info.get("body")
        }
        if not bodies:
            return "(no loaded skills to compact)"

        prompt = (
            "Summarize the following loaded skills for continuity. "
            "Return JSON object mapping skill name to a short summary of key constraints.\n\n"
            + json.dumps(bodies, ensure_ascii=False)[:60000]
        )
        response = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
        )
        text = extract_text_blocks(response.content)
        try:
            summaries = json.loads(text)
            if isinstance(summaries, dict):
                for name, summary in summaries.items():
                    if name in self.loaded_skill_state:
                        self.loaded_skill_state[name]["summary"] = str(summary)
                        self.loaded_skill_state[name]["body"] = ""
        except json.JSONDecodeError:
            # Fall back to retaining the first few lines.
            for name, body in bodies.items():
                lines = [line.strip() for line in body.splitlines() if line.strip()][:6]
                self.loaded_skill_state[name]["summary"] = " | ".join(lines)[:400]
                self.loaded_skill_state[name]["body"] = ""
        return self.loaded_skill_summaries_text()

    def loaded_skill_summaries_text(self) -> str:
        if not self.loaded_skill_state:
            return "(no loaded skill summaries)"
        lines = []
        for name, state in sorted(self.loaded_skill_state.items()):
            summary = state.get("summary") or "(loaded but not summarized yet)"
            lines.append(f"- {name}: {summary}")
        return "\n".join(lines)
