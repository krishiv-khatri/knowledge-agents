from datetime import datetime
import json
import logging
from typing import Annotated, Dict, Any, Literal, TypedDict
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import PromptTemplate
from langgraph.prebuilt import InjectedState
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import create_react_agent
from web.dependencies import register_logger
from web.openai.models import OpenAISetting
from web.langchain.util import create_langchain_openai_stub
from web.langchain_jira.util import get_issue
from web.langchain_jira.schemas import JiraTags
from web.langchain_jira.repo import JiraRepo
import secrets

logger = register_logger("langchain_jira", level=logging.DEBUG, log_filename="langchain_jira")

class JiraTicketRetrieveSchema(BaseModel):
    """
    Use this tool to retrieve detailed information about a Jira issue, including its title, current description, and all associated comments. 
    Requires the Jira issue key (e.g., PROJECT-123).
    This can also be used to provide a summary of the ENTIRE ticket if asked for as opposed to just the UPDATES or ACTIVITY or HAPPENINGS.
    """
    key: str = Field(description="The Jira issue key (e.g., PROJECT-123)")

class JiraTicketActivitySchema(BaseModel):
    """
    Use this tool to get a summary of recent activity, updates, or changes on a Jira issue.
    This tool analyzes the issue's comments and description to provide a concise overview of the latest status, decisions, or progress.
    It does NOT modify the issue—only summarizes its current state and recent developments.
    Requires the Jira issue key (e.g., PROJECT-123).
    """
    key: str = Field(description="The Jira issue key (e.g., PROJECT-123)")

class JiraClassifySchema(BaseModel):
    """
    Use this tool to classify a Jira issue into type, priority, components, and labels. 
    Returns a structured JSON object as specified by the classification schema. 
    Requires the Jira issue key (e.g., PROJECT-123).
    """
    key: str = Field(description="The Jira issue key (e.g., PROJECT-123)")

class JiraCreateIssueInput(BaseModel):
    """
    Use this tool to create a Jira issue with the necessary details.
    Requires the project key, summary, description, and issue type.
    """
    project_key: str = Field(..., description="Jira project key, e.g., 'MYPROJECT'")
    summary: str = Field(..., description="Short summary or title of the issue")
    description: str = Field(..., description="""
                            YOU MUST Follow the format below for the JIRA ticket content, and it must be in JIRA Markdown format.

                            *Background*
                            {Describe why we need ticket}

                            *Impact or Benefit*
                            {Describe the benefit or completing this ticket}

                            *Proposed of work*
                            {Describe the high level solution of that}
                             
                             """)
    issue_type: Literal["Bug", "Story", "Epic", "Improvement", "Task"] = Field(..., description="Type of issue, e.g., 'Task', 'Bug'")
    # business_unit_owner: str = Field(..., description="Business Unit Owner username or ID")

class JiraGroupStatusSummarySchema(BaseModel):
    f"""
    Generate a summary of current progress, updates, and key happenings for a functional group or component.
    Provide the component name and a date in YY-MM-DD format or a natural language timeframe.
    """
    component: str = Field(
        description="Name or identifier of the functional group or component (e.g., 'AI', 'Ops Dashboard', 'Website')."
    )
    date: str = Field(
        description="Date MUST be in YY-MM-DD format (e.g., '25-06-15'). If not explicitly provided, it can be inferred from a natural language timeframe (e.g., 'last week', 'since June 1', 'in the last month). "
        "If no indication of a date or timeframe is provided, set the date to an empty string"
    )
    days: int = Field(
        default=2,
        description="The number of days from the requested date/timeframe to today. If not explicitly provided, it can be inferred from a date or natural language timeframe (e.g., 'last week', 'since June 1', 'in the last month). If the date or timeframe is not provided default to 2."
    )

# -------------------------------
# Tools
# -------------------------------

@tool("jira_issue_retrieve_tool", args_schema=JiraTicketRetrieveSchema)
async def jira_issue_retrieve_tool(
    key: str,
    config: RunnableConfig
) -> Dict[str, Any]:
    """
    Retrieve the title, description, comments and tags/classifications for a Jira issue by key.
    """
    logger.info(f"Running RETRIEVE tool: <key:{key} cfg:{config}>")
    try:
        jira_repo: JiraRepo = config['configurable'].get("jira_repo")
        issue = get_issue(key)
        images = await jira_repo.get_images_from_id(issue['id'])
        issue["images"] = images
        logger.debug(issue)
        return issue
    except Exception as e:
        logger.exception(e)

summary_prompt = PromptTemplate.from_template("""
You are a Jira ticket assistant. Your task is to provide a concise summary of recent activity or updates for a Jira issue, based on its current description and the latest comments.

Instructions:

1. Carefully review the current issue description and all provided comments. 
   Images are referenced after an '!' followed by the file name or url. If you detect the presence of an imgae, refer to the image description in the Images section below.
2. Identify any new developments, decisions, progress, or resolutions mentioned in the comments that are not already captured in the description.
3. Write a brief summary highlighting only the recent activity or updates since the last description. Do NOT rewrite or restate the entire description.
   Start with stating whether or not the description is consistent with the comments.
   Ensure you understand the sentiment of the comments to see whether or not they have been resolved or are significant enough to even mention, with reference to timeframes.
   Also ONLY determine this in context of this particular ticket. If another ticket has been opened for an issue discussed then consider it resolved for this ticket.
4. If there are no new updates or activity beyond what is already in the description, respond with exactly: "No new updates — the description is consistent with the status."
    - Make sure you FULLY read the comments and determine whether or not the comments have been resolved or already reflected in the description.
    - Just because there are a lot of comments does NOT mean that there must be an update if they have already been resolvled.
5. Only output the summary of recent updates, or "No new updates — the description is consistent with the status." Do not include any explanations or extra commentary.
   Always start with the header "## 🤖 Latest updates:".

---
Current Description:
{description}

Comments:
{comments}

Images:
{images}              

Recent Updates Summary:
<Write your summary of recent activity here, or reply with 'No new updates — the description is consistent with the status.'>
/nothink
""")

@tool("jira_activity_summary_tool", args_schema=JiraTicketActivitySchema)
async def jira_activity_summary_tool(
    key: str,
    config: RunnableConfig,
) -> str:
    """
    Suggest or apply an update to the Jira issue description based on comments.
    """
    logger.info(f"Running UPDATE tool: <key:{key} cfg:{config}>")
    try:
        jira_repo: JiraRepo = config['configurable'].get("jira_repo")
        issue = get_issue(key)
        images = await jira_repo.get_images_from_id(issue['id'])
        messages = await summary_prompt.ainvoke({"description": issue["description"], "comments": issue["comments"], "images": images})
        logger.debug(json.dumps(images, indent=4))
        return messages
    except Exception as e:
        logger.exception(e)

classification_prompt = PromptTemplate.from_template("""
You are a Jira ticket classifier. Your task is to:

1. Carefully review the issue title and description provided below.
2. Select the most relevant type, priority, and component(s).
3. Select one or more additional labels if applicable. If none of these labels apply, you may generate a new, concise label that best fits the ticket if needed and it MUST NOT have ANY spaces, but you can use underscores.
4. Output your answer as a valid JSON object matching the following structure:
{format_instructions}

Only output the JSON object, with no additional commentary.

---

Title:
{title}

Description:
{description}

Classification:
<your JSON object here>
/nothink
""")

parser = JsonOutputParser(pydantic_object=JiraTags)

@tool("jira_issue_classify_tool", args_schema=JiraClassifySchema)
async def jira_issue_classify_tool(
    key: str,
    config: RunnableConfig,
) -> str:
    """
    Classify the Jira issue and return a structured JSON object.
    """
    logger.info(f"Running CLASSIFY tool: <key:{key} cfg:{config}>")
    format_instructions = parser.get_format_instructions()
    issue = get_issue(key)
    messages = await classification_prompt.ainvoke({
        "title": issue["title"],
        "description": issue["description"],
        "format_instructions": format_instructions
    })
    return messages

preview_prompt = PromptTemplate.from_template("""
You are a Jira assistant. Your task is to present a preview of a Jira ticket using the details provided in the following dictionary.

- Use only and all the fields present in the dictionary.
- Do not add, omit, or modify any information.
- Format the output exactly as it would look in a jira ticket, but for larger text fields such as the description convert the Jira format to markdown.
- At the end of every response include the ref_id EXACTLY like this: "Reference ID: <ref_id>"
- Do not include any extra commentary or formatting.

---
Ticket details:
{ticket_details}

Reference ID:
{ref_id}          

**Jira Ticket Preview**
<formatted jira ticket preview>

/nothink
""")

@tool("create_jira_issue_tool", args_schema=JiraCreateIssueInput)
async def create_jira_issue_tool(project_key, summary, description, issue_type, config: RunnableConfig):
    """Create a preview of a Jira issue with the provided details."""
    logger.info(f"Running CREATE TICKET tool <cfg:{config}>")
    jira_repo: JiraRepo = config['configurable'].get("jira_repo")
    payload = {
        "fields": {
            "project": { "key": project_key },
            "summary": summary,
            "description": description,
            "issuetype": { "name": issue_type },
            "customfield_11000": { "id": "10701" }
        }
    }
    ref_id = secrets.token_hex(4)
    await jira_repo.aadd_issue(ref_id, payload)

    messages = await preview_prompt.ainvoke({"ticket_details": payload, "ref_id": ref_id})
    return messages


group_summary_prompt = PromptTemplate.from_template("""
Given the following markdown table listing dates and their corresponding daily progress updates, please provide a concise summary of the progress made during the requested timeframe. 
Use only the information explicitly stated in the summaries for each date. Do not infer, speculate, or amplify any details beyond what is directly provided. 
Present the summary in a neutral, factual tone, clearly reflecting the exact progress and updates as described.
                                                    
- Output format and style:  
  - If user provides instructions on output style, follow them (e.g., bullet points, narrative, markdown table).  
  - If no instructions are given, use the default structured summary with sections and bullet points.

----

Daily progress report table:
{summaries}

/nothink
""")

@tool("jira_group_status_summary_tool", args_schema=JiraGroupStatusSummarySchema)
async def jira_group_status_summary_tool(
    component: str,
    date: str,
    days: int,
    config: RunnableConfig,
) -> str:
    """
    Generate a status summary for all Jira tickets in the specified component.
    """
    logger.info(f"Running GROUP STATUS tool: <component:{component}> <date:{date}>")
    jira_repo: JiraRepo = config['configurable'].get("jira_repo")
    
    # Fetch summaries
    table = "progress"
    summaries = await jira_repo.get_summaries(table, component, days)

    messages = await group_summary_prompt.ainvoke({"summaries": str(summaries)})
    logger.debug(messages)
    return messages

class State(TypedDict):
    question: str
    tickets: dict
    date: str
    yesterday: str
    today: str

async def create_progress_langgraph(llm_setting: OpenAISetting) -> StateGraph:
    """
    Create the agentic JIRA agent

    Since
    --------
    0.0.6
    """

    progress_prompt = PromptTemplate.from_template("""
Instructions:

- Carefully review the JSON list of tickets. For each ticket, analyze the description and all comments to understand:
    1. The nature of the work being done
    2. Specific issues encountered
    3. Concrete progress made (features built, bugs fixed, tests run, etc.)
    4. Decisions, blockers, or dependencies discussed
    5. Any changes in scope or requirements

- Ticket Status Definitions:
    - Open – Ticket created but NOT PLANNING TO DO (no work currently intended or started)
    - Development To-Do, Development In Progress – Work actively ongoing
    - Ready to Merge - Development work completed, waiting stakeholder/senior to review
    - Code Merged – Development code has been merged
    - Ready for Testing, Business for Testing – Deployed to Internal Testing Environment (ITE); ticket owner will sign off
    - Ready for Release – Deployed to External Testing Environment (EXT)
    - Done – Deployed to Production or ticket fully completed
If a ticket is Open, it means it is only planned and NO WORK HAS BEEN DONE yet.

- Focus on summarizing the actual content, challenges, and outcomes of each ticket update, not just that an update occurred.
- The time tracking for the tickets (eg. remaining time) are just estimates rather than har metrics so DO NOT explicitly mention them.
- If a previous summary is provided, write a delta summary highlighting what changed since then — new progress, issues, resolved blockers, or status changes. Do not repeat previous information.
  If a previous summary is provided AND there are no relavent updates, respond with "No current updates for <component>." 
  If no previous summary is provided, write a full summary.
- Organize your summary into exactly the following sections in the same order and include only updates that are relevant for today ({today_date}):

Latest Summaries
    - Overview of current priorities, major work, and recent accomplishments with last update dates.
    - This should be a concise paragraph—no fluff or generic phrases.
    - Avoid unnecessary intros (e.g., avoid "The team has been...").

Updates
    - For each notable ticket update, provide bullet points with:
        - Date (if available)
        - Ticket key (e.g., PROJ-2312)
        - Specific, concise summary of progress, issues, decisions, blockers, or dependencies.
    - Avoid generic phrases like "ticket updated."
    - Group updates by date.

Archived
    - List ONLY tickets cancelled or confirmed not to be done.
    - Reference ticket keys and briefly describe outcome (e.g., "Cancelled due to X").

Formatting
    - Use mainly bullet points throughout.
    - Be concise, factual, and specific.
    - Output ONLY the summary or "No current updates for <component>."
    - No explanations or extra commentary.
----

Current Tickets JSON:
{tickets_json}

Previous Summary:
{previous_summary}

Updates:
<Write your summary here or reply with "No current updates for <component>.">
/nothink
""")
    
    chat_openai = create_langchain_openai_stub(llm_setting, temperature=0.2)

    async def summarize_group(state: State, config):
        jira_repo: JiraRepo = config['configurable'].get("jira_repo")
        tickets = state['tickets']
        for ticket in tickets:
            #ticket['images'] = await jira_repo.get_images_from_id(ticket['id'])
            #logger.debug(ticket['images'])
            ticket['images'] = []
            #logger.debug(ticket['images'])
        messages = await progress_prompt.ainvoke({"tickets_json": state["tickets"], "previous_summary": state["yesterday"], "today_date": state["date"]})
        logger.info("Running chat model")
        response = await chat_openai.ainvoke(messages, config)
        logger.debug(response.content)
        return {"today": str(response.content)}

    # Compile application and test
    graph_builder = StateGraph(State).add_sequence([summarize_group])
    graph_builder.add_edge(START, "summarize_group")
    #logger.info("Graph compiled")
    return graph_builder.compile()

class ImageState(TypedDict):
    image: str
    description: str
    url: str

async def create_image_langgraph(llm_setting: OpenAISetting) -> StateGraph:
    """
    Create the image langgraph

    Since
    --------
    0.0.6 (Updated at 0.0.8)
    
    """
    chat_openai = create_langchain_openai_stub(llm_setting, 0.2)
    async def describe(state: ImageState, config):
        try:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe what is happening in this image."},
                        {"type": "image_url", "image_url": {"url": state["image"]}}
                    ]
                }
            ]
            logger.info("Running image model")
            response = await chat_openai.ainvoke(messages, config)
            logger.debug(response.content)
            return {"description": str(response.content)}
        except Exception as e:
            logger.error(f"Error in describe node: {e}")
            raise
    
    # Compile application and test
    graph_builder = StateGraph(ImageState).add_sequence([describe])
    graph_builder.add_edge(START, "describe")
    logger.info("Image graph compiled")
    return graph_builder.compile()

async def create_agent(llm_setting: OpenAISetting) -> StateGraph:
    """    
    Since
    --------
    0.0.10 (Updated at 0.0.9)
    """
    system_prompt = f"""
        You are a Jira Agent designed to help users interact with Jira tickets and manage sprint progress for functional groups. Follow these instructions:

        1. Understand the User’s Request
            If the user provides a Jira issue key:
                - Extract and validate the key. The correct format is <PROJECT>-<NUMBER> (e.g., PROJ-1234).
                - Allowed projects should be configured in your environment.
                - If the key is incorrectly formatted (e.g., missing dash, lowercase, or space instead of dash), correct it.
                - If the project code is not allowed, respond: “This project does not exist.”
                - If the key is missing or invalid, respond: “Please provide the Jira ticket key in the format PROJECT-123.”

            If the user refers to a functional group/component:
                - Identify the group/component from the allowed list:
                  AI, Database, DevOps n Tools, Drop Copy, HA n Resiliency, LCH, MDP, Monitoring, NMS, Ops Dashboard, Performance n Capacity, RPS n Quants, RTFP, Site Synchronization, Website, Platform Core Components.
                - If the group/component is not recognized, respond: “Please provide a valid functional group/component.”

        2. Route the Request
            Ticket-related requests:
                - If the user asks for information about a ticket (e.g., "Show me details for PROJECT-123" or "What is PROJECT-123 about?") or a summary of it, use the retrieval tool to get the ticket's title, description, and comments.
                - If the user asks for a summary of activity, status or updates on a ticket (e.g., "Can you summarize updates on PROJECT-123?" or "What has changed in PROJECT-123?"), use the summarization/update tool.
                - If the user asks for classification or categorization (e.g., "Classify PROJECT-123" or "What type of ticket is PROJECT-123?"), use the classification tool.
                - For classification, always return only a valid JSON object as specified by the tool. Do not add any extra commentary or formatting.
                - If the user requests to create a new Jira ticket, use the create_jira_issue_tool.
                  When returning the result of this tool, always output a clear, readable preview of the ticket that was created, including its key, project, issue type, summary, and description. Do not return raw JSON for ticket creation.
                - For the the jira_create_ticket tool make sure you format each field EXACTLY as defined by the schema and consistant with JIRA conventions.
            
            Functional group/component requests:
                - Use the jira_group_status_summary_tool to generate clear, concise daily summaries or status reports for the specified group/component.

        3. If you are unsure which tool to use, select the one that most closely matches the user's intent, or ask the user for clarification.
        4. Never answer user queries directly. Always use the appropriate tool and return its output as instructed.
        5. If the tool provides format instructions or a required output structure, strictly follow them.
        6. If the user's request cannot be fulfilled due to missing or invalid information, respond with a clear instruction on what is needed.

        General Rules
            - Always follow any format or output structure required by the tools.
            - Do not speculate or include information not present in the ticket or component data.
            - If information is missing or unclear, ask the user for the necessary details.
            - Keep all responses factual, objective, and professional.
            - Do not add explanations, commentary, or formatting beyond what is required by the tools.

        For reference, today's date is {str(datetime.now().date())}
        /nothink
        """

    chat_openai = create_langchain_openai_stub(llm_setting)

    agent = create_react_agent(
        model=chat_openai,
        prompt=system_prompt,
        tools=[jira_issue_retrieve_tool, jira_activity_summary_tool, jira_issue_classify_tool, create_jira_issue_tool, jira_group_status_summary_tool],
        version='v1'
    )
    return agent
