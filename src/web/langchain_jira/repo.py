import os
import json
import logging
import asyncpg
from datetime import datetime
from logging import Logger
from typing import Dict, Optional
from py_markdown_table.markdown_table import markdown_table
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.dialects.postgresql import insert
from web.langchain_jira.models import JiraFollowupNotification, JiraFollowupStatus, JiraFollowupTicketTracking

class JiraRepo:
    """
    A wrapper for `langchain_postgres` repo to provide some extra functionality

    Since
    --------
    0.0.6
    """
    def __init__(self, url: str, logger: Logger = None):
        """

        Since
        --------
        0.0.6
        """
        self._url = url
        self._logger = logger
    
    async def aadd_issue(self, ref_id, data: Dict):
        conn = await asyncpg.connect(self._url)
        try: 
            # Store the summary in the new column
            await conn.execute(
            'INSERT INTO issues (ref_id, data) VALUES ($1, $2)',
                ref_id, json.dumps(data))
          
            print(f"Added proposed issue: {ref_id}")            
        except Exception as e:
            print(e)
        finally:
            await conn.close()


    async def get_issue(self, ref_id):
        conn = await asyncpg.connect(self._url)
        row = await conn.fetchrow(
            'SELECT data FROM issues WHERE ref_id = $1',
            ref_id
        )
        if row:
            return row['data']
        else:
            return None
    
    async def store_group_history(self, table: str, component: str, date_ticket_dict: dict):
        conn = await asyncpg.connect(self._url)

        data = [
        [datetime.strptime(date, "%Y-%m-%d").date(), json.dumps(tickets), component]
        for date, tickets in date_ticket_dict.items()
    ]

        stmt = f"""
            INSERT INTO {table} (snapshot_date, tickets, component)
            VALUES ($1::date, $2::jsonb, $3)
            ON CONFLICT (snapshot_date, component) DO NOTHING
        """

        # Insert all rows asynchronously
        await conn.executemany(stmt, data)

        await conn.close()

    async def get_all_group_history(self, table, component):
            conn = await asyncpg.connect(self._url)
            rows = await conn.fetch(f"SELECT snapshot_date, tickets FROM {table} WHERE component = $1 ORDER BY snapshot_date ASC", component)
            await conn.close()
            # Convert to list of dicts, parsing the JSONB field
            result = [
                {
                    "date": row["snapshot_date"].isoformat(),
                    "tickets": json.loads(row["tickets"])
                }
                for row in rows
            ]
            return result

    async def aadd_group_summary(self, table: str, component: str, date: str, summary: str):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            stmt = f"""
                UPDATE {table}
                SET summary = $1
                WHERE snapshot_date = $2::date
                    AND component = $3
            """
            await conn.execute(stmt, summary, datetime.strptime(date, "%Y-%m-%d").date(), component)
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()

    async def get_summaries(self, table, component, limit):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            rows = await conn.fetch(
            f"""
            SELECT snapshot_date, summary
            FROM {table}
            WHERE component = $1
            ORDER BY snapshot_date DESC
            LIMIT $2
            """,
            component, limit
            )
            
            # Convert rows to list of dicts with keys matching column headers
            data = []
            for row in reversed(rows):  # reverse to get ascending order by date
                data.append({
                    "date": str(row["snapshot_date"]),
                    "summary": row["summary"]
                })

            # Generate markdown table string using py-markdown-table
            md_table = markdown_table(data).get_markdown()

            return md_table
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()
    
    async def delete_latest_row(self, table: str, component: str):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            self._logger.info("Deleting latest row")
            await conn.execute(
            f"""
            DELETE FROM {table}
            WHERE ctid = (
                SELECT ctid
                FROM progress
                WHERE component = $1
                ORDER BY snapshot_date DESC
                LIMIT 1
            )
            """,
            component,
        )
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()

    async def get_previous_summary(self, table, component):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            row = await conn.fetchrow(
            f"""
            SELECT snapshot_date, summary
            FROM {table}
            WHERE component = $1
            AND summary NOT ILIKE '%no current updates%'
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            component,
            )
            return row
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()
    
    async def store_issue(self, issue, payload):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            stmt = f"""
                INSERT INTO jira_tickets (issue_id, issue_key, summary, description, ticket_created, ticket_updated, comments, last_ingest_at, payload)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (issue_key) DO NOTHING
            """
            await conn.execute(stmt, issue['id'], issue['key'], issue['title'], issue['description'], issue['created_timestamp'], issue['updated_timestamp'], json.dumps(issue['comments']), datetime.now(), json.dumps(payload))

            if issue['attachments']:
                for file in issue['attachments']:
                    if 'png' in file['filename']:
                        await self.store_image(issue['id'], file)
            
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()
    
    async def store_image(self, issue_id, image: Dict):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            stmt = f"""
                INSERT INTO jira_ticket_images (issue_id, image_url, uploaded_at, file_name)
                VALUES ($1, $2, $3, $4)
                RETURNING issue_id
            """
            await conn.execute(stmt, issue_id, image['content'], datetime.strptime(image['created'], "%Y-%m-%dT%H:%M:%S.%f%z").date(), image['filename'])
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()
    
    async def get_image_urls(self):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            stmt = f"""
                SELECT issue_id, image_url
                FROM jira_ticket_images
                WHERE image_description IS NULL;
            """
            rows = await conn.fetch(stmt)
            dict_rows = [dict(row) for row in rows]
            return dict_rows
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()
    
    async def update_image_description(self, image_url: str, description: str):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            stmt = """
                UPDATE jira_ticket_images
                SET image_description = $1
                WHERE image_url = $2
            """
            await conn.execute(stmt, description, image_url)
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()
    
    async def get_images_from_id(self, issue_id: int):
        conn = None
        try:
            conn = await asyncpg.connect(self._url)
            stmt = f"""
                SELECT file_name, image_url, image_description
                FROM jira_ticket_images
                WHERE issue_id = $1;
            """
            rows = await conn.fetch(stmt, int(issue_id))
            dict_rows = [dict(row) for row in rows]
            return dict_rows
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()

    async def get_email(self, username):
        try:
            conn = await asyncpg.connect(self._url)
            row = await conn.fetchrow(
                'SELECT email FROM users WHERE username = $1',
                username
            )
            return row['email']
        except Exception as e:
            self._logger.exception(e)
        finally:
            if conn:
                await conn.close()

class JiraFollowupRepo:
    """
    A simple repo providing some basic functional to manage the jira follow-up record

    Since
    --------
    0.0.7
    """
    def __init__(self, async_engine: AsyncEngine, logger: Logger = None):
        """
        Since
        --------
        0.0.7
        """
        self._async_engine = async_engine
        self._logger = logger

    async def aget_tracking(self, issue_key: str) -> Optional[JiraFollowupTicketTracking]:
        """
        Args:
            issue_key (str): The JIRA ticket ID like PROJ-1234
            created_at: 
            updated_at: 

        Since
        --------
        0.0.7
        """
        async with AsyncSession(self._async_engine) as session:
            # Step 1 - see whether we have any existing record for this issue_key, PENDING and recipient
            stmt = select(JiraFollowupTicketTracking).where(JiraFollowupTicketTracking.issue_key == issue_key)
            rs = await session.scalars(stmt)
            return rs.first()

    async def aupsert_tracking(self, issue_key: str, ticket_created_at: datetime = None, ticket_updated_at: datetime = None, comment_md5: str = '', llm_prompt: str = None, ingest_status: str = ''):
        """
        Args:
            issue_key (str): The JIRA ticket ID like PROJ-1234
            created_at (datetime): 
            updated_at (datetime): 
            llm_prompt (str): 

        Since
        --------
        0.0.7
        """
        updated_value = {
            "issue_key": issue_key,
            "project": os.getenv("JIRA_PROJECT", "MYPROJECT")
        }
        if ticket_updated_at:
            updated_value["ticket_created_at"] = ticket_created_at
        if ticket_updated_at:
            updated_value["ticket_updated_at"] = ticket_updated_at
        if llm_prompt:
            updated_value["llm_prompt"] = llm_prompt
        if ingest_status:
            updated_value["ingest_status"] = ingest_status
        if comment_md5:
            updated_value["comment_md5"] = comment_md5

        #print(f"aupsert_tracking {updated_value}")

        insert_value = dict(updated_value)
        if not llm_prompt:
            insert_value["llm_prompt"] = ''
        if not ingest_status:
            insert_value["ingest_status"] = ''

        async with AsyncSession(self._async_engine) as session:
            # Step 1 - see whether we have any existing record for this issue_key, PENDING and recipient
            stmt = insert(JiraFollowupTicketTracking).values(insert_value)
            stmt = stmt.on_conflict_do_update(
                index_elements=['issue_key'],  # Primary key or unique constraint,
                set_=updated_value
            )
            await session.execute(stmt)
            await session.commit()

    async def aadd_followup(self, issue_key: str, recipient: str, comment_id: int, issue_summary: Dict) -> bool:
        """

        Args:
            issue_key (str): The JIRA ticket ID like PROJ-1234
            recipient (str): The recipient email
            comment_id (int): The comment ID that caused the follow-up
            issue_summary: (Dict): 

        Since
        --------
        0.0.7
        """
        async with AsyncSession(self._async_engine) as session:
            # Step 1 - see whether we have any existing record for this issue_key, PENDING and recipient
            stmt = select(JiraFollowupNotification.issue_key).where(JiraFollowupNotification.issue_key == issue_key, JiraFollowupNotification.recipient == recipient, JiraFollowupNotification.comment_id == comment_id)
            rs = await session.scalars(stmt)
            existing_issue_key = rs.first()
            if existing_issue_key:
                stmt = update(JiraFollowupNotification).values(status=JiraFollowupStatus.FOLLOW_UP_REQUIRED).where(JiraFollowupNotification.issue_key == issue_key, JiraFollowupNotification.recipient == recipient, JiraFollowupNotification.comment_id == comment_id)
                await session.execute(stmt)
                await session.commit()
                # We have already pending record, no need to add new follow-up
                return False
            else:
                new_followup_record = JiraFollowupNotification(issue_key=issue_key, recipient=recipient, comment_id=comment_id, issue_summary=issue_summary, status=JiraFollowupStatus.FOLLOW_UP_REQUIRED, reason='')
                session.add(new_followup_record)
                await session.commit()
                return True

    async def aadd_no_followup(self, issue_key: str) -> bool:
        """
        Since
        --------
        0.0.7
        """
        async with AsyncSession(self._async_engine) as session:
            # Step 1 - update all action that needed to be follow up to followed
            stmt = update(JiraFollowupNotification).values(status=JiraFollowupStatus.FOLLOWED).where(JiraFollowupNotification.issue_key == issue_key, JiraFollowupNotification.status == JiraFollowupStatus.FOLLOW_UP_REQUIRED)
            await session.execute(stmt)
            
            # Step 2 - insert a new record to say no follow-up is required
            stmt = insert(JiraFollowupNotification).values(issue_key=issue_key, recipient='', issue_summary={}, status=JiraFollowupStatus.NO_ACTION_REQUIRED, reason='')
            stmt = stmt.on_conflict_do_nothing(
                index_elements=['issue_key', 'recipient'],  # Primary key or unique constraint
            )
            await session.execute(stmt)
            await session.commit()
            return True
        
    async def areset_followup_status(self, issue_key: str, status: JiraFollowupStatus) -> bool:
        """
        Since
        --------
        0.0.7
        """
        async with AsyncSession(self._async_engine) as session:
            stmt = update(JiraFollowupNotification) \
                .values(status=JiraFollowupStatus.FOLLOWED) \
                .where(JiraFollowupNotification.issue_key == issue_key, JiraFollowupNotification.status == JiraFollowupStatus.FOLLOW_UP_REQUIRED)
            await session.execute(stmt)
            await session.commit()
            return True

    async def cancel_pending_followup(self, issue_key: str, reason: str) -> bool:
        """
        Args:
            issue_key (str):
            reason (str): The reason why we cancel the follow-up

        Since
        --------
        0.0.7
        """
        async with AsyncSession(self._async_engine) as session:
            # Step 1 - see whether we have any existing record for this issue_key, PENDING and recipient
            stmt = select(func.count()).where(JiraFollowupNotification.issue_key == issue_key, JiraFollowupNotification.status == JiraFollowupStatus.FOLLOW_UP_REQUIRED)
            rs = await session.scalars(stmt)
            cnt = rs.first()
            if cnt == 0:
                # No record need to be updated
                return False
            else:
                stmt = update(JiraFollowupNotification)\
                    .where(JiraFollowupNotification.issue_key == issue_key, JiraFollowupNotification.status == JiraFollowupStatus.FOLLOW_UP_REQUIRED)\
                    .values(status=JiraFollowupStatus.CANCELLED, reason=reason)
                await session.execute(stmt)
                await session.commit()
                return True
