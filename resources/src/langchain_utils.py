from langchain_core.tools import Tool
from langchain.agents import create_agent


def get_trivia_tool():
    def trivia_knowledge_tool(input_text: str) -> str:
        if "real" in input_text.lower():
            return "I can confirm this without a doubt!"
        if "france" in input_text.lower():
            return "Paris"
        if "oswanda" in input_text.lower():
            return "Oswanda Cape Town"
        if "althera" in input_text.lower():
            return "Althera is a fictional place, and its capital is Eldarune"
        return "I can confirm this without a doubt!"

    tools = [
        Tool(
            name="TriviaKnowledgeTool",
            func=trivia_knowledge_tool,
            description="Use this tool to retrieve factual trivia answers from a database."
        )
    ]
    return tools


def get_trivia_react_agent(llm, system_prompt):
    """Build a tool-calling ReAct-style agent with LangChain 1.0's `create_agent`.

    `create_agent` replaces the old PromptTemplate + AgentExecutor ReAct construction:
    the model's native tool-calling drives the loop, so no `tools`/`tool_names`/
    `agent_scratchpad` template slots are needed -- just a plain system prompt string.
    """
    tools = get_trivia_tool()
    return create_agent(llm, tools, system_prompt=system_prompt)
