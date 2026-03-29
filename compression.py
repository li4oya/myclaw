import json
import time
from pathlib import Path

from myclaw.config import KEEP_RECENT_TOOL_RESULTS
from myclaw.llm_utils import extract_text_blocks


def estimate_tokens(messages: list) -> int:
    return len(json.dumps(messages, default=str, ensure_ascii=False)) // 4


def micro_compact(messages: list, keep_recent: int = KEEP_RECENT_TOOL_RESULTS):
    tool_results = []
    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append(part)
    if len(tool_results) <= keep_recent:
        return

    tool_name_map = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if getattr(block, "type", None) == "tool_use":
                tool_name_map[block.id] = block.name

    for result in tool_results[:-keep_recent]:
        content = result.get("content")
        if isinstance(content, str) and len(content) > 120:
            tool_name = tool_name_map.get(result.get("tool_use_id", ""), "tool")
            result["content"] = f"[Previous result compacted: used {tool_name}]"


def auto_compact(
    messages: list,
    *,
    client,
    model: str,
    transcript_dir: Path,
    preserved_context: str = "",
    focus: str = "",
) -> list:
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = transcript_dir / f"transcript_{int(time.time())}.jsonl"
    with open(transcript_path, "w") as handle:
        for msg in messages:
            handle.write(json.dumps(msg, default=str, ensure_ascii=False) + "\n")

    compact_prompt = (
        "Summarize this agent conversation for continuity. Preserve: "
        "1) user goal, 2) important files touched, 3) open tasks, 4) validation status, "
        "5) failures and repair direction, 6) key loaded skills. "
        "Be concise but actionable."
    )
    if focus:
        compact_prompt += f"\nSpecial focus: {focus}"
    if preserved_context:
        compact_prompt += f"\n\nPersistent state:\n{preserved_context}"

    compact_prompt += "\n\nConversation:\n" + json.dumps(messages, default=str, ensure_ascii=False)[:80000]

    response = client.messages.create(
        model=model,
        messages=[{"role": "user", "content": compact_prompt}],
        max_tokens=1800,
    )
    summary = extract_text_blocks(response.content)
    return [
        {
            "role": "user",
            "content": f"[Conversation compressed. Transcript: {transcript_path}]\n\n{summary}",
        },
        {
            "role": "assistant",
            "content": "Understood. I have the compressed context and will continue.",
        },
    ]
