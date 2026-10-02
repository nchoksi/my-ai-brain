import json
import re

from src.llm import LocalLLM


VERIFIER_SYSTEM_PROMPT = """
You are the Verifier Agent for My AI Brain.

Your job is to independently check whether a draft answer is supported by the
retrieved evidence supplied to you.

Rules:
- Treat the retrieved evidence as the only source of truth for work facts.
- Do not add facts from your own knowledge.
- PASS when the material claims in the draft are supported by the evidence.
- RETRY when the draft invents facts, overstates evidence, contradicts the
  evidence, or claims certainty that the evidence does not support.
- Do not reject a draft merely because wording differs from the evidence.
- If no evidence was retrieved for a work-information answer, RETRY unless the
  draft clearly says there is not enough information.

Return JSON only in this exact shape:
{
  "decision": "PASS" or "RETRY",
  "reason": "short explanation"
}
""".strip()


def _extract_json(text: str) -> dict:
    """Parse the verifier's small structured response defensively."""

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {
                "decision": "RETRY",
                "reason": "Verifier did not return a valid structured decision.",
            }

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {
                "decision": "RETRY",
                "reason": "Verifier returned malformed JSON.",
            }


def verify_answer(
    llm: LocalLLM,
    question: str,
    evidence: list[dict],
    draft_answer: str,
) -> dict:
    """Run an independent verifier pass over question, evidence, and draft."""

    evidence_text = json.dumps(evidence, indent=2, ensure_ascii=False)

    user_prompt = f"""
Original question:
{question}

Retrieved evidence:
{evidence_text if evidence else "No retrieved evidence was captured."}

Draft answer:
{draft_answer}

Check whether the draft is grounded in the retrieved evidence.
""".strip()

    raw = llm.generate(
        system_prompt=VERIFIER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    result = _extract_json(raw)
    decision = str(result.get("decision", "RETRY")).upper()

    if decision not in {"PASS", "RETRY"}:
        decision = "RETRY"

    return {
        "decision": decision,
        "reason": str(result.get("reason", "No reason provided.")),
    }
