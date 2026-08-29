"""
agent.py

Week 2's upgraded brain: combines RAG (grounded answers from the
tenant's knowledge base) with tool-calling (booking, lead capture,
message-taking, escalation) — same tool-calling loop pattern as
llm_handler.py in the voice receptionist project, but tenant-scoped
throughout, and with skills added on top of plain Q&A.

Critical guardrail (per the plan): raw tool-call JSON must never
reach the caller. The loop always asks the LLM for a final natural-
language turn after any tool executes — never returns a tool's raw
dict directly.
"""

import json
from models import Config
from sqlalchemy.orm import Session
import vector_store
import skills
from llm_client import chat_completion


MAX_TOOL_ITERATIONS = 5

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment for the caller.",
            "parameters": {
                "type": "object",
                "properties": {
                    "datetime_str": {"type": "string", "description": "ISO format, e.g. 2026-07-30T14:00:00"},
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                },
                "required": ["datetime_str", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_lead",
            "description": "Log a caller's interest when they're not ready to book yet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "intent": {"type": "string", "description": "What they're interested in"},
                },
                "required": ["name", "intent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_message",
            "description": "Log a message for the business to follow up on, when you can't resolve the request directly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["name", "message"],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "escalate",
            "description": "Flag this conversation for a human to handle directly — use for pricing questions, medical/sensitive topics, or anything you should not answer yourself.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "name": {"type": "string", "description": "The caller's name, collected before escalating."},
                    "phone": {"type": "string", "description": "The caller's phone number, collected before escalating."},
                },
                "required": ["reason", "name", "phone"],
            },
        },
    },
    {
    "type": "function",
    "function": {
        "name": "get_day_of_week",
        "description": "Get the exact day of the week for a given date. ALWAYS use this tool instead of calculating the day of week yourself — never guess or reason it out.",
        "parameters": {
            "type": "object",
            "properties": {
                "date_str": {"type": "string", "description": "Date in YYYY-MM-DD format"},
            },
            "required": ["date_str"],
            },
        },
    },
    {
    "type": "function",
    "function": {
        "name": "get_current_date",
        "description": "Get today's actual current date and day of week. ALWAYS use this first if the caller references 'today', 'tomorrow', 'this Friday', or any other relative date — never assume or guess today's date yourself.",
        "parameters": {"type": "object", "properties": {}
            },
        },
    },
]

SYSTEM_PROMPT_TEMPLATE = """You are the AI receptionist for {tenant_name}, a {vertical} business.

{settings_section}

Answer using the STRUCTURED DETAILS above as the authoritative source
for hours, services, and booking rules — if the CONTEXT below conflicts
with them, trust the STRUCTURED DETAILS instead, since the business
owner set those directly.

For anything not covered by STRUCTURED DETAILS, use the CONTEXT below,
retrieved from this business's own knowledge base. Never guess or use
outside knowledge.

You have tools to book appointments, capture leads, take messages, and
escalate. Booking requests must respect the booking rules above.

HARD RULES:
1. NEVER state a price. If asked about cost, use the escalate tool.
2. NEVER discuss medical/health details or give advice yourself. If a
   caller describes symptoms or a medical concern, first check
   whether this business's own services genuinely relate to it (per
   STRUCTURED DETAILS and CONTEXT). If they do, use the escalate tool
   so a staff member follows up. If this business has nothing to do
   with medical/health matters, say so directly and politely, and
   suggest the caller consult a doctor — do not escalate or take a
   message, since no one at this business would actually follow up
   on it.
3. Before escalating or taking a message for any unanswered question,
   first judge whether it's genuinely something this business could
   plausibly follow up on, versus something clearly outside what this
   business does at all (per STRUCTURED DETAILS and CONTEXT).
   - If it's a real, in-scope request you just don't have the answer
     to yet (e.g. a specific availability question, a detail not yet
     in the knowledge base), use take_message or escalate.
   - If it's clearly unrelated to this business entirely, say so
     honestly and directly instead — do not escalate or take a
     message implying someone will follow up on something this
     business was never going to handle.
4. Always confirm details (date, time, name, and phone number) back to
   the caller before booking, and always ask for a phone number even
   though it is not strictly required — the business needs a way to
   reach the caller if something needs to change.
5. NEVER read tool results back as raw data — always respond in
   natural, conversational language.
6. When a tool call fails (success: false), your natural-language
   explanation must be based ONLY on that tool's "message" field.
   Do not invent, guess, reconstruct, or supplement the reason —
   not the day of week, not business hours, not anything else you
   haven't been explicitly given. Rephrase the message conversationally,
   but never change or add to its substance.
7. NEVER compute, guess, or reason out a day of the week yourself —
   always call get_day_of_week for any date you need to reference,
   whether answering a direct question or handling a booking.
8. NEVER assume or guess today's date. For any relative date
   reference ("today", "tomorrow", "this Friday", "next week"),
   call get_current_date first to get the real date, then compute
   from there.
9. Whenever you use the escalate tool, you must first collect the
    caller's name and phone number if you don't already have them in
    this conversation, before calling the tool — never escalate
    without contact info. Pass the FULL context of what they need
    (not just a short label) as the reason, so the business owner
    has everything they need to follow up without re-asking the
    customer. After escalating, always tell the caller clearly that
    a team member will contact them shortly.   
CONTEXT:
{context}
"""
def _format_settings(config) -> str:
    """Turns a tenant's Config row into readable text for the prompt."""
    if not config:
        return "STRUCTURED DETAILS: (not yet configured by this business)"

    hours_lines = []
    for day, h in (config.hours or {}).items():
        if h.get("closed"):
            hours_lines.append(f"  {day.capitalize()}: Closed")
        else:
            hours_lines.append(f"  {day.capitalize()}: {h.get('open')} - {h.get('close')}")

    services = ", ".join(config.services) if config.services else "(none listed)"
    rules = config.booking_rules or {}

    return f"""STRUCTURED DETAILS (set directly by the business owner — trust these over anything else):
Hours:
{chr(10).join(hours_lines) if hours_lines else "  (not set)"}
Services: {services}
Booking rules: can book up to {rules.get('advance_days', 'N/A')} days ahead, minimum {rules.get('min_notice_hours', 'N/A')} hours notice.
Persona: {config.persona or "A friendly, professional receptionist."}"""


def _execute_tool(db: Session, tenant_id: str, conversation_id: str, name: str, args: dict) -> dict:
    if name == "book_appointment":
        return skills.book_appointment(db, tenant_id, conversation_id, **args)
    if name == "capture_lead":
        return skills.capture_lead(db, tenant_id, conversation_id, **args)
    if name == "take_message":
        return skills.take_message(db, tenant_id, conversation_id, **args)
    if name == "escalate":
        return skills.escalate(db, tenant_id, conversation_id, **args)
    if name == "get_day_of_week":
        return skills.get_day_of_week(**args)
    if name == "get_current_date":
        return skills.get_current_date()
    return {"error": f"Unknown tool: {name}"}

def respond(db: Session, tenant, conversation_id: str, message: str, history: list) -> dict:
    """
    Full Week 2 agent turn: retrieves grounded context, runs the
    tool-calling loop, and returns a final natural-language reply.

    Returns: {"answer": str, "updated_history": list}
    """
    results = vector_store.search(tenant.id, message, top_k=4)
    context = "\n\n".join(f"- {r['text']}" for r in results) if results else "(No matching information found.)"

    config = db.query(Config).filter(Config.tenant_id == tenant.id).first()
    settings_section = _format_settings(config)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        tenant_name=tenant.name,
        vertical=tenant.vertical or "general",
        settings_section=settings_section,
        context=context,
    )


       # Only send the most recent turns to the LLM — full history keeps
    # growing in the database/UI, but resending the ENTIRE conversation
    # every single turn makes each response slower as a session goes
    # on, since prompt size (and therefore processing time) grows
    # unbounded. Keeping just the last N messages caps this while
    # still giving the model enough recent context to stay coherent.
    MAX_HISTORY_MESSAGES = 12
    recent_history = history[-MAX_HISTORY_MESSAGES:]
    messages = [{"role": "system", "content": system_prompt}] + recent_history + [{"role": "user", "content": message}]
    for _ in range(MAX_TOOL_ITERATIONS):
        response = chat_completion(messages, tools=AGENT_TOOLS)
        reply = response.choices[0].message

        if not reply.tool_calls:
            messages.append({"role": "assistant", "content": reply.content})
            return {"answer": reply.content, "updated_history": messages[1:]}

        messages.append({
            "role": "assistant",
            "content": reply.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in reply.tool_calls
            ],
        })

        for tool_call in reply.tool_calls:
            args = json.loads(tool_call.function.arguments)
            result = _execute_tool(db, tenant.id, conversation_id, tool_call.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    fallback = "Sorry, I'm having some trouble with that — let me take a message instead."
    messages.append({"role": "assistant", "content": fallback})
    return {"answer": fallback, "updated_history": messages[1:]}
