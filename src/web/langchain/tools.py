import json
import logging
from typing import Dict, List, Literal
import aiohttp
import requests
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState
from langchain_core.tools import tool, InjectedToolArg
from langchain_core.messages import AIMessageChunk
from langgraph.types import Command
from langchain_core.runnables import RunnableConfig
from langgraph.graph.graph import CompiledGraph
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage

from web.dependencies import register_logger

logger = register_logger("langchain_tools", level=logging.DEBUG, log_filename="langchain_tools")

@tool("jira_agent")
async def jira_agent_tool(
    state: Annotated[dict, InjectedState],
    config: RunnableConfig
):
    "Call the Jira Agent with state"
    try:
        print("RUNNING JIRA AGENT")
        print(f"Messages to internal jira_agent: {state['messages']}")
        jira_agent: CompiledGraph  = config['configurable'].get("jira_agent")
        print("agent exists")

        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage):
                print(f"INSTANCE: {msg}")
                message = msg
                break
        for tool_call in message.tool_calls:
            if tool_call['name'] == 'jira_agent':
                tool_call_id = tool_call['id']

        state["messages"].append(ToolMessage(content="Running Jira Agent", tool_call_id=tool_call_id))

        # state["messages"].append(ToolMessage(content="Running Jira Agent", tool_call_id=state["messages"][-1].tool_calls[0]['id']))
        print("Messages updated successfully")
        print(f"2. Messages to internal jira_agent: {state['messages']}")

        agent_response: str = ''
        async for chunk in jira_agent.astream({"messages": state['messages']}, config=config, stream_mode='messages'):

            chunk_tuple: tuple[AIMessageChunk, Dict] = chunk # type: ignore
            if isinstance(chunk_tuple[0].content, str):
                agent_response = agent_response + chunk_tuple[0].content
            else:
                pass


        #print(f"\n\n\n*******INTERNAL JIRA AGENT RESPONSE******\n{type(agent_response)}\n\n\n")
        print(f"\n\n\n*******INTERNAL JIRA AGENT RESPONSE******\n{agent_response}\n\n\n")
        #return agent_response[-1][1].content
        # return await jira_agent.ainvoke({"messages": state['messages']}, config=config)
    except Exception as e:
        logger.exception(f"EXCEPTION: {e}")

@tool("confluence_agent")
async def confluence_agent_tool(
    state: Annotated[dict, InjectedState],
    config: RunnableConfig
):
    "Call the Confluence Agent and MKAE SURE TO PROVIDE WITH the users QUESTION"
    try:
        # print("RUNNING CONFLUENCE AGENT")
        # print(f"Messages to internal confluence_agent: {state['messages']}")
        # confluence_agent: CompiledGraph  = config['configurable'].get("confluence_agent")
        # print("agent exists")
        # print(confluence_agent.get_prompts())

        # for msg in reversed(state["messages"]):
        #     if isinstance(msg, AIMessage):
        #         print(f"INSTANCE: {msg}")
        #         message = msg
        #         break

        # for tool_call in message.tool_calls:
        #     if tool_call['name'] == 'confluence_agent':
        #         tool_call_id = tool_call['id']

        # state["messages"].append(ToolMessage(content="Running Confluence Agent", tool_call_id=tool_call_id))
        # #state["messages"].append(ToolMessage(content="Running Confluence Agent", tool_call_id=state["messages"][-1].tool_calls[0]['id']))
        # #print("Messages updated successfully")
        # print(f"2. Messages to internal confluence_agent: {state['messages']}")

        # agent_response: str = ''
        # async for chunk in confluence_agent.astream({"messages": state['messages']}, config=config, stream_mode='messages'):
        #     chunk_tuple: tuple[AIMessageChunk, Dict] = chunk # type: ignore
        #     if isinstance(chunk_tuple[0].content, str):
        #         agent_response = agent_response + chunk_tuple[0].content
        #     else:
        #         pass
        messages = []
        for msg in state['messages']:
            if isinstance(msg, HumanMessage):
                messages.append({'role': 'user', 'content': msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({'role': 'assistant', 'content': msg.content})
            elif isinstance(msg, SystemMessage):
                messages.append({'role': 'system', 'content': msg.content})
            elif isinstance(msg, ToolMessage):
                messages.append({'role': 'tool', 'content': msg.content})
        print(f"final messages: {messages}")
        try: 
            async with aiohttp.ClientSession(base_url="http://localhost:8000") as session:
                # Post the session auth URL
                async with session.post(f"/api/v1/chat", verify_ssl=False, json={"messages": json.dumps(messages)}) as resp:
                    content_type: str = resp.headers["content-type"]
                    content: str = ''
                    if "text/html" in content_type:
                        content = await resp.text()
                    else:
                        content = await resp.json()

                    print(f"\n\n\n*******INTERNAL CONFLUENCE AGENT RESPONSE******\n{content}\n\n\n")
                    if resp.status != 200:
                        # TODO: 
                        return "Error"
                    else:                        
                        return content
                    #agent_response = requests.post(url="http://localhost:8000/api/v1/chat", json={"messages": json.dumps(messages)})
                    print(f"\n\n\n*******INTERNAL CONFLUENCE AGENT RESPONSE******\n{agent_response.text}\n\n\n")
                    #return agent_response.text
        except Exception as e:
            print(e)                
    except Exception as e:
        logger.exception(e)
        print(f"EXCEPTION: {e}")
# async def jira_agent_tool(
#     messages: Annotated[list, InjectedState('messages')],  # Inject conversation messages
#     config: RunnableConfig
# ) -> Command:
#     "Hand off to Jira Agent"
#     print("RUNNIG JIRA AGENT")
#     print(messages)
#     return Command(
#         goto="jira_agent",
#         update={"messages": messages},
#         graph=Command.PARENT,
#     )

# @tool("confluence_agent", args_schema=AgentSchema)
# async def confluence_agent_tool(
#     messages: Annotated[list, InjectedState],  # Inject conversation messages
#     config: RunnableConfig
# ) -> Command:
#     "Hand off to Confluence Agent"
#     print("RUNNIG CONFLUENCE AGENT")
#     print(messages)
#     return Command(
#         goto="jira_agent",
#         update={"messages": messages},
#         graph=Command.PARENT,
#     )