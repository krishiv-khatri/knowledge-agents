import os
import re
import json
import asyncio
import logging
from typing import Annotated
from fastapi import APIRouter, Body, Depends, HTTPException
from langgraph.graph.graph import CompiledGraph
from langgraph.graph import StateGraph
from web.dependencies import register_logger
from web.langchain_jira.ingest_service import IngestService
from web.openai.dependencies import require_openai_setting
from web.openai.models import OpenAISetting
from web.langchain.util import StreamingResponseWithStatusCode, langchain_stream_with_statuscode_generator
from web.langchain_jira.util import get_all_issues, get_image, get_issue_changelogs_by_component, get_issue_payload, group_issues_by_date, update_issue, get_issue, create_issue
from web.langchain_jira.chaser import JiraChaser
from web.langchain_jira.dependencies import require_image_langgraph, require_ingest_service, require_jira_agent, require_jira_follow_up_repo, require_jira_repo
from web.langchain_jira.util import get_issue_changelogs_by_component, group_issues_by_date, update_issue, get_issue, create_issue
from web.langchain_jira.schemas import ChatCompletionRequest, AgentCompletionRequest, OpenaiCompletionRequest, QueryResponsePayload
from web.langchain_jira.repo import JiraFollowupRepo, JiraRepo

router = APIRouter(prefix="/api/v1")

tags = ["jira_assistant"]

logger = register_logger("langchain_jira", level=logging.DEBUG, log_filename="langchain_jira")

@router.post(
    f"/jira",
    tags=tags,
    include_in_schema=True
)
async def completion(
    body: Annotated[AgentCompletionRequest, Body], 
    agent: CompiledGraph = Depends(require_jira_agent),
    jira_repo: JiraRepo = Depends(require_jira_repo),
):
    """
    Since
    --------
    0.0.2
    """
    msg = {"messages": {"role": "user", "content": body.question}}
    return StreamingResponseWithStatusCode(
        langchain_stream_with_statuscode_generator(agent.astream(msg, config={"jira_repo": jira_repo}, stream_mode=["messages"])),
        media_type='text/chunked')

# @router.post(
#     "/jira_openai",
#     tags=tags,
#     include_in_schema=True
# )
# async def jira_completion(
#     body: OpenaiCompletionRequest = Body(...),
#     agent: CompiledGraph = Depends(require_jira_agent),
#     jira_repo: JiraRepo = Depends(require_jira_repo),
# ):
#     # Validate messages exist
#     if not body.messages:
#         raise HTTPException(status_code=400, detail="Messages list is empty")

#     msg = {"messages": body.messages}

#     return StreamingResponseWithStatusCode(
#         langchain_stream_with_statuscode_generator(
#             agent.astream(msg, config={"jira_repo": jira_repo}, stream_mode=["messages"])
#         ),
#         media_type="text/chunked"
#     )

async def process_jira_completion(
    body: OpenaiCompletionRequest,
    agent: CompiledGraph,
    jira_repo: JiraRepo,
):
    if not body.messages:
        raise HTTPException(status_code=400, detail="Messages list is empty")

    msg = {"messages": body.messages}

    return StreamingResponseWithStatusCode(
        langchain_stream_with_statuscode_generator(
            agent.astream(msg, config={"jira_repo": jira_repo}, stream_mode=["messages"])
        ),
        media_type="text/event-stream"
    )

@router.post(
    f"/update",
    tags=tags,
    include_in_schema=True
)
async def completion(
    payload: QueryResponsePayload
):
    """
    Since
    --------
    0.0.2
    """
    # Extract the ticket key using regex
    pattern = r"\b([a-zA-Z]+)[\s-]+(\d+)\b"
    match = re.search(pattern, payload.query)
    if match:
        project = match.group(1).upper()
        number = match.group(2)
        # Add your allowed Jira project keys here
        allowed_projects = os.getenv("JIRA_ALLOWED_PROJECTS", "MYPROJECT,SUPPORT,INFRA").split(",")
        if project in allowed_projects:
            key = f"{project}-{number}"
            logger.debug(f"KEY: {key}")
        else:
            logger.error(f"This project does not exist: {project}")
    else:
        raise HTTPException(status_code=400, detail="Invalid or missing ticket key in query")
    
    # Ensure the response field is present and not empty
    if not payload.response:
        raise HTTPException(status_code=400, detail="Missing response in payload")

    # Check if response is JSON or plain text
    classification = None
    response_type = None
    try:
        decoder = json.JSONDecoder()
        payload.response = payload.response.strip()
        for i, char in enumerate(payload.response):
            if char == '{':
                try:
                    obj, end = decoder.raw_decode(payload.response[i:])
                    classification = obj
                    response_type = "json"
                    break  # Stop after finding the first valid JSON
                except json.JSONDecodeError:
                    continue
        if response_type != "json":
            # Try to parse the whole string as JSON (in case it's pure JSON)
            classification = json.loads(payload.response)
            response_type = "json"
    except (json.JSONDecodeError, TypeError):
        logger.info("JSON noty detected")
        summary = str(payload.response)
        response_type = "text"


    if response_type == "json":
        logger.info('detected JSON successfully')
        # Handle JSON response
        fields = {"components": [{"name": component} for component in classification["components"]],
                                "issuetype": {"name": classification["issuetype"]},
                                "priority": {"name": classification["priority"]},
                                "labels": classification["labels"]}
        data = {"fields": fields}
        update_issue(key, data)
    else:
        # Handle text response
        if "🤖 Latest updates" in summary:
            summary_wo_header = re.sub(r"^## 🤖 Latest updates:\s*\n", "", summary)
            divider = "----"
            summary_header = "h4. *🤖 Latest updates:*"

            # Get current description
            description = get_issue(key)["description"]

            # Build the new summary block
            new_summary_block = f"{summary_header}\n{str(summary_wo_header).strip()}\n{divider}\n"

            # Regex to find existing summary block (from header to divider)
            pattern = re.compile(
                rf"^{re.escape(summary_header)}\n.*?\n{re.escape(divider)}\n", re.DOTALL
            )

            # If summary exists, replace it; else, prepend
            if pattern.match(description):
                updated_description = pattern.sub(new_summary_block, description, count=1)
            else:
                updated_description = new_summary_block + description.lstrip()

            data = {"update": {"description": [{"set": updated_description}]}}
            update_issue(key, data)

@router.post(
    f"/create",
    tags=tags,
    include_in_schema=True
)
async def create_ticket(
    payload: QueryResponsePayload,
    jira_repo: JiraRepo = Depends(require_jira_repo),
):
    
    preview = payload.response
    match = re.search(r"Reference ID:\s*(\w+)", preview)
    if match:
        ref_id = match.group(1)
        logger.info(f"Reference ID: {ref_id}")
    data = await jira_repo.get_issue(ref_id)
    data = json.loads(data)
    data["fields"]["reporter"] = {"name": payload.user_email}
    jira_response = create_issue(data)

    key = jira_response["key"]
    jira_base_url = os.getenv("JIRA_BASE_URL", "https://jira.example.com")
    return {"key": key, "url": f"{jira_base_url}/browse/{key}"}

@router.post(
    f"/store_group",
    tags=tags,
    include_in_schema=True
)
async def store_group_tickets(
    jira_repo: JiraRepo = Depends(require_jira_repo),
):
    # Load component names from config. These should match your Jira project's component names.
    from web.persistence.dependencies import require_config
    config = require_config()
    components = config.get("jira", {}).get("cron", {}).get("components", [])
    for component in components:
        grouped_issues = group_issues_by_date(get_issue_changelogs_by_component(component))
        await jira_repo.store_group_history(component, grouped_issues)
    logger.info("ADDED TO DB :)")

@router.post(
    f"/store",
    tags=tags,
    include_in_schema=True
)
async def store_tickets(
    jira_repo: JiraRepo = Depends(require_jira_repo),
):
    start_at = 0
    while start_at < 2377:
        issues = get_all_issues(start_at)
        for issue in issues:
            try:
                payload = get_issue_payload(issue['key'])
                await jira_repo.store_issue(issue, payload)
                logger.info(f"Stored ticket <{issue['key']}>")
            except Exception as e:
                logger.exception(e)
        start_at += 100
        await asyncio.sleep(5)

        

@router.post(
    f"/progress",
    tags=tags,
    include_in_schema=True
)
async def progress(ingest_service: IngestService = Depends(require_ingest_service)):
    """
    Since
    --------
    0.0.6 (Updated at 0.0.8.2)
    """
    await ingest_service.reingest()

@router.post(
    f"/describe",
    tags=tags,
    include_in_schema=True
)
async def describe_image(
    image_langgraph: StateGraph = Depends(require_image_langgraph),
    jira_repo: JiraRepo = Depends(require_jira_repo),
):
    images = await jira_repo.get_image_urls()
    for image in images:
        try:
            issue_id = image['issue_id']
            url = image['image_url']
            image_encoded = get_image(url)
            logger.info(f'Describing image <{url}>')
            response = await image_langgraph.ainvoke({"image": image_encoded})
            await jira_repo.update_image_description(url, response['description'])
        except Exception as e:
            logger.exception(e)

@router.post(
    f"/test_progress",
    tags=tags,
    include_in_schema=True
)
async def test_progress(ingest_service: IngestService = Depends(require_ingest_service)):
    """
    Since
    --------
    0.0.7 (Updated at 0.0.8.2)
    """
    component = "Performance n Capacity"
    table = 'test_progress'
    await ingest_service.ingest([component], table)

@router.post(
    f"/chase",
    tags=tags,
    include_in_schema=True
)
async def chase(
    llm_setting: OpenAISetting = Depends(require_openai_setting), 
    jira_follow_up_repo: JiraFollowupRepo = Depends(require_jira_follow_up_repo)):

    jira_chaser = JiraChaser(llm_setting=llm_setting, jira_follow_up_repo=jira_follow_up_repo)
    await jira_chaser.initialize()
    await jira_chaser.chase()
