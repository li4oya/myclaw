from __future__ import annotations

from typing import Callable

from myclaw.config import MAX_SUBAGENT_TURNS
from myclaw.llm_utils import extract_text_blocks


class SubagentRunner:
    def __init__(
        self,
        *,
        client,
        model: str,
        schema_builder: Callable[[list[str] | None], list[dict]],
        handler_builder: Callable[[list[str] | None], dict[str, Callable]],
    ):
        self.client = client
        self.model = model
        self.schema_builder = schema_builder
        self.handler_builder = handler_builder

    def run(
        self,
        *,
        prompt: str,
        description: str = "",
        allowed_tools: list[str] | None = None,
        max_turns: int = MAX_SUBAGENT_TURNS,
    ) -> dict:
        tools = self.schema_builder(allowed_tools)
        handlers = self.handler_builder(allowed_tools)
        messages = [{"role": "user", "content": prompt}]
        system = (
            "You are an isolated subagent with a fresh context. "
            "Complete the assigned subtask with the provided tools only. "
            "Return a concise summary of what you changed, checked, and any remaining risk."
        )
        if description:
            system += f"\nTask description: {description}"

        response = None
        for turn in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                system=system,
                messages=messages,
                tools=tools,
                max_tokens=6000,
            )
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                summary = extract_text_blocks(response.content)
                return {
                    "status": "completed",
                    "summary": summary or "(no subagent summary)",
                    "turns": turn + 1,
                }

            results = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                handler = handlers.get(block.name)
                try:
                    output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                except Exception as exc:
                    output = f"Error: {exc}"
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output)[:50000],
                    }
                )
            messages.append({"role": "user", "content": results})

        summary = ""
        if response is not None:
            summary = extract_text_blocks(response.content)
        return {
            "status": "timeout",
            "summary": summary or "Subagent hit the safety turn limit.",
            "turns": max_turns,
        }
