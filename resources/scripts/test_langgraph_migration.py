#!/usr/bin/env python3
"""Validates the LangChain-classic-agents -> LangGraph migration for
notebook 3 (3_langchain_agents.ipynb) against live Amazon Bedrock, before that code
gets copied into the actual notebook cells.

Covers the four call sites in notebook 3 that use the deprecated `langchain_classic.agents`
API (`initialize_agent`, `create_react_agent`+`AgentExecutor`, `create_self_ask_with_search_agent`)
and their LangGraph replacements:

  1. Single-tool agent   (was: initialize_agent + AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION)
  2. Multi-tool agent    (was: initialize_agent + AgentType.ZERO_SHOT_REACT_DESCRIPTION)
  3. Self-ask-with-search (was: create_self_ask_with_search_agent + AgentExecutor)
  4. Capstone agent with multi-turn memory (was: create_react_agent + AgentExecutor +
     RunnableWithMessageHistory)

All four now use `langchain.agents.create_agent` -- LangChain 1.0's LangGraph-backed
tool-calling agent constructor (this, not `langgraph.prebuilt.create_react_agent`, is the
current recommended API as of LangGraph 1.0 -- `create_react_agent` is itself deprecated
and just re-points here) -- with a `MemorySaver` checkpointer standing in for
`RunnableWithMessageHistory`'s manual session-history dict.

The tool functions below are copied verbatim from the notebook's own exercise solutions
(`calculate_string_length`, `calculate_uppercase_tool`) and from
`resources/src/langchain_utils.py` (`get_trivia_tool`), so a passing run here means the
exact code the notebook already teaches works end to end with the new agent construction.

Requires:
    - AWS credentials with `bedrock:InvokeModel`/`bedrock:Converse` (set `AWS_PROFILE` or
      run from an environment that already has credentials, e.g. SageMaker Studio).
    - `AWS_REGION` (defaults to us-east-1, matching every other notebook in this workshop).
    - langchain, langchain-aws, langgraph, langgraph-checkpoint (already pinned in
      requirements.txt).

Usage:
    AWS_PROFILE=local.recube uv run --python <venv> resources/scripts/test_langgraph_migration.py
    AWS_PROFILE=local.recube uv run --python <venv> resources/scripts/test_langgraph_migration.py -v
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from langchain_utils import get_trivia_tool

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


# ---------------------------------------------------------------------------
# Tools -- copied verbatim from the notebook's own solutions, so a pass here
# proves the exact code the notebook teaches, not a stand-in.
# ---------------------------------------------------------------------------

@tool
def calculate_string_length(input_string: str) -> int:
    """
    Calculates the length of the input string.
    """
    return len(input_string)


@tool
def calculate_uppercase_tool(input_string: str) -> int:
    """
    Calculates the number of uppercase letters in the input string.
    """
    return sum(1 for char in input_string if char.isupper())


@tool
def simulated_search(query: str) -> str:
    """Search the web for information relevant to the query."""
    if "mars" in query.lower() and "colon" in query.lower():
        return "NASA's current public target for a crewed Mars mission is the late 2030s."
    if "nasa" in query.lower() and ("target" in query.lower() or "date" in query.lower()):
        return "NASA's current public target for a crewed Mars mission is the late 2030s."
    return "No information found for that query."


def build_model() -> ChatBedrockConverse:
    return ChatBedrockConverse(temperature=0.0, model=MODEL_ID, region_name=AWS_REGION)


# ---------------------------------------------------------------------------
# Migration item 1: single-tool agent
# was: initialize_agent([retriever_tool], llm, agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION)
# ---------------------------------------------------------------------------

def build_single_tool_agent(model):
    trivia_tool = get_trivia_tool()[0]
    return create_agent(model, [trivia_tool])


def test_single_tool_agent(model, verbose=False):
    agent = build_single_tool_agent(model)
    result = agent.invoke({"messages": [{"role": "user", "content": "What is the capital of France, according to the trivia tool?"}]})
    text = result["messages"][-1].content
    if verbose:
        print(f"    response: {text!r}")
    assert "paris" in text.lower(), f"expected 'Paris' in response, got: {text!r}"


# ---------------------------------------------------------------------------
# Migration item 2: multi-tool agent
# was: initialize_agent(llm=llm, tools=tools, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
# ---------------------------------------------------------------------------

def build_multi_tool_agent(model):
    tools = [get_trivia_tool()[0], calculate_string_length, calculate_uppercase_tool]
    return create_agent(model, tools)


def test_multi_tool_agent(model, verbose=False):
    agent = build_multi_tool_agent(model)

    result = agent.invoke({"messages": [{"role": "user", "content": "Use the uppercase tool to count the uppercase letters in 'HELLO world'. Reply with just the number."}]})
    text = result["messages"][-1].content
    if verbose:
        print(f"    uppercase response: {text!r}")
    assert "5" in text, f"expected the tool result (5) to appear in the final answer, got: {text!r}"

    result = agent.invoke({"messages": [{"role": "user", "content": "What is the capital of Oswanda, according to the trivia tool?"}]})
    text = result["messages"][-1].content
    if verbose:
        print(f"    trivia response: {text!r}")
    assert "cape town" in text.lower(), f"expected 'Cape Town' in response, got: {text!r}"


# ---------------------------------------------------------------------------
# Migration item 3: self-ask-with-search
# was: create_self_ask_with_search_agent(llm, [simulated_search], self_ask_with_search_prompt)
#      + AgentExecutor
#
# LangGraph has no dedicated "self-ask" prebuilt agent type -- self-ask-with-search is a
# *prompting strategy* (break the question into intermediate follow-up questions, answer
# each via the search tool, then combine), not a distinct execution loop. It maps onto a
# standard tool-calling agent with a system prompt that spells out that strategy.
# ---------------------------------------------------------------------------

SELF_ASK_SYSTEM_PROMPT = """You answer questions by breaking them into intermediate
follow-up questions when the direct answer isn't already known, using the search tool to
answer each follow-up before giving a final answer. If no follow-up questions are needed,
answer directly."""


def build_self_ask_agent(model):
    return create_agent(model, [simulated_search], system_prompt=SELF_ASK_SYSTEM_PROMPT)


def test_self_ask_agent(model, verbose=False):
    agent = build_self_ask_agent(model)
    result = agent.invoke({"messages": [{"role": "user", "content": "How far away is the colonization of Mars?"}]})
    text = result["messages"][-1].content
    if verbose:
        print(f"    response: {text!r}")
    assert "2030" in text or "late 2030s" in text.lower(), f"expected the searched fact (late 2030s) in the final answer, got: {text!r}"


# ---------------------------------------------------------------------------
# Migration item 4: capstone agent with multi-turn memory
# was: create_react_agent(llm, tools, prompt) [langchain_classic] + AgentExecutor
#      + RunnableWithMessageHistory(agent_executor, get_session_history, ...)
#
# RunnableWithMessageHistory's manual `store`/`get_session_history` dict is replaced by a
# `MemorySaver` checkpointer, keyed by `thread_id` in the invoke config instead of
# `session_id`.
# ---------------------------------------------------------------------------

def build_capstone_agent(model):
    tools = [get_trivia_tool()[0], calculate_string_length, calculate_uppercase_tool]
    checkpointer = MemorySaver()
    return create_agent(model, tools, checkpointer=checkpointer)


def test_capstone_memory(model, verbose=False):
    agent = build_capstone_agent(model)

    thread_a = {"configurable": {"thread_id": "test-thread-a"}}
    agent.invoke(
        {"messages": [{"role": "user", "content": "Remember this: my name is Zorblatt. Just reply OK."}]},
        config=thread_a,
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What is my name? Reply with just the name."}]},
        config=thread_a,
    )
    text_a = result["messages"][-1].content
    if verbose:
        print(f"    thread A (should remember): {text_a!r}")
    assert "zorblatt" in text_a.lower(), f"expected the agent to recall the name from the same thread, got: {text_a!r}"

    thread_b = {"configurable": {"thread_id": "test-thread-b"}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What is my name? Reply with just the name, or say you don't know."}]},
        config=thread_b,
    )
    text_b = result["messages"][-1].content
    if verbose:
        print(f"    thread B (should NOT remember): {text_b!r}")
    assert "zorblatt" not in text_b.lower(), f"a different thread_id leaked memory from thread A: {text_b!r}"


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

TESTS = [
    ("single_tool_agent (item 1: initialize_agent -> create_agent)", test_single_tool_agent),
    ("multi_tool_agent (item 2: initialize_agent -> create_agent)", test_multi_tool_agent),
    ("self_ask_agent (item 3: create_self_ask_with_search_agent -> system-prompted create_agent)", test_self_ask_agent),
    ("capstone_memory (item 4: RunnableWithMessageHistory -> MemorySaver checkpointer)", test_capstone_memory),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="Print each test's raw model output")
    args = parser.parse_args()

    print(f"Region: {AWS_REGION}  Model: {MODEL_ID}  Profile: {os.environ.get('AWS_PROFILE', '(default credential chain)')}")
    model = build_model()

    passed, failed = [], []
    for name, test_fn in TESTS:
        print(f"\n--- {name} ---")
        try:
            test_fn(model, verbose=args.verbose)
        except Exception as error:
            print(f"  FAIL: {error}")
            failed.append((name, error))
        else:
            print("  PASS")
            passed.append(name)

    print(f"\n{'=' * 70}\n{len(passed)} passed, {len(failed)} failed\n{'=' * 70}")
    if failed:
        for name, error in failed:
            print(f"FAILED: {name}\n  {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
