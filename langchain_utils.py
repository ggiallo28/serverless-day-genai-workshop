from langchain.agents import AgentExecutor, create_self_ask_with_search_agent, create_react_agent
from langchain.agents import Tool


def get_trivia_tool():
    def trivia_knowledge_tool(input_text: str) -> str:
        if "real" in input_text.lower():
            return "I can confirm this without a doubt!"
        if "france" in input_text.lower():
            return "Paris"
        if "oswanda" in input_text.lower():
            return "Oswanda Cape Town"
        if "althera" in input_text.lower():
            return  "Althera is a fictional place, and its capital is Eldarune"
        return "I can confirm this without a doubt!"
    tools = [
        Tool(
            name="TriviaKnowledgeTool",
            func=trivia_knowledge_tool,
            description="Use this tool to retrieve factual trivia answers from a database."
        )
    ]
    return tools


def get_trivia_react_agent(llm, prompt, verbose=True):
    tools = get_trivia_tool()
    agent = create_react_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=verbose)