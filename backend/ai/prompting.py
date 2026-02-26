from __future__ import annotations

from ai.base_instruction import get_base_instruction


def build_auto_chat_system_prompt(ai_instruction: str, greeting_examples: str) -> str:
    """
    Combine user-provided role instruction and examples into a single system prompt.
    Kept simple for now; later we can structure this as JSON or multi-message prompt.
    """
    ai_instruction = (ai_instruction or "").strip()
    greeting_examples = (greeting_examples or "").strip()

    parts: list[str] = []
    base = get_base_instruction().strip()
    if base:
        parts.append(base)
    if ai_instruction:
        parts.append("ROLE INSTRUCTION:\n" + ai_instruction)
    if greeting_examples:
        parts.append("GREETING EXAMPLES:\n" + greeting_examples)
    return "\n\n".join(parts).strip()


def build_greeting_prompt(system_prompt: str, peer_username: str | None, peer_display_name: str | None) -> str:
    who = peer_display_name or peer_username or "пользователь"
    uname = peer_username or ""
    header = (
        "You are generating the FIRST message to start a Telegram DM conversation.\n"
        "CRITICAL RULES:\n"
        "- Write in Russian.\n"
        "- Keep it short (1-2 sentences).\n"
        "- Emojis are allowed VERY RARELY (max 1 per greeting).\n"
        "- Do not mention you are an AI.\n"
        "- Do not include '@' in usernames.\n"
        "- Output only the final message text. No labels.\n"
        "- IMPORTANT: Base your greeting style primarily on GREETING EXAMPLES from system prompt.\n"
        "- Use GREETING EXAMPLES as style anchors (tone, vocabulary, rhythm), not as text to copy.\n"
        "- Never copy an example verbatim; always produce a new wording.\n"
        "- Keep variety: different openings, sentence forms, and synonyms.\n"
        "- If target name/username is available, adapt naturally.\n"
        "- Be natural and sound like a real person.\n"
    )
    ctx = f"Target: name='{who}', username='{uname}'."
    task = (
        "Task: Generate one unique opening message now, in the style of GREETING EXAMPLES."
    )
    return f"{header}\n\n{system_prompt}\n\n{ctx}\n{task}\n\nAssistant:"


def build_reply_prompt(system_prompt: str, history: list[dict]) -> str:
    """
    history: list of {direction: 'IN'|'OUT', text: str}
    """
    header = (
        "You are chatting in Telegram DMs as a real person.\n"
        "CRITICAL RULES:\n"
        "- Write in Russian.\n"
        "- Keep responses concise (1-3 sentences).\n"
        "- Emojis are allowed VERY RARELY (max 1-2 per entire conversation).\n"
        "- Do not mention you are an AI/bot/model.\n"
        "- Output ONLY the assistant message text. Do not include role labels like 'User:' or 'Assistant:'.\n"
        "- IMPORTANT: Consider the FULL conversation context before responding.\n"
        "- Do NOT ask questions that have already been answered in the conversation.\n"
        "- Do NOT repeat information that was already provided.\n"
        "- Move the conversation forward logically.\n"
        "- Adapt to the user's communication style (formal/casual/slang).\n"
        "- Be natural and avoid robotic or template phrases.\n"
    )
    lines: list[str] = []
    for m in history:
        role = "User" if m.get("direction") == "IN" else "Assistant"
        text = (m.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"{role}: {text}")
    transcript = "\n".join(lines)
    
    # Add context analysis instructions
    context_analysis = (
        "\n\nANALYZE THE CONVERSATION CONTEXT BEFORE RESPONDING:\n"
        "1. What has already been discussed?\n"
        "2. What information is already known?\n"
        "3. What would be a logical next step?\n"
        "4. Avoid asking redundant or obvious questions.\n"
        "5. If the user said something vague, ask ONE specific clarifying question.\n"
    )
    
    return f"{header}\n\n{system_prompt}\n\nConversation:\n{transcript}{context_analysis}\n\nAssistant:"
