import asyncio
from datetime import datetime
import hashlib
import json
import traceback
from typing import List, Dict, TypedDict
from langgraph.graph import START, StateGraph, END
from langchain_core.prompts import PromptTemplate
from web.langchain_jira.models import JiraFollowupStatus, JiraFollowupTicketTracking
from web.openai.models import OpenAISetting
from web.langchain.util import create_langchain_openai_stub
from web.langchain_jira.dependencies import logger
from web.langchain_jira.repo import JiraFollowupRepo
from web.langchain_jira.util import get_current_issues_v2

class State(TypedDict):
    issue: Dict
    messages: List[Dict]
    jira_followup_repo: JiraFollowupRepo

class JiraChaser:
    def __init__(self, llm_setting: OpenAISetting, jira_follow_up_repo: JiraFollowupRepo):
        self.lang_graph = None
        self.llm_setting = llm_setting
        self.jira_follow_up = jira_follow_up_repo

    async def initialize(self):
        # Create the LangGraph instance for chasing
        self.lang_graph = await create_chaser_langgraph(self.llm_setting)

    async def chase(self):
        cnt = 0
        start_at = 0
        max_tickets_to_process = 100
        # For each round, we can ONLY process `max_tickets_to_process`
        while cnt < max_tickets_to_process:
            issues = get_current_issues_v2(start_at)
            for issue in issues:
                try:
                    issue_key = issue['key']
                    logger.debug(f"{'SENTI':15} Process <issue_key:{issue_key}")
                    issue_last_updated: int = issue['updated_epoch']                    
                    dt_updated_at = datetime.fromtimestamp(issue_last_updated)
                    
                    # Get the existing tracking to see whether we need to update or not
                    existing_jira_ticket_tracking: JiraFollowupTicketTracking = await self.jira_follow_up.aget_tracking(issue_key)
                    process_needed = False
                    reason = ""
                    #
                    # Only process the sentiment analysis when the following conditions met
                    # 
                    # 1) No tracking record
                    # 2) tracking record are synchronized with ticket last update
                    #
                    if not issue['comments']:
                        process_needed = False
                        reason = "skip_as_no_comments"
                    elif not existing_jira_ticket_tracking:
                        process_needed = True
                        reason = 'no_existing_record'
                    else:
                        existing_last_updated: float = existing_jira_ticket_tracking.ticket_updated_at.timestamp()
                        if issue_last_updated >= existing_last_updated:
                            # If ticket is updated, check comment md5
                            comment_md5 = hashlib.md5(json.dumps(issue['comments']).encode(encoding='utf-8')).hexdigest()
                            existing_comment_md5: str = existing_jira_ticket_tracking.comment_md5
                            if comment_md5 != existing_comment_md5:
                                reason = 'comment_changed'
                                process_needed = True
                            else:
                                process_needed = False
                                logger.info(f"{'SKIP SENTI':15} <issue_key: {issue_key}, reason: ticket_update_but_comment_no_updated, existing_last_updated:{existing_last_updated}, last_updated:{issue_last_updated}>")
                        else:
                            process_needed = False
                            reason = 'no_update'

                    if process_needed:
                        logger.info(f"{'PROC SENTI':15} <issue_key: {issue_key}, reason: {reason}, last_updated:{issue_last_updated}, comment_md5:{comment_md5}>")
                        # Update the issue tracking status to PENDING for recovery
                        await self.jira_follow_up.aupsert_tracking(issue_key, ticket_created_at=dt_updated_at, ticket_updated_at=dt_updated_at, ingest_status='pending')
                        cnt += 1
                        result = await self.lang_graph.ainvoke({"issue": issue, "jira_followup_repo": self.jira_follow_up})
                        
                        # Update the issue tracking to completed
                        comment_md5 = hashlib.md5(json.dumps(issue['comments']).encode(encoding='utf-8')).hexdigest()
                        await self.jira_follow_up.aupsert_tracking(issue_key, ticket_created_at=dt_updated_at, ticket_updated_at=dt_updated_at, comment_md5=comment_md5, ingest_status='completed')
                    else:
                        # Skip sentiment analysis if no comments there
                        logger.info(f"{'SKIP SENTI':15} <issue_key: {issue_key}, reason: {reason}>")
                        await self.jira_follow_up.aupsert_tracking(issue_key, ticket_created_at=dt_updated_at, ticket_updated_at=dt_updated_at, llm_prompt='', ingest_status=reason)

                        #     if issue_last_updated >= existing_last_updated and (existing_status == 'completed' or existing_status == 'skip_as_no_update'):
                        #         logger.info(f"{'SKIP SENTI':15} <issue_key: {issue_key}, reason: no_update, existing_last_updated:{existing_last_updated}, last_updated:{issue_last_updated}>")
                        #         # Update the issue tracking status
                        #         await self.jira_follow_up.aupsert_tracking(issue_key, ingest_status='skip_as_no_update')
                        #     else:
                        #         logger.info(f"{'PROC SENTI':15} <issue_key: {issue_key}, reason: need_update, last_updated:{issue_last_updated}>")
                        #         # Update the issue tracking status to PENDING for recovery
                        #         await self.jira_follow_up.aupsert_tracking(issue_key, ticket_created_at=dt_updated_at, ticket_updated_at=dt_updated_at, ingest_status='pending')
                        #         cnt += 1
                        #         result = await self.lang_graph.ainvoke({"issue": issue, "jira_followup_repo": self.jira_follow_up})
                        #         # Update the issue tracking status to PENDING for recovery
                        #         await self.jira_follow_up.aupsert_tracking(issue_key, ingest_status='completed')
                        # else:
                        #     logger.info(f"{'PROC SENTI':15} <issue_key: {issue_key}, reason: no_existing_record, last_updated:{issue_last_updated}>")
                        #     # Update the issue tracking status to PENDING for recovery
                        #     await self.jira_follow_up.aupsert_tracking(issue_key, ticket_created_at=dt_updated_at, ticket_updated_at=dt_updated_at, ingest_status='pending')
                        #     cnt += 1
                        #     result = await self.lang_graph.ainvoke({"issue": issue, "jira_followup_repo": self.jira_follow_up})
                        #     # Update the issue tracking status to PENDING for recovery
                        #     await self.jira_follow_up.aupsert_tracking(issue_key, ingest_status='completed')
                except Exception as e:
                    logger.error(f"{'SENTI':15} ERROR <issue_key: {issue_key} msg:{e}> ")
                    #traceback.print_exc(e)

            await asyncio.sleep(5)
            if len(issues) == 0:
                break
            start_at += len(issues)


async def create_chaser_langgraph(llm_setting) -> StateGraph:
    """
    Create the  JIRA chaser LangGraph that:
    - For each issue, analyzes sentiment on all fields and comments
    - Decides if action is needed
    - If yes, generates a chase/reminder/follow-up message to last tagged people
    - Adds chase messages to state
    """

    chaser_prompt = PromptTemplate.from_template("""
You are an AI assistant helping to manage JIRA issues.

Analyze the following issue details and its comments carefully, Those comments are listed in chronological order. That is to say, the oldest at the top, the latest comment at the bottom.

GUIDLINE:

- Comments content are stored in "comment" field in JSON
- Comments timestamp are stored in "timestamp" field in ISO8601 format.
- Tagged persons are always indicated in square brackets immediately following a tilde ~, 
  - Example 1: [jane.doe@example.com ] 
  - Example 2: [jsmith]
- Tagged persons info may be an email or just a username.
- Identify all tagged persons ONLY in comments (not in the description) by extracting the text after the tilde ~ inside the square brackets.
- Consider only the most recent instance of each tagged person by examining the timestamps of the comments.
- Differentiate clearly between the commenter (full name) and the tagged person(s).
                                                 
<context>
{issue}
</context>

INSTRUCTION:

- Determine if a follow-up is needed for each tagged person by applying these rules:
- ONLY follow up if the tagged person has been explicitly asked to take an action or respond to a question in their most recent tagging.
- DO NOT follow up if the tagged person is mentioned solely for informational purposes or to keep them in the loop.
- DO NOT follow up if the tagged person has already responded or addressed the request in any subsequent comments.
- DO NOT follow up if the issue or the specific question has been REPLIED in later comments.
- Use the full context, including the description, summary, and all comments in chronological order, to judge whether any action is still pending.
- Ensure that the follow-up is relevant and timely by focusing on recent comments and the current state of the discussion, rather than just the presence of tags.
- For each tagged username requiring follow-up, generate a polite, clear chase/reminder message including:
  - "recipient": the tagged person's username
  - "subject": a concise subject line including the issue priority/urgency and ticket key (e.g., "[High Priority] XYZ-123")
  - "body": a message that includes:
    - Who pinged them (the commenter’s full name)
    - For what ticket (issue key)
    - What they are asked to do (the specific follow-up action)
      - A brief summary of the ticket (from the summary field)
      - Current status based on description and comments, reflecting the latest information
    "reason": a reason why the tagged person should follow-up
    "comment_timestamp": "The timestamp in ISO8601 format when the tagged person is being asked"
    "comment_id": "The comment id containing the question that tagged the person
                                                 
 - Do NOT include tagged usernames for which no follow-up is needed in the output.
 - If there are no comments or no tagged usernames require follow-up, you MUST respond with EXACTLY "No follow-up needed." NEVER return an empty JSON.
 - Return either "No follow-up needed." OR a JSON list where each element is an object with the following fields:
   "recipient": string (username extracted from tagged info)
   "subject": string
   "body": string
   "reason": string
   "comment_timestamp": "The timestamp in ISO8601 format when the tagged person is being asked"
   "comment_id": integer
   It should be a plain string and not formatted in a particular way.

Example response:
[
    {{
        "recipient": "jane.doe@example.com",
        "subject": "[High Priority] Following up on XYZ-123",
        "body": "Hi Jane, you were pinged by John Smith regarding ticket XYZ-123. Please provide an update or next steps as requested. The ticket summary is: 'Fix login issue on mobile app.' Currently, the issue is in progress with recent comments indicating some blockers.",
        "reason": "The reason why being tagged"
    }},
    {{
        "recipient": "jsmith",
        "subject": "[Medium Priority] Reminder to address testing on XYZ-123",
        "body": "Hi John, you were pinged by Alice Brown regarding ticket XYZ-123. Kindly review the latest changes and confirm if testing can proceed. The ticket summary is: 'Fix login issue on mobile app.' The current status is 'In Review' with comments awaiting your approval.",
        "reason": "The reason why being tagged"
        
    }}
]
""")


    chat_openai = create_langchain_openai_stub(llm_setting, temperature=0.01)

    async def analyze(state: State, config):
        # Run the prompt with issue data
        issue = state["issue"]
        title = issue["title"]
        description = issue['description']
        comments = issue["comments"]
        # print("PROMPT")
        # print(comments)
        #priority = issue["priority"]
        key = issue["key"]
        #key, "title": title, "description": description, "comments": comments, "priority": priority})
        messages = await chaser_prompt.ainvoke({"issue": json.dumps(issue, indent=4) })

        jira_followup_repo: JiraFollowupRepo = state.get("jira_followup_repo")
        try:
            dt_undefined = datetime.fromtimestamp(0)
            await jira_followup_repo.aupsert_tracking(key, ticket_created_at=dt_undefined, ticket_updated_at=dt_undefined, llm_prompt=messages.to_string())
        except Exception as e:
            print(e)
            traceback.print_exception(e)

        logger.info(f"Running sentiment and follow-up generation LLM for <{issue['key']}>")
        response = await chat_openai.ainvoke(messages, config)
        logger.debug(f"LLM response: {response.content}")
        print(f"{response.content}")
        
        if 'no follow-up' in str(response.content).lower():
            return {"messages": []}        
        try:
            followups = json.loads(response.content)
            return {"messages": followups}
        except Exception as e:
            logger.exception(f"Failed to parse LLM response: {e}")

    async def send(state: State):
        print("sending...")
        jira_followup_repo: JiraFollowupRepo = state.get("jira_followup_repo")
        issue_key = state['issue']['key']
        follow_up_messages = state.get('messages', [])
        try:
            # If there are existing follow-up status, reset it
            await jira_followup_repo.areset_followup_status(issue_key, status=JiraFollowupStatus.FOLLOWED)

            if follow_up_messages:
                for follow_up_message in follow_up_messages:
                    
                    await jira_followup_repo.aadd_followup(issue_key, follow_up_message['recipient'], follow_up_message['comment_id'], follow_up_message)
            else:
                pass
                #await jira_followup_repo.aadd_no_followup(issue_key)

            issue_last_updated: float = state['issue']['updated_epoch']
            # TODO: filling created_at wrongly
            
            dt_updated_at = datetime.fromtimestamp(issue_last_updated)
            await jira_followup_repo.aupsert_tracking(issue_key, ticket_created_at=dt_updated_at, ticket_updated_at=dt_updated_at)
            logger.info(f"{'NOTIFY':15} Tracking <issue_key: {issue_key} last_updated: (epoch:{issue_last_updated}, human_readable: {state['issue']['updated']}>")
        except Exception as e:
            print(e)
            traceback.print_exception(e)

    graph_builder = StateGraph(State)
    graph_builder.add_sequence([analyze, send])
    graph_builder.add_edge(START, "analyze")

    logger.info("JiraChaser LangGraph compiled")
    return graph_builder.compile()