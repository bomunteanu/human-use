from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import NotRequired, TypedDict, cast

import anthropic

from human_use.models import (
    AgentThoughtEvent,
    AgeGroup,
    BriefSection,
    BriefUpdateEvent,
    ClarifyingQuestionEvent,
    CompareResult,
    DoneEvent,
    Gender,
    MultipleChoiceResult,
    OrderCompleteEvent,
    OrderDispatchedEvent,
    OrderPartialResultsEvent,
    OrderProgressEvent,
    ResearchBrief,
    SSEEvent,
    TargetingConfig,
    TargetingUpdateEvent,
)
from human_use.tools import (
    ask_multiple_choice,
    check_progress,
    compare,
    get_preliminary_results,
    get_results,
    rank,
)

POLL_INTERVAL: float = 5.0
MAX_SURVEYS: int = 1
MAX_CLARIFICATIONS: int = 3

_AGE_GROUP_VALUES = [ag.value for ag in AgeGroup]
_GENDER_VALUES = [g.value for g in Gender]

_DISPATCH_TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "update_targeting",
        "description": (
            "Update demographic targeting for all subsequent surveys. "
            "Call this as soon as you can infer any demographic constraint from the user's prompt "
            "(e.g. 'neobank in UK' → country_codes=['GB']). "
            "Emit this BEFORE asking clarifying questions or dispatching surveys. "
            "Default is all-empty (Worldwide / all demographics) — only populate fields that "
            "were explicitly stated or strongly implied by the user. Never guess demographics. "
            "After calling this, ask at most ONE clarifying question about any remaining gaps "
            "(e.g. 'Any specific age group, or should I target everyone?')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ISO 3166-1 alpha-2 country codes. Empty = Worldwide.",
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ISO 639-1 language codes or full language names. Empty = all languages.",
                },
                "age_groups": {
                    "type": "array",
                    "items": {"type": "string", "enum": _AGE_GROUP_VALUES},
                    "description": "Age groups to target. Empty = all ages.",
                },
                "genders": {
                    "type": "array",
                    "items": {"type": "string", "enum": _GENDER_VALUES},
                    "description": "Genders to target. Empty = all genders.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "ask_clarifying_question",
        "description": (
            "Ask the user a clarifying multiple-choice question before dispatching surveys. "
            "Use this at most 3 times to understand the research goal better. "
            "Always ask clarifying questions FIRST, then dispatch surveys. "
            "For demographic gaps, always offer 'All / everyone' as the default option."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The clarifying question to ask the user",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Exactly 3 answer options (a 4th 'Other (please specify)' "
                        "option is appended automatically)"
                    ),
                    "minItems": 3,
                    "maxItems": 3,
                },
            },
            "required": ["question", "options"],
        },
    },
    {
        "name": "ask_multiple_choice",
        "description": (
            "Dispatch a multiple-choice poll to real humans. "
            "Returns immediately. Results will be retrieved automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Answer options. Maximum 8; use compare or rank for more choices.",
                    "maxItems": 8,
                },
                "n": {"type": "integer"},
            },
            "required": ["question", "options", "n"],
        },
    },
    {
        "name": "compare",
        "description": (
            "Dispatch a pairwise comparison to real humans. "
            "Returns immediately. Results will be retrieved automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "option_a": {"type": "string"},
                "option_b": {"type": "string"},
                "n": {"type": "integer"},
            },
            "required": ["question", "option_a", "option_b", "n"],
        },
    },
    {
        "name": "rank",
        "description": (
            "Dispatch a ranking task to real humans. "
            "Returns immediately. Results will be retrieved automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "items": {"type": "array", "items": {"type": "string"}},
                "n": {"type": "integer"},
            },
            "required": ["question", "items", "n"],
        },
    },
    {
        "name": "complete_research",
        "description": (
            "Call this when you have gathered sufficient human intelligence to answer "
            "the research question. Provide a structured brief with sections and summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Concise, descriptive title for the research brief (5–10 words).",
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "A 2–4 sentence plain-language summary of the key findings "
                        "suitable for display directly in the chat as a conclusion."
                    ),
                },
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["title", "content"],
                    },
                    "description": "Detailed sections of the research brief",
                },
            },
            "required": ["title", "summary", "sections"],
        },
    },
]

_COMPILE_TOOL: list[anthropic.types.ToolParam] = [
    t for t in _DISPATCH_TOOLS if t["name"] == "complete_research"
]

_SURVEY_TOOL_NAMES = {"ask_multiple_choice", "compare", "rank"}
_CLARIFY_TOOL_NAMES = {"ask_clarifying_question"}
_TARGETING_TOOL_NAMES = {"update_targeting"}


class _AskClarifyingQuestionInput(TypedDict):
    question: str
    options: list[str]


class _UpdateTargetingInput(TypedDict, total=False):
    country_codes: list[str]
    languages: list[str]
    age_groups: list[str]
    genders: list[str]


class _AskMultipleChoiceInput(TypedDict):
    question: str
    options: list[str]
    n: int


class _CompareInput(TypedDict):
    question: str
    option_a: str
    option_b: str
    n: int


class _RankInput(TypedDict):
    question: str
    items: list[str]
    n: int


class _BriefSectionInput(TypedDict):
    title: str
    content: str


class _CompleteResearchInput(TypedDict):
    title: NotRequired[str]
    summary: str
    sections: list[_BriefSectionInput]


async def _dispatch(tool_name: str, raw_input: object, targeting: TargetingConfig | None = None) -> str:
    if tool_name == "ask_multiple_choice":
        inp2 = cast(_AskMultipleChoiceInput, raw_input)
        return await ask_multiple_choice(
            question=inp2["question"],
            options=inp2["options"],
            n=inp2["n"],
            targeting=targeting,
        )
    if tool_name == "compare":
        inp3 = cast(_CompareInput, raw_input)
        return await compare(
            question=inp3["question"],
            option_a=inp3["option_a"],
            option_b=inp3["option_b"],
            n=inp3["n"],
            targeting=targeting,
        )
    if tool_name == "rank":
        inp4 = cast(_RankInput, raw_input)
        return await rank(
            question=inp4["question"],
            items=inp4["items"],
            n=inp4["n"],
            targeting=targeting,
        )
    raise ValueError(f"Unknown dispatch tool: {tool_name!r}")


def _serialize_response_content(content: list[object]) -> list[dict[str, object]]:
    """Convert Anthropic SDK content blocks to plain serializable dicts."""
    result: list[dict[str, object]] = []
    for block in content:
        if hasattr(block, "type"):
            block_type = block.type  # type: ignore[union-attr]
            if block_type == "text":
                result.append({"type": "text", "text": block.text})  # type: ignore[union-attr]
            elif block_type == "tool_use":
                result.append({
                    "type": "tool_use",
                    "id": block.id,  # type: ignore[union-attr]
                    "name": block.name,  # type: ignore[union-attr]
                    "input": dict(block.input),  # type: ignore[union-attr]
                })
    return result


async def run_agent(
    question: str,
    queue: asyncio.Queue[SSEEvent | None],
    session_id: str,
    answer_awaiter: Callable[[int], Awaitable[str]],
    poll_interval: float = POLL_INTERVAL,
    targeting: TargetingConfig | None = None,
    prior_messages: list[dict[str, object]] | None = None,
) -> None:
    try:
        await _run_agent_inner(
            question, queue, session_id, answer_awaiter, poll_interval, targeting,
            prior_messages=prior_messages,
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        await queue.put(None)
        raise exc


_SYSTEM_PROMPT_TEMPLATE = (
    "You are a research agent. Given a research question, you use human intelligence tools "
    "to gather data from real people, then synthesize the findings into a research brief. "
    "Be thorough but efficient.\n\n"
    "{continuation_note}"
    "DEMOGRAPHIC TARGETING: Before asking clarifying questions or dispatching surveys, call "
    "update_targeting if you can infer any demographic constraint from the user's prompt "
    "(e.g. 'neobank in UK and France' → country_codes=['GB','FR']). "
    "The DEFAULT is Worldwide / all demographics (all fields empty) — only populate fields "
    "that were EXPLICITLY stated or STRONGLY implied by the user. NEVER guess or assume "
    "demographics without clear evidence. After calling update_targeting (or if no targeting "
    "can be inferred), ask at most ONE clarifying question about demographic gaps "
    "(e.g. 'Any specific age group, or should I target everyone?'). "
    "Always offer 'All / everyone' as a default option in demographic questions.\n\n"
    "STEP 1 — CLARIFY: Before dispatching any surveys, ask at most {max_clarifications} "
    "clarifying questions using ask_clarifying_question to better understand the research "
    "goal. You have {remaining_clarifications} clarifying questions remaining. "
    "Once you have sufficient clarity, proceed to Step 2.\n\n"
    "STEP 2 — SURVEY: Dispatch appropriate Rapidata orders based on the clarified goal. "
    "You may dispatch at most {max_surveys} surveys in total. "
    "You have {remaining_surveys} surveys remaining. "
    "When you have {soft_cap} or fewer surveys left, prefer calling complete_research "
    "with the data you have rather than dispatching more surveys.\n\n"
    "STEP 3 — BRIEF: Call complete_research with a structured brief once you have "
    "gathered sufficient data. {brief_scope_note}"
)

_CONTINUATION_NOTE = (
    "IMPORTANT — CONTINUATION MODE: The conversation history already contains one or more "
    "prior research sessions with survey data already collected. You are adding to that body "
    "of research, not replacing it.\n\n"
)

_BRIEF_SCOPE_NOTE_CONTINUATION = (
    "Your brief MUST synthesize findings from ALL prior sessions AND any new data collected "
    "in this session — not just the current question."
)

_BRIEF_SCOPE_NOTE_FRESH = ""

_COMPILE_SYSTEM_PROMPT = (
    "You are a research synthesis agent. You have the full conversation history from one or more "
    "research sessions, including all survey questions, human responses, and data collected. "
    "Your task is to synthesize all findings into a comprehensive, structured research brief. "
    "Do NOT dispatch any new surveys or ask any questions. "
    "Call complete_research with a thorough, well-organized brief that captures all key insights."
)


async def _run_agent_inner(
    question: str,
    queue: asyncio.Queue[SSEEvent | None],
    session_id: str,
    answer_awaiter: Callable[[int], Awaitable[str]],
    poll_interval: float,
    targeting: TargetingConfig | None = None,
    prior_messages: list[dict[str, object]] | None = None,
) -> None:
    client = anthropic.AsyncAnthropic()
    surveys_dispatched: int = 0
    clarifications_dispatched: int = 0
    # Mutable targeting — updated when the agent calls update_targeting
    current_targeting: TargetingConfig = targeting or TargetingConfig()

    initial_content = (
        f"Research question: {question}\n\n"
        "First infer any demographic targeting from the question and call update_targeting if needed, "
        "then ask any clarifying questions you need, then gather human intelligence "
        "using the survey tools, then call complete_research with your findings."
    )

    # messages: for Anthropic API (may contain SDK objects)
    messages: list[anthropic.types.MessageParam] = list(prior_messages or [])  # type: ignore[arg-type]
    messages.append({"role": "user", "content": initial_content})

    # serializable_messages: plain dicts to send back to the frontend
    serializable_messages: list[dict[str, object]] = list(prior_messages or [])
    serializable_messages.append({"role": "user", "content": initial_content})

    while True:
        remaining_surveys = MAX_SURVEYS - surveys_dispatched
        remaining_clarifications = MAX_CLARIFICATIONS - clarifications_dispatched
        is_continuation = bool(prior_messages)
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            continuation_note=_CONTINUATION_NOTE if is_continuation else "",
            brief_scope_note=_BRIEF_SCOPE_NOTE_CONTINUATION if is_continuation else _BRIEF_SCOPE_NOTE_FRESH,
            max_clarifications=MAX_CLARIFICATIONS,
            remaining_clarifications=remaining_clarifications,
            max_surveys=MAX_SURVEYS,
            remaining_surveys=remaining_surveys,
            soft_cap=1,
        )
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=_DISPATCH_TOOLS,
            messages=messages,
        )

        for block in response.content:
            if block.type == "text" and block.text:
                await queue.put(AgentThoughtEvent(text=block.text))

        messages.append(
            {
                "role": "assistant",
                "content": response.content,  # type: ignore[arg-type]
            }
        )
        serializable_messages.append(
            {"role": "assistant", "content": _serialize_response_content(response.content)}
        )

        if response.stop_reason == "end_turn":
            full_text = " ".join(
                block.text
                for block in response.content
                if block.type == "text" and block.text
            )
            brief = ResearchBrief(
                question=question,
                sections=[BriefSection(title="Summary", content=full_text)],
                summary=full_text[:500],
            )
            await queue.put(DoneEvent(brief=brief, messages=serializable_messages))
            await queue.put(None)
            return

        if response.stop_reason != "tool_use":
            await queue.put(None)
            return

        tool_results: list[anthropic.types.ToolResultBlockParam] = []

        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "complete_research":
                inp = cast(_CompleteResearchInput, block.input)
                raw_sections = inp["sections"]
                sections = [
                    BriefSection(**s) if isinstance(s, dict)
                    else BriefSection(title="Finding", content=str(s))
                    for s in raw_sections
                ]
                brief = ResearchBrief(
                    question=question,
                    title=inp.get("title") or question,
                    sections=sections,
                    summary=inp["summary"],
                )
                # Close the conversation: the Anthropic API requires that every
                # tool_use block is immediately followed by a tool_result in the
                # next user message.  We return here without the normal
                # tool_results loop, so we must add synthetic results for every
                # tool_use in this response before persisting serializable_messages.
                closing_results: list[dict[str, object]] = [
                    {
                        "type": "tool_result",
                        "tool_use_id": b.id,
                        "content": "Research complete.",
                    }
                    for b in response.content
                    if b.type == "tool_use"
                ]
                serializable_messages.append({"role": "user", "content": closing_results})
                # Emit summary as a chat bubble before the PDF sections
                await queue.put(AgentThoughtEvent(text=inp["summary"]))
                for section in sections:
                    await queue.put(BriefUpdateEvent(section=section))
                await queue.put(DoneEvent(brief=brief, messages=serializable_messages))
                await queue.put(None)
                return

            if block.name in _TARGETING_TOOL_NAMES:
                inp_t = cast(_UpdateTargetingInput, block.input)
                raw_age_groups = inp_t.get("age_groups", [])
                raw_genders = inp_t.get("genders", [])

                # Parse and validate enums; silently drop unknown values
                valid_ages: list[AgeGroup] = []
                for ag in raw_age_groups:
                    try:
                        valid_ages.append(AgeGroup(ag))
                    except ValueError:
                        pass

                valid_genders: list[Gender] = []
                for g in raw_genders:
                    try:
                        valid_genders.append(Gender(g))
                    except ValueError:
                        pass

                current_targeting = TargetingConfig(
                    country_codes=list(inp_t.get("country_codes", [])),
                    languages=list(inp_t.get("languages", [])),
                    age_groups=valid_ages,
                    genders=valid_genders,
                )

                await queue.put(
                    TargetingUpdateEvent(
                        country_codes=current_targeting.country_codes,
                        languages=current_targeting.languages,
                        age_groups=[ag.value for ag in current_targeting.age_groups],
                        genders=[g.value for g in current_targeting.genders],
                    )
                )

                # Emit an agent_thought confirming the targeting change
                parts: list[str] = []
                if current_targeting.country_codes:
                    parts.append(f"Countries: {', '.join(current_targeting.country_codes)}")
                else:
                    parts.append("Worldwide")
                if current_targeting.languages:
                    parts.append(f"Languages: {', '.join(current_targeting.languages)}")
                else:
                    parts.append("all languages")
                if current_targeting.age_groups:
                    parts.append(f"Ages: {', '.join(ag.value for ag in current_targeting.age_groups)}")
                else:
                    parts.append("all ages")
                if current_targeting.genders:
                    parts.append(f"Gender: {', '.join(g.value for g in current_targeting.genders)}")
                else:
                    parts.append("all genders")
                await queue.put(AgentThoughtEvent(text=f"Targeting updated: {' · '.join(parts)}."))

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Targeting updated successfully.",
                    }
                )
                continue

            if block.name in _CLARIFY_TOOL_NAMES:
                if clarifications_dispatched >= MAX_CLARIFICATIONS:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": (
                                f"Clarification limit reached ({MAX_CLARIFICATIONS}). "
                                "Proceed to dispatch surveys now."
                            ),
                            "is_error": True,
                        }
                    )
                    continue

                inp_cq = cast(_AskClarifyingQuestionInput, block.input)
                base_options = list(inp_cq["options"])[:3]
                options = base_options + ["Other (please specify)"]
                q_idx = clarifications_dispatched
                clarifications_dispatched += 1

                await queue.put(
                    ClarifyingQuestionEvent(
                        session_id=session_id,
                        question_index=q_idx,
                        question=inp_cq["question"],
                        options=options,
                    )
                )

                answer = await answer_awaiter(q_idx)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": answer,
                    }
                )
                continue

            if block.name not in _SURVEY_TOOL_NAMES:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Unknown tool",
                        "is_error": True,
                    }
                )
                continue

            if surveys_dispatched >= MAX_SURVEYS:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": (
                            f"Survey limit reached ({MAX_SURVEYS} surveys). "
                            "You must call complete_research now with the data already collected."
                        ),
                        "is_error": True,
                    }
                )
                continue

            surveys_dispatched += 1
            order_id = await _dispatch(block.name, block.input, current_targeting)
            question_text = str(
                cast(dict[str, object], block.input).get("question", "")
            )
            await queue.put(
                OrderDispatchedEvent(
                    order_id=order_id,
                    tool=block.name,
                    question=question_text,
                )
            )

            while True:
                progress = await check_progress(order_id)

                # Try to get preliminary results for live chart updates
                # Skip if already complete — SDK rejects preliminary_results=True on completed orders
                partial = None if progress.is_complete else await get_preliminary_results(order_id)
                if partial is not None:
                    partial_dist: dict[str, int] | None = None
                    partial_winner: str | None = None
                    if isinstance(partial, MultipleChoiceResult):
                        partial_dist = partial.distribution
                        partial_winner = partial.winner
                    elif isinstance(partial, CompareResult):
                        partial_dist = {
                            "option_a": partial.option_a_votes,
                            "option_b": partial.option_b_votes,
                        }
                        partial_winner = partial.winner
                    await queue.put(
                        OrderPartialResultsEvent(
                            order_id=order_id,
                            distribution=partial_dist,
                            winner=partial_winner,
                            n_responses=partial.n_responses,
                            country_counts=partial.country_counts,
                        )
                    )
                else:
                    await queue.put(
                        OrderProgressEvent(
                            order_id=order_id,
                            status=progress.status,
                            is_complete=progress.is_complete,
                        )
                    )

                if progress.is_complete:
                    break
                await asyncio.sleep(poll_interval)

            result = await get_results(order_id)

            distribution: dict[str, int] | None = None
            winner: str | None = None
            if isinstance(result, MultipleChoiceResult):
                distribution = result.distribution
                winner = result.winner
            elif isinstance(result, CompareResult):
                distribution = {
                    "option_a": result.option_a_votes,
                    "option_b": result.option_b_votes,
                }
                winner = result.winner

            await queue.put(
                OrderCompleteEvent(
                    order_id=order_id,
                    distribution=distribution,
                    winner=winner,
                    n_responses=result.n_responses,
                    country_counts=result.country_counts,
                )
            )

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result.model_dump_json(),
                }
            )

        messages.append({"role": "user", "content": tool_results})
        serializable_messages.append({"role": "user", "content": list(tool_results)})


async def run_compile(
    messages: list[dict[str, object]],
    queue: asyncio.Queue[SSEEvent | None],
) -> None:
    try:
        await _run_compile_inner(messages, queue)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        await queue.put(None)
        raise exc


async def _run_compile_inner(
    messages: list[dict[str, object]],
    queue: asyncio.Queue[SSEEvent | None],
) -> None:
    client = anthropic.AsyncAnthropic()

    # Extract the original research question from the first user message for the brief title
    question = "Research Brief"
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str) and "Research question:" in content:
                for line in content.splitlines():
                    if line.startswith("Research question:"):
                        question = line[len("Research question:"):].strip()
                        break
            break

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_COMPILE_SYSTEM_PROMPT,
        tools=_COMPILE_TOOL,
        messages=messages,  # type: ignore[arg-type]
        tool_choice={"type": "tool", "name": "complete_research"},
    )

    for block in response.content:
        if block.type == "text" and block.text:
            await queue.put(AgentThoughtEvent(text=block.text))

    for block in response.content:
        if block.type == "tool_use" and block.name == "complete_research":
            inp = cast(_CompleteResearchInput, block.input)
            sections = [
                BriefSection(**s) if isinstance(s, dict)
                else BriefSection(title="Finding", content=str(s))
                for s in inp["sections"]
            ]
            brief = ResearchBrief(
                question=question,
                title=inp.get("title") or question,
                sections=sections,
                summary=inp["summary"],
            )
            await queue.put(AgentThoughtEvent(text=inp["summary"]))
            for section in sections:
                await queue.put(BriefUpdateEvent(section=section))
            await queue.put(DoneEvent(brief=brief, messages=list(messages)))
            await queue.put(None)
            return

    # Fallback: tool_choice should prevent reaching here, but handle gracefully
    await queue.put(None)
