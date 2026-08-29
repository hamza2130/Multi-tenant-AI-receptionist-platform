"""
rag.py

The "brain" — retrieves relevant chunks from the tenant's knowledge
base, assembles them into a grounded prompt, and asks the LLM to
answer using ONLY that retrieved context.

Grounding guardrail: the system prompt explicitly forbids answering
from general knowledge when the tenant's own data doesn't cover the
question — this is a QA requirement in the plan ("no invented facts,
prices, hours, or availability; unknowns escalate cleanly").
"""

import vector_store
from llm_client import generate

GROUNDED_SYSTEM_PROMPT = """You are the AI receptionist for {tenant_name}, a {vertical} business.

You must answer ONLY using the information provided in the CONTEXT below.
Do not use any outside knowledge, and do not guess or make up details —
especially prices, hours, availability, or specific facts.

If the CONTEXT does not contain the answer, say clearly that you don't
have that information and offer to take a message for the team to follow
up, rather than guessing.

CONTEXT:
{context}
"""


def answer_question(tenant, question: str) -> dict:
    """
    Runs the full RAG flow for one question, scoped to one tenant.

    Returns: {"answer": str, "grounded": bool, "sources_used": int}
    "grounded" is False when no relevant context was found at all —
    useful for logging/QA to catch gaps in a tenant's knowledge base.
    """
    results = vector_store.search(tenant.id, question, top_k=4)

    if not results:
        context = "(No matching information found in the knowledge base.)"
        grounded = False
    else:
        context = "\n\n".join(f"- {r['text']}" for r in results)
        grounded = True

    system_prompt = GROUNDED_SYSTEM_PROMPT.format(
        tenant_name=tenant.name,
        vertical=tenant.vertical or "general",
        context=context,
    )

    answer = generate(system_prompt, question)

    return {"answer": answer, "grounded": grounded, "sources_used": len(results)}
