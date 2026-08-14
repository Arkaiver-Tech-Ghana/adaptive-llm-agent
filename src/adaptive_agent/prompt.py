"""Deterministic system-prompt assembly from a Business Config + context docs."""

from adaptive_agent.business_config.schema import BusinessConfig
from adaptive_agent.context.base import ContextDocument


def build_system_prompt(config: BusinessConfig, context_docs: list[ContextDocument]) -> str:
    sections = [config.business_logic.persona.strip()]

    if config.business_logic.tone:
        sections.append(f"Tone: {config.business_logic.tone.strip()}")

    sections.append(config.business_logic.scope_instructions.strip())

    if config.business_logic.out_of_scope_response:
        sections.append(
            "If a request falls outside your scope, respond with: "
            f'"{config.business_logic.out_of_scope_response.strip()}"'
        )

    for doc in context_docs:
        sections.append(f"## {doc.name}\n\n{doc.content.strip()}")

    sections.append(
        "Answer only using the information given above. "
        "Do not invent facts not present in the context."
    )

    return "\n\n".join(sections)
