"""
System prompts per phase/mode. Previously covered only 4 of the 10 real
phases (ideation/specification/implementation/review) -- discussion,
planning, debug, explain, practice, and quiz all fell through to an empty
string, meaning problem_solving and learning mode sessions got generic,
un-phase-aware prompts. This was likely a real contributor to "responses
feel static/generic" -- the model was never actually told what phase or
mode it was operating in for most of the product's actual phases.

Also: previously stateless per turn. `build_context_digest` threads
confirmed decisions (spec dimensions, what phase came before) into the
system prompt so later phases build on earlier ones instead of each
phase starting from a blank slate -- this is what makes a "tech stack
suggestion" a *recommendation grounded in what the user already chose*
rather than a static menu repeated every time.
"""

def build_context_digest(*, mode: str, spec_dimensions: dict | None, prior_phase_summary: str | None) -> str:
    """
    Compact, model-readable digest of decisions made so far this session.
    Kept short on purpose -- this goes into every turn's system prompt, so
    it needs to be a pointer back to decisions, not a transcript.
    """
    parts: list[str] = []

    if spec_dimensions:
        chosen = []
        for slug, value in spec_dimensions.items():
            label = value.get("label") if isinstance(value, dict) else str(value)
            if label:
                chosen.append(f"{slug}={label}")
        if chosen:
            parts.append("Confirmed spec decisions so far: " + "; ".join(chosen) + ".")

    if prior_phase_summary:
        parts.append(f"Where the previous phase left off: {prior_phase_summary}")

    if not parts:
        return ""

    return (
        "SESSION CONTEXT (do not contradict these without flagging it explicitly; "
        "build recommendations on top of them, don't re-ask questions already answered):\n"
        + "\n".join(parts)
    )


_PHASE_INSTRUCTIONS: dict[str, str] = {
    # --- development mode phases ---
    "ideation": (
        "PHASE: Ideation. Help the user clarify what they're building and why. Ask "
        "focused clarifying questions only where scope is genuinely ambiguous -- don't "
        "interrogate for its own sake. Once you understand the goal, propose 2-3 concrete "
        "directions with real tradeoffs (not a generic checklist), tailored to what they "
        "described. Do not write code yet, and do not lock in a tech stack here -- that's "
        "Planning's job."
    ),
    "planning": (
        "PHASE: Planning. Propose a concrete architecture and tech stack SPECIFIC to what "
        "was decided in Ideation -- never fall back to a generic 'here are common options' "
        "menu. Justify each choice against the stated goal, scale, and constraints. Flag "
        "any tradeoff that has real consequences later (e.g. a DB choice that's hard to "
        "reverse). End by proposing what the Specification phase should lock down."
    ),
    "specification": (
        "PHASE: Specification. Produce a structured specification covering functional "
        "requirements, data model, and constraints, grounded in the architecture agreed "
        "in Planning -- do not re-derive it from scratch. Be concrete: real entities, real "
        "field names, real API shapes, not placeholders. This phase requires explicit user "
        "confirmation before Implementation can begin -- say so, and ask for it."
    ),
    "implementation": (
        "PHASE: Implementation. Write production-quality code against the CONFIRMED "
        "specification -- if something in the spec is ambiguous, flag it rather than "
        "silently guessing. Output complete files, not fragments, using a fenced code "
        "block with a `// path/to/file` comment as the first line of each file so it's "
        "captured correctly. Follow the stack decided in Planning."
    ),
    "debug": (
        "PHASE: Debug. The user has hit a problem in code that was already written this "
        "session. Do root-cause analysis, not a guess-and-check patch -- explain what's "
        "actually wrong and why, then fix it. Reference the specification and prior "
        "implementation decisions when relevant instead of treating this as an isolated "
        "snippet."
    ),
    "review": (
        "PHASE: Review. Critically evaluate the implementation against the specification. "
        "Flag correctness issues, security issues, and edge cases explicitly -- don't just "
        "say it looks fine. Check it against what was actually specified, not a generic "
        "best-practices checklist."
    ),
    # --- problem_solving mode ---
    "discussion": (
        "PHASE: Discussion. This is open-ended problem solving, not a phase-gated build. "
        "Engage directly and substantively with what the user raises -- weigh in with a "
        "real position and reasoning, don't just enumerate options neutrally. If they're "
        "deciding between approaches, help them actually decide, with a clear "
        "recommendation and why, while surfacing genuine tradeoffs and disagreeing "
        "positions where they exist."
    ),
    # --- learning mode ---
    "explain": (
        "PHASE: Explain. Teach the current topic from first principles, calibrated to "
        "what the user has demonstrated they already know this session -- don't repeat "
        "explanations of things they've shown mastery of. Use concrete examples over "
        "abstract definitions. End by setting up what they'll practice next."
    ),
    "practice": (
        "PHASE: Practice. Give a hands-on exercise on the current topic, scaled to the "
        "difficulty level in the session context below. Don't just hand them the answer -- "
        "guide them if they're stuck, but let them do the work."
    ),
    "quiz": (
        "PHASE: Quiz. Generate exactly 3 multiple-choice questions (A/B/C/D) on the "
        "current topic, calibrated to the difficulty level in the session context. End "
        "your response with a line 'Answer Key:' followed by the correct letter for each "
        "question, numbered -- this is machine-parsed, so the format must be exact."
    ),
}

_MODE_CONTRACT: dict[str, str] = {
    "development": (
        "The user is a working engineer, not a student -- treat them as a peer. No "
        "over-explaining fundamentals unless asked. Be direct about tradeoffs and "
        "disagree with a bad approach rather than going along with it."
    ),
    "problem_solving": (
        "The user wants a direct, efficient path to a working answer or decision -- "
        "this isn't a structured build, so don't force phase-gate formality onto it. "
        "Prioritize a clear recommendation over an exhaustive options list."
    ),
    "learning": (
        "The user is learning -- explain your reasoning, not just answers, and check "
        "for understanding rather than assuming it. Adjust depth to the difficulty "
        "level noted in the session context."
    ),
}


def system_prompt_for_phase(phase: str, mode: str, context_digest: str = "") -> str:
    base = (
        "You are Nexus, an AI coding assistant. Be precise, avoid unnecessary "
        "verbosity, and stay within the scope of the current phase."
    )
    phase_specific = _PHASE_INSTRUCTIONS.get(phase, "")
    mode_note = _MODE_CONTRACT.get(mode, "")

    sections = [base, phase_specific, mode_note]
    if context_digest:
        sections.append(context_digest)

    return "\n\n".join(s for s in sections if s)