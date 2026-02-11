from datetime import datetime
from typing import Dict
from sqlalchemy import JSON, Integer, String, Text
from db.models import Base
from sqlalchemy.orm import Mapped, mapped_column
from enum import Enum

class JiraFollowupTicketTracking(Base):
    """

    """
    # The table name in the database
    __tablename__ = "jira_followup_ticket_trackings"

    issue_key: Mapped[str] = mapped_column(String(32), primary_key=True, comment="The JIRA issue key. For example PROJ-1234")
    """
    The JIRA issue ID

    Since
    --------
    0.0.7
    """
    project: Mapped[str] = mapped_column(String(32))
    """
    The JIRA project that the issue belong to
    
    Since 
    ---------
    0.0.7
    """
    comment_md5: Mapped[str] = mapped_column(String(64), default='', comment="The comment checksum")
    """
    Number of comments processed
    
    Since 
    ---------
    0.0.9
    """
    ticket_created_at: Mapped[datetime] = mapped_column(nullable=True)
    """
    When the ticket being created at

    Since 
    ---------
    0.0.7
    """
    ticket_updated_at: Mapped[datetime] = mapped_column(nullable=True)
    """
    When the ticket being updated at

    Since 
    ---------
    0.0.7
    """
    llm_prompt: Mapped[str] = mapped_column(Text, nullable=True, comment="The full prompt context that we used for generating the sentiment analysis")    
    """
    The LLM prompt

    Since 
    ---------
    0.0.7
    """
    ingest_status: Mapped[str] = mapped_column(String(32), nullable=True)
    """
    What is the last ingest status. Either 'no update', 'no comment'

    Since 
    ---------
    0.0.7    
    """
    last_ingest_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
    """
    When the ticket being ingest at

    Since 
    ---------
    0.0.7
    """

class JiraFollowupStatus(str, Enum):
    NO_ACTION_REQUIRED = "no_action"
    FOLLOW_UP_REQUIRED = "follow_up"
    FOLLOWED = "followed"
    CANCELLED = "cancelled"
    FOLLOW_UP_SENT = "follow_up_sent"

class JiraFollowupNotification(Base):
    """
    Since
    --------
    0.0.7
    """

    # The table name in the database
    __tablename__ = "jira_followup_notifications"

    issue_key: Mapped[str] = mapped_column(String(32), primary_key=True, comment="The JIRA ticket ID")
    """
    The JIRA ticket ID

    Since
    --------
    0.0.7
    """
    recipient: Mapped[str] = mapped_column(String(32), primary_key=True, comment="The receipient that need to answer the question")
    """
    The JIRA ticket ID

    Since
    --------
    0.0.7
    """
    comment_id: Mapped[int] = mapped_column(Integer, comment="The comment ID caused this follow-up notification")
    """
    The comment ID that caused this follow-up notification

    Since
    --------
    0.0.7
    """
    status: Mapped[str] = mapped_column(String(12), comment="The JIRA ticket chase status")
    """
    The JIRA ticket chase status

    Since
    --------
    0.0.7
    """
    reason: Mapped[str] = mapped_column(String(64), default="", comment="Reason of status changes")
    """
    Since
    --------
    0.0.7
    """
    issue_summary: Mapped[Dict] = mapped_column(JSON)
    """
    The summary text for chasing the 
    
    Since 
    ---------
    0.0.7
    """
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    """
    When is the setting is created

    Since 
    ---------
    0.0.7
    """
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
    """
    When is the setting updated

    Since 
    ---------
    0.0.7
    """
