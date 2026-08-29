"""
llm_client.py

Provider-swappable LLM client (Day 1-2 task from the plan). Right
now it talks to Groq, since that's already a working, tested
integration from the voice receptionist project. Swapping to Qwen3
(or any other OpenAI-compatible hosted endpoint) later should only
require changing generate() and the .env LLM_PROVIDER value — nothing
in rag.py or elsewhere should need to change.
"""

from groq import Groq
from config import settings

_groq_client = Groq(api_key=settings.GROQ_API_KEY)


def generate(system_prompt: str, user_message: str) -> str:
    """
    Simple, no-tools generation — used by rag.py for plain Q&A.
    """
    if settings.LLM_PROVIDER == "groq":
        response = _groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content

    raise NotImplementedError(f"LLM provider '{settings.LLM_PROVIDER}' not implemented yet.")


def chat_completion(messages: list, tools: list = None):
    """
    Lower-level call that exposes tool-calling — used by agent.py's
    tool-calling loop (Week 2 skills: booking, leads, messages,
    escalation). Returns the raw provider response so the caller can
    inspect tool_calls, matching the pattern from the voice
    receptionist project's llm_handler.py.
    """
    if settings.LLM_PROVIDER == "groq":
        kwargs = {"model": settings.GROQ_MODEL, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return _groq_client.chat.completions.create(**kwargs)

    raise NotImplementedError(f"LLM provider '{settings.LLM_PROVIDER}' not implemented yet.")
