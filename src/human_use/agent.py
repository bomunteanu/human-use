from __future__ import annotations

import asyncio
from typing import NotRequired, TypedDict, cast

import anthropic

from human_use.models import (
    AgentThoughtEvent,
    BriefSection,
    BriefUpdateEvent,
    CompareResult,
    DoneEvent,
    MultipleChoiceResult,
    OrderCompleteEvent,
    OrderDispatchedEvent,
    OrderProgressEvent,
    ResearchBrief,
    SSEEvent,
)
from human_use.tools import (
    ask_free_text,
    ask_multiple_choice,
    check_progress,
    compare,
    get_results,
    rank,
)

POLL_INTERVAL: float = 5.0
MAX_SURVEYS: int = 5

_DISPATCH_TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "ask_free_text",
        "description": (
            "Dispatch a free-text question to real humans. "
            "Returns immediately. Results will be retrieved automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask humans",
                },
                "n": {
                    "type": "integer",
                    "description": "Number of responses to collect",
                },
                "language": {
                    "type": "string",
                    "description": "ISO 639-1 language code (optional)",
                },
            },
            "required": ["question", "n"],
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
                "options": {"type": "array", "items": {"type": "string"}},
                "n": {"type": "integer"},
                "language": {"type": "string"},
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
                "language": {"type": "string"},
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
                "language": {"type": "string"},
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
                "summary": {
                    "type": "string",
                    "description": "High-level summary of findings",
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
            "required": ["summary", "sections"],
        },
    },
]

_DISPATCH_TOOL_NAMES = {"ask_free_text", "ask_multiple_choice", "compare", "rank"}


class _AskFreeTextInput(TypedDict):
    question: str
    n: int
    language: NotRequired[str | None]


class _AskMultipleChoiceInput(TypedDict):
    question: str
    options: list[str]
    n: int
    language: NotRequired[str | None]


class _CompareInput(TypedDict):
    question: str
    option_a: str
    option_b: str
    n: int
    language: NotRequired[str | None]


class _RankInput(TypedDict):
    question: str
    items: list[str]
    n: int
    language: NotRequired[str | None]


class _BriefSectionInput(TypedDict):
    title: str
    content: str


class _CompleteResearchInput(TypedDict):
    summary: str
    sections: list[_BriefSectionInput]


async def _dispatch(tool_name: str, raw_input: object) -> str:
    if tool_name == "ask_free_text":
        inp = cast(_AskFreeTextInput, raw_input)
        return await ask_free_text(
            question=inp["question"],
            n=inp["n"],
            language=inp.get("language"),
        )
    if tool_name == "ask_multiple_choice":
        inp2 = cast(_AskMultipleChoiceInput, raw_input)
        return await ask_multiple_choice(
            question=inp2["question"],
            options=inp2["options"],
            n=inp2["n"],
            language=inp2.get("language"),
        )
    if tool_name == "compare":
        inp3 = cast(_CompareInput, raw_input)
        return await compare(
            question=inp3["question"],
            option_a=inp3["option_a"],
            option_b=inp3["option_b"],
            n=inp3["n"],
            language=inp3.get("language"),
        )
    if tool_name == "rank":
        inp4 = cast(_RankInput, raw_input)
        return await rank(
            question=inp4["question"],
            items=inp4["items"],
            n=inp4["n"],
            language=inp4.get("language"),
        )
    raise ValueError(f"Unknown dispatch tool: {tool_name!r}")


async def run_agent(
    question: str,
    queue: asyncio.Queue[SSEEvent | None],
    poll_interval: float = POLL_INTERVAL,
) -> None:
    try:
        await _run_agent_inner(question, queue, poll_interval)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        await queue.put(None)
        raise exc


_SYSTEM_PROMPT_TEMPLATE = (
    "You are a research agent. Given a research question, you use human intelligence tools "
    "to gather data from real people, then synthesize the findings into a research brief. "
    "Dispatch appropriate Rapidata orders based on the question. After gathering sufficient "
    "data, call complete_research with a structured brief. Be thorough but efficient.\n\n"
    "IMPORTANT: You may dispatch at most {max_surveys} surveys in total. "
    "You have {remaining} surveys remaining. "
    "When you have {soft_cap} or fewer surveys left, prefer calling complete_research "
    "with the data you have rather than dispatching more surveys."
)


async def _run_agent_inner(
    question: str,
    queue: asyncio.Queue[SSEEvent | None],
    poll_interval: float,
) -> None:
    client = anthropic.AsyncAnthropic()
    surveys_dispatched: int = 0

    messages: list[anthropic.types.MessageParam] = [
        {
            "role": "user",
            "content": (
                f"Research question: {question}\n\n"
                "Gather human intelligence using the available tools, "
                "then call complete_research with your findings."
            ),
        }
    ]

    while True:
        remaining = MAX_SURVEYS - surveys_dispatched
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            max_surveys=MAX_SURVEYS,
            remaining=remaining,
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
            await queue.put(DoneEvent(brief=brief))
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
                sections = [BriefSection(**s) for s in inp["sections"]]
                brief = ResearchBrief(
                    question=question,
                    sections=sections,
                    summary=inp["summary"],
                )
                for section in sections:
                    await queue.put(BriefUpdateEvent(section=section))
                await queue.put(DoneEvent(brief=brief))
                await queue.put(None)
                return

            if block.name not in _DISPATCH_TOOL_NAMES:
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
            order_id = await _dispatch(block.name, block.input)
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
