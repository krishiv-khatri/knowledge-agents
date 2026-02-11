from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import List
from langgraph.graph import StateGraph
from fastapi import HTTPException
from web.langchain_jira.client import JiraApiClient
from web.langchain_jira.repo import JiraRepo

class IngestService:
    """    
    Since
    -----
    0.0.6
    """

    def __init__(self, jira_client: JiraApiClient, jira_repo: JiraRepo, logger: Logger, lang_graph: StateGraph, vlm_langgraph: StateGraph):
        """
        Args:
            jira_client: The asyncio jira client used for extracting jira tickets
            vectorstore_repo: The repository holding the jira tickets
            logger: The shared logger
            lang_greph: 
            vlm_langgraph: 

        Since
        -----
        0.0.6 (Updated at 0.0.7)
        """
        self._jira_client = jira_client
        self._jira_repo = jira_repo
        self._logger = logger
        self._ingest_components = []
        self._lang_graph = lang_graph
        self._vlm_graph = vlm_langgraph

    def add_ingest_components(self, components: List[str]):
        """
        Add the jira components that need to be ingest periodically

        Args:
            component (List[str]): a list of the component names

        Since
        -----
        0.0.6
        """
        self._ingest_components.append(components)

    async def reingest(self):
        """
        Since
        -----
        0.0.6
        """
        for components in self._ingest_components:
            await self.ingest(components)

    async def ingest(self, components: List[str], target_table: str = 'progress'):
        """
        Since
        -----
        0.0.8
        """
        self._logger.info(f"{'SUMMARY':15} PROCESSED START <target_table:{target_table}>")

        for component in components:
            # Add daily summaries
            self._logger.info(f"{'SUMMARY':15} <fg:{component}>")
            try:
                # Delete latest row
                await self._jira_repo.delete_latest_row(target_table, component)

                # Store daily ticket infromation to the progress table
                grouped_issues = self._jira_client.group_issues_by_date(self._jira_client.get_issue_changelogs_by_component(component))
                await self._jira_repo.store_group_history(target_table, component, grouped_issues)

                result = await self._jira_repo.get_all_group_history(target_table, component)

                #fetch previous summary
                prev_row = await self._jira_repo.get_previous_summary(target_table, component)
                prev_response = prev_row["summary"]
                prev_date = str(prev_row["snapshot_date"])
                self._logger.debug(f"Previous summary <{prev_date}>: {prev_response}")
                
                for day in result:
                    date = day["date"]
                    tickets = day["tickets"]

                    if datetime.strptime(date, "%Y-%m-%d") >= datetime.strptime(prev_date, "%Y-%m-%d"):
                        response = await self._lang_graph.ainvoke({"question": f"what is happening with the {component} group", "tickets": tickets, "yesterday": prev_response, "date": date})

                        if "no current updates" not in response["today"].lower():
                            prev_response = response["today"]

                        await self._jira_repo.aadd_group_summary(target_table, component, date, response["today"])
                        self._logger.info(f"{'SUMMARY':15} <fg:{component}, date:{date}>")
                    else:
                        self._logger.info(f"{'SUMMARY':15} SKIPPED <fg:{component}, date:{date}>")

                dt_last_processed: datetime = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

                dt_today = datetime.now(tz=timezone.utc)

                # Handle the case if there is no ticket for that component 
                date_ticket_dict = {}

                date = dt_last_processed + timedelta(days=1)
                while date < dt_today:
                    self._logger.info(f"SKIPPED {date} {dt_today}")
                    date_ticket_dict[datetime.strftime(date, "%Y-%m-%d")] = {}
                    date = date + timedelta(days=1)

                await self._jira_repo.store_group_history(target_table, component, date_ticket_dict)

                date = dt_last_processed + timedelta(days=1)
                while date < dt_today:
                    await self._jira_repo.aadd_group_summary(target_table, component, datetime.strftime(date, "%Y-%m-%d"), f"No current updates for {component}.")
                    date = date + timedelta(days=1)

            except Exception as e:
                self._logger.exception(e)
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing request: {str(e)}"
                )

        self._logger.info(f"{'SUMMARY':15} PROCESSED END")