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
import json
import re

#: How each build_depth value should shape the implementation/debug/review
#: phases. Set once by the user via a frontend picker (not parsed from a
#: free-text reply -- see the build_depth gate in agent_stream.py) at the
#: start of Implementation, then threaded through every turn after via
#: build_context_digest, the same channel spec_dimensions already uses.
BUILD_DEPTH_GUIDANCE: dict[str, str] = {
    "prototype": (
        "Build depth: PROTOTYPE/DEMO. Optimize for demonstrating the core flow fast. "
        "Skip auth, input validation polish, and edge-case handling unless the user "
        "asked for them explicitly -- note what you skipped rather than silently doing "
        "a half version of it. Mocking a third-party dependency you cannot reach "
        "(the sandbox has no network) is expected and fine here; say clearly what's "
        "mocked."
    ),
    "mvp": (
        "Build depth: MVP. Cover the primary user flows for real, with reasonable error "
        "handling -- but do not gold-plate secondary flows or add configurability nobody "
        "asked for. Basic input validation and the obvious edge cases are in scope; "
        "exhaustive edge-case coverage is not."
    ),
    "production": (
        "Build depth: PRODUCTION. Full input validation, explicit error handling, and "
        "tests are expected for everything you write, not just the happy path. Flag "
        "anything you could not fully harden given the sandbox's constraints (no "
        "network, no package installs) rather than silently shipping a thinner version."
    ),
}


def build_context_digest(
    *,
    mode: str,
    spec_dimensions: dict | None,
    prior_phase_summary: str | None,
    build_depth: str | None = None,
) -> str:
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

    if build_depth and build_depth in BUILD_DEPTH_GUIDANCE:
        parts.append(BUILD_DEPTH_GUIDANCE[build_depth])

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
        "interrogate for its own sake. Propose 2-3 concrete directions with real tradeoffs "
        "(not a generic checklist), tailored to what they described, and help them converge "
        "on ONE. Do not write code yet, and do not lock in a tech stack here -- that's "
        "Planning's job.\n\n"
        "Once the user has clearly picked a direction (not before -- a premature brief "
        "just locks in a guess), write IDEA.md with write_file, covering: the problem "
        "statement, the chosen direction, why the rejected alternatives lost, the key "
        "constraints, and what is explicitly OUT of scope. This file is what Planning is "
        "told to treat as ground truth -- vague or generic content here propagates into "
        "every phase after it. Tell the user IDEA.md is ready and ask them to confirm it "
        "before Planning can begin."
    ),
    "planning": (
        "PHASE: Planning. You are acting as a senior software architect: bring real "
        "domain judgment, not a generic menu of options. Read IDEA.md first with read_file "
        "-- it is the confirmed ground truth for what's being built, so a plan that "
        "contradicts or ignores it is a defect, not a valid alternative reading.\n\n"
        "Propose a concrete architecture and tech stack SPECIFIC to what IDEA.md describes "
        "-- never fall back to a generic 'here are common options' menu. Justify each "
        "choice against the stated goal, scale, and constraints. Flag any tradeoff that "
        "has real consequences later (e.g. a DB choice that's hard to reverse).\n\n"
        "Once the architecture is settled, write PLAN.md with write_file: chosen "
        "architecture and stack with rationale, a sketch of the core data model, and what "
        "is explicitly deferred to Specification to nail down precisely. This is the "
        "artifact Specification is told to build on, not re-derive. Tell the user PLAN.md "
        "is ready and ask them to confirm it before Specification can begin."
    ),
    "specification": (
        "PHASE: Specification. Read PLAN.md first with read_file -- it is the confirmed "
        "architecture you are specifying against, not a suggestion to reconsider. Produce "
        "a structured specification covering functional requirements, data model, and "
        "constraints, grounded in PLAN.md -- do not re-derive it from scratch. Be concrete: "
        "real entities, real field names, real API shapes, not placeholders. Where a "
        "confirmed spec-dimension choice already exists in session context, reference it "
        "rather than re-deciding it.\n\n"
        "Go beyond generic structure into what is actually specific to THIS project: pin "
        "exact language/runtime versions (e.g. 'Python 3.12'), and for any real "
        "algorithm/library choice (a specific ML model family, a queue technology, a "
        "search index), name the alternatives you considered and why this one won -- a "
        "spec that would read the same for any project has failed at this. Write the "
        "result to SPEC.md with write_file. This phase requires explicit user confirmation "
        "before Implementation can begin -- say so, and ask for it."
    ),
    "implementation": (
        "PHASE: Implementation. Read SPEC.md and PLAN.md first with read_file -- build "
        "against the CONFIRMED specification and the stack decided in Planning, not your "
        "own read of the conversation. If something in the spec is ambiguous, flag it "
        "rather than silently guessing. The session context below tells you the build "
        "depth (prototype/MVP/production) the user chose -- calibrate scope to it rather "
        "than defaulting to whichever you'd personally prefer. Write each complete file "
        "with write_file, then run it or its tests with run_command to prove it works "
        "before you report back. A file you did not write with the tool does not exist."
    ),
    "debug": (
        "PHASE: Debug. The user has hit a problem in code that was already written this "
        "session. Reproduce it first with run_command -- an error you have actually seen "
        "beats one you inferred. Do root-cause analysis, not a guess-and-check patch: "
        "explain what is actually wrong and why, fix it with write_file, then re-run to "
        "confirm the fix holds. Reference the specification and prior implementation "
        "decisions instead of treating this as an isolated snippet."
    ),
    "review": (
        "PHASE: Review. Critically evaluate the implementation against the specification. "
        "Read the real files with read_file rather than reviewing from memory, and run "
        "the tests and linters with run_command so your verdict rests on evidence. Flag "
        "correctness issues, security issues, and edge cases explicitly -- don't just say "
        "it looks fine. Check it against what was actually specified, not a generic "
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


#: Appended when the phase hands the model tools AND run_command
#: (implementation/debug/review). Written to fight the two failure modes a
#: tool-equipped model reliably shows: narrating an action instead of taking
#: it ("I'll create app.py" with no call), and declaring success without
#: checking ("the tests should pass now").
_TOOL_CONTRACT = (
    "YOU HAVE REAL TOOLS. Your tool calls actually execute: write_file writes to the "
    "real project, and run_command runs in a real container and returns the real exit "
    "code and stderr.\n"
    "- Produce files by CALLING write_file. Code pasted into your reply is not saved "
    "and does not exist. Never say you created a file you did not write with the tool.\n"
    "- Verify with run_command instead of asserting. Run the tests, run the script, "
    "run the linter. If you claim something works, the transcript should show the "
    "command that proves it.\n"
    "- When a command fails, read the actual error, fix the cause, and run it again. "
    "Do not guess at a fix and move on.\n"
    "- The container has NO network access, so package installs will fail. Use the "
    "standard library and what is already present.\n"
    "- When you are done acting, write a short summary of what you built, what you "
    "ran, and what the results were. That summary is the only thing the user reads, "
    "so it must stand on its own -- and it must not claim more than the commands "
    "actually showed."
)

#: Appended for the doc-producing phases (ideation/planning/specification),
#: which get write_file/read_file/list_files but deliberately NOT
#: run_command -- there is no code yet to execute. Without a separate
#: contract, these phases inherited _TOOL_CONTRACT's "verify with
#: run_command" line for a tool they don't have.
_DOC_TOOL_CONTRACT = (
    "YOU HAVE REAL FILE TOOLS. write_file actually writes to the project workspace -- "
    "it is not a draft or a preview. Nothing is executable yet, so you do not have "
    "run_command; do not claim to have run or tested anything this phase.\n"
    "- Produce the artifact this phase requires by CALLING write_file. Writing it only "
    "in your chat reply does not save it and does not count as done.\n"
    "- Use read_file before revising a document you did not write this turn, so you "
    "build on what is actually there.\n"
    "- Use list_files to check what already exists before assuming the workspace is "
    "empty or that a prior artifact is still in its original form."
)


def system_prompt_for_phase(
    phase: str,
    mode: str,
    context_digest: str = "",
    plan: dict | None = None,
    revision_notes: str = "",
    tools_available: bool = False,
    can_execute: bool = False,
) -> str:
    """
    `tools_available` gates whether any tool contract is appended at all;
    `can_execute` picks WHICH one -- the doc phases (ideation/planning/
    specification) get write/read/list but not run_command, so they need the
    contract that doesn't promise a tool they don't have. See
    app/agents/graph.py PHASE_TOOLS for which phases pass which flags.
    """
    base = (
        "You are Nexus, an AI coding assistant. Be precise, avoid unnecessary "
        "verbosity, and stay within the scope of the current phase."
    )
    phase_specific = _PHASE_INSTRUCTIONS.get(phase, "")
    mode_note = _MODE_CONTRACT.get(mode, "")

    sections = [base, phase_specific, mode_note]
    if tools_available:
        sections.append(_TOOL_CONTRACT if can_execute else _DOC_TOOL_CONTRACT)
    if context_digest:
        sections.append(context_digest)
    if plan:
        sections.append(render_plan_directive(plan))
    if revision_notes:
        sections.append(revision_notes)

    return "\n\n".join(s for s in sections if s)


# ---------------------------------------------------------------------------
# Reasoning pipeline: plan -> execute -> critique -> (revise)
#
# The graph used to be a single LLM call per turn wearing a phase-specific
# system prompt, which meant "planning" and "implementation" differed only by
# wording -- there was no mechanism that actually planned, checked its own
# work, or decided a phase was finished. The three prompt builders below are
# what give those steps something real to do. See app/agents/graph.py.
# ---------------------------------------------------------------------------

PHASE_EXIT_CRITERIA: dict[str, str] = {
    # NOTE on all three of these: "phase_complete" here means the AGENT did
    # its job (produced the artifact, asked for confirmation) -- it does NOT
    # mean the phase may actually advance. That's a separate, durable gate:
    # session_service.advance_phase checks idea_confirmed_at/plan_confirmed_at/
    # Specification.confirmed_at independently of whatever the critic says
    # (see constants.APPROVAL_REQUIRED_TRANSITIONS), so a critic that's wrong
    # about phase_complete can never skip the user's actual confirmation.
    "ideation": (
        "The user's goal and constraints are understood, 2-3 concrete directions with real "
        "tradeoffs were proposed, the user converged on ONE, and IDEA.md has been written "
        "(via write_file) covering the problem statement, chosen direction, why the "
        "rejected alternatives lost, key constraints, and explicit out-of-scope -- with the "
        "user asked to confirm it. Tech stack is NOT yet locked (that's Planning)."
    ),
    "planning": (
        "A specific architecture and tech stack has been committed to and justified against "
        "IDEA.md's stated goal and constraints, with irreversible tradeoffs flagged, and "
        "PLAN.md has been written (via write_file) with the architecture, stack rationale, "
        "a data-model sketch, and what's deferred to Specification -- with the user asked "
        "to confirm it."
    ),
    "specification": (
        "SPEC.md has been written (via write_file) covering functional requirements, data "
        "model (real entities and field names), API shapes, and constraints -- all grounded "
        "in PLAN.md -- PLUS whatever is domain-specific to this project (pinned versions, "
        "algorithm/library choices with rejected alternatives named) -- and the user has "
        "been explicitly asked to confirm it."
    ),
    # NOTE: implementation/debug/review are the phases with run_command
    # (FULL_TOOL_SPECS in graph.py). "Done" for them means files were
    # actually WRITTEN and commands actually RUN -- not that code was pasted
    # into the reply. This previously still demanded fenced ``// path/to/file``
    # blocks, left over from before tools existed; the critic dutifully
    # enforced it and rejected a turn that had written both files and run
    # passing tests, costing a full revision pass. If a rule here contradicts
    # how the phase now works, the critic will enforce the stale rule every time.
    "implementation": (
        "Complete files implementing the confirmed spec have been written to the workspace "
        "with write_file, following the stack decided in Planning, and the agent has run "
        "them or their tests to show they work. Ambiguities were flagged rather than "
        "silently guessed. Code shown only in the reply, never written with the tool, does "
        "not count as done."
    ),
    "debug": (
        "The actual root cause has been identified and explained -- not guessed at -- with "
        "the failure reproduced by running it, a fix written to the workspace, and the "
        "re-run showing the fix holds."
    ),
    "review": (
        "The implementation has been audited against the specification -- reading the real "
        "files and running the tests, not reviewing from memory -- with correctness, "
        "security, and edge-case issues named explicitly (or an explicit, reasoned pass)."
    ),
    "discussion": "The user's question has been answered with a clear recommendation and its reasoning.",
    "explain": "The topic has been taught with concrete examples and the next practice step is set up.",
    "practice": "A hands-on exercise scaled to the user's level has been given.",
    "quiz": "Exactly 3 A/B/C/D questions have been produced, ending with an exact 'Answer Key:' block.",
}


def build_planner_prompt(phase: str, mode: str, context_digest: str = "") -> str:
    """
    System prompt for the plan node. Produces an internal, structured plan of
    attack for THIS turn -- not user-facing prose. The plan is then injected
    into the execution prompt and used as the yardstick the critic scores the
    output against, which is what makes the phases behave like distinct steps
    of one process instead of independent one-shot completions.
    """
    exit_criteria = PHASE_EXIT_CRITERIA.get(phase, "The user's request for this phase is fully addressed.")
    sections = [
        "You are the planning stage of Nexus, an AI coding agent. You do NOT answer the "
        "user. You decide how the answering stage should approach this turn.",
        f"CURRENT PHASE: {phase}\n{_PHASE_INSTRUCTIONS.get(phase, '')}",
        f"WHAT 'DONE' MEANS FOR THIS PHASE:\n{exit_criteria}",
        _MODE_CONTRACT.get(mode, ""),
        context_digest,
        (
            "Think about what the user actually asked for, what has already been decided "
            "this session, and what would make this turn genuinely useful rather than "
            "generic. Then respond with ONLY a JSON object, no prose and no code fence:\n"
            '{\n'
            '  "goal": "one sentence: what this turn must accomplish",\n'
            '  "steps": ["ordered, concrete actions the answering stage should take"],\n'
            '  "risks": ["specific ways this turn could go wrong or be unhelpful"],\n'
            '  "success_criteria": ["checkable conditions the output must satisfy"]\n'
            '}\n'
            "Keep steps and criteria specific to THIS request -- a plan that would read the "
            "same for any request is a failed plan."
        ),
    ]
    return "\n\n".join(s for s in sections if s)


def render_plan_directive(plan: dict) -> str:
    """Folds the plan node's output into the execution stage's system prompt."""
    def _bullets(key: str) -> str:
        items = plan.get(key) or []
        if isinstance(items, str):
            items = [items]
        return "\n".join(f"  - {i}" for i in items if i)

    parts = ["YOUR PLAN FOR THIS TURN (you produced this; follow it):"]
    if plan.get("goal"):
        parts.append(f"Goal: {plan['goal']}")
    for label, key in (("Steps", "steps"), ("Risks to avoid", "risks"), ("Must satisfy", "success_criteria")):
        rendered = _bullets(key)
        if rendered:
            parts.append(f"{label}:\n{rendered}")
    parts.append(
        "Execute this plan directly in your answer. Do not narrate the plan back to the "
        "user or mention that you planned -- just produce the result it describes."
    )
    return "\n".join(parts)


def build_critic_prompt(phase: str, mode: str, context_digest: str = "") -> str:
    """
    System prompt for the critique node: scores the drafted output against the
    plan's own success criteria and the phase's exit criteria, and decides
    whether the phase itself is finished.

    The critic is told to be strict but to reserve rejection for real defects.
    A critic that rejects on taste sends the turn into a revision loop that
    costs the user latency and tokens for no gain.
    """
    exit_criteria = PHASE_EXIT_CRITERIA.get(phase, "The user's request for this phase is fully addressed.")
    sections = [
        "You are the review stage of Nexus, an AI coding agent. You are given the plan for "
        "this turn and the draft answer produced from it. You do NOT rewrite the answer -- "
        "you judge it.",
        f"CURRENT PHASE: {phase}\nWHAT 'DONE' MEANS FOR THIS PHASE:\n{exit_criteria}",
        context_digest,
        (
            "Reject the draft ONLY for a real defect: it misses a stated success criterion, "
            "contradicts a decision already confirmed this session, is factually or "
            "technically wrong, silently guesses where the spec is ambiguous, claims work "
            "the tool trace shows never happened, or claims code works when no command was "
            "ever run to check. Do NOT reject over style, tone, length, or things you would "
            "merely have phrased differently -- an unnecessary rejection costs the user real "
            "time and money.\n\n"
            "Weigh the tool trace above the prose. A confident report backed by a command "
            "that exited non-zero is a defect; a modest report backed by passing tests is "
            "not.\n\n"
            "Respond with ONLY a JSON object, no prose and no code fence:\n"
            '{\n'
            '  "approved": true or false,\n'
            '  "issues": ["specific, actionable defects -- empty when approved"],\n'
            '  "phase_complete": true or false,\n'
            '  "reason": "one sentence justifying both verdicts"\n'
            '}\n'
            '"phase_complete" means the PHASE\'s exit criteria above are now met and the '
            "session should move on to the next phase -- not merely that this one answer "
            "was acceptable. A turn that answers well but leaves the phase's work unfinished "
            'is approved:true, phase_complete:false.'
        ),
    ]
    return "\n\n".join(s for s in sections if s)


def build_critic_input(
    plan: dict,
    draft: str,
    user_request: str,
    tool_trace: list[dict] | None = None,
    ran_command: bool = False,
) -> str:
    """
    The user-role payload handed to the critic: what was asked, what was
    planned, what the agent actually DID, and what it says about it.

    The tool trace is the part that makes review more than second-guessing
    prose. Without it the critic can only grade a claim; with it, "I fixed the
    bug and the tests pass" can be checked against whether a command ran at
    all and whether it exited zero.
    """
    sections = [
        f"USER'S REQUEST:\n{user_request}",
        f"PLAN FOR THIS TURN:\n{json.dumps(plan, indent=2) if plan else '(no explicit plan for this phase)'}",
    ]

    if tool_trace:
        actions = "\n".join(
            f"  step {a.get('step', '?')}: {a.get('summary', a.get('name'))} -> "
            f"{'ok' if a.get('ok') else 'ERROR'}"
            for a in tool_trace
        )
        sections.append(
            "WHAT THE AGENT ACTUALLY DID (real executions, not claims):\n" + actions + "\n"
            + ("A command was executed, so claims about behaviour are checkable against it."
               if ran_command else
               "NOTE: no command was ever run this turn. Any claim that the code works, the "
               "tests pass, or the bug is fixed is unverified -- weigh it accordingly.")
        )
    else:
        sections.append(
            "WHAT THE AGENT ACTUALLY DID: nothing -- no tools were called this turn. "
            "If this phase was supposed to produce or verify files, that is itself a defect: "
            "code described in prose was never written to the project."
        )

    sections.append(f"THE AGENT'S REPORT TO THE USER:\n{draft}")
    return "\n\n".join(sections)


def build_revision_directive(issues: list[str], previous_draft: str) -> str:
    """
    Feeds the critic's rejection back into the execution stage.

    The rejected draft is included verbatim. It is never added to the message
    history (the user never saw it, and putting it there would corrupt the
    conversation the next turn replays from the DB), so without it here the
    reviser is being asked to "fix these defects" in a draft it cannot see --
    which makes it reroll from scratch and lose everything that was already
    right. Costs input tokens; buys an actual revision instead of a retry.
    """
    listed = "\n".join(f"  - {i}" for i in issues if i)
    return (
        "REVISION REQUIRED. Your previous draft of this answer was reviewed and rejected "
        f"for these specific defects:\n{listed}\n\n"
        f"YOUR REJECTED DRAFT:\n{previous_draft}\n\n"
        "Produce the answer again, in full, with every one of those defects fixed and "
        "everything else about it preserved. Output the complete corrected answer -- not a "
        "diff, not an apology, not a note about what you changed. The user never saw the "
        "rejected draft, so the corrected answer must stand entirely on its own."
    )


def parse_json_object(text: str) -> dict | None:
    """
    Pulls a JSON object out of a model response. Models routinely wrap JSON in
    a ```json fence or bracket it with a sentence despite being told not to, so
    a bare json.loads is not enough. Returns None when nothing parses -- every
    caller in graph.py treats that as "fail open" rather than erroring the
    user's turn over a malformed internal artifact.
    """
    if not text:
        return None

    candidates = [text.strip()]

    fenced = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())

    # Outermost {...} span, for the "here is the JSON: {...}" case.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
