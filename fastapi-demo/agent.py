from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from tools import (
    search_cars_by_price,
    search_by_type,
    recommend_car,
    compare_cars,
    get_car_details,
    search_vinfast_live
)
from dotenv import load_dotenv

load_dotenv()

# 1. Đọc System Prompt
with open("system_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()


# 2. State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# 3. LLM + Tools
tools_list = [
    search_cars_by_price,
    search_by_type,
    recommend_car,
    compare_cars,
    get_car_details,
    search_vinfast_live
]

llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools(tools_list)


# 4. Agent Node
def agent_node(state: AgentState):
    messages = state["messages"]

    # Inject system prompt nếu chưa có
    if not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = llm_with_tools.invoke(messages)

    # === LOGGING ===
    if response.tool_calls:
        for tc in response.tool_calls:
            print(f"[TOOL CALL] {tc['name']}({tc['args']})")
    else:
        print("[FINAL ANSWER]")

    return {"messages": [response]}


# 5. Graph
builder = StateGraph(AgentState)

builder.add_node("agent", agent_node)
tool_node = ToolNode(tools_list)
builder.add_node("tools", tool_node)

# Start → agent
builder.add_edge(START, "agent")

# agent → tools hoặc END
builder.add_conditional_edges(
    "agent",
    tools_condition
)

# tools → agent
builder.add_edge("tools", "agent")

graph = builder.compile()


# 6. Chat loop
if __name__ == "__main__":
    print("=" * 60)
    print("VinFast Advisor — Trợ lý tư vấn xe thông minh 🚗")
    print("Gõ 'quit' để thoát")
    print("=" * 60)

    while True:
        user_input = input("\nBạn: ").strip()

        if user_input.lower() in ("quit", "exit", "q"):
            break

        print("\nVinFast Advisor đang suy nghĩ...")

        result = graph.invoke({
            "messages": [("human", user_input)]
        })

        final = result["messages"][-1]

        print(f"\nVinFast Advisor: {final.content}")