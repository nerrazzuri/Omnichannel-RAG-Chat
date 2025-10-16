"""
Conversation context management backed by SQLAlchemy models.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from shared.database.models import Conversation, Message, User


class ConversationService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_conversation(
        self, tenant_id: str, user_id: str, channel: str, context: Optional[Dict[str, Any]] = None, channel_ctx: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        # Ensure the user exists to satisfy FK constraints (PostgreSQL)
        user = self.db.get(User, user_id)
        if not user:
            # Default new users to END_USER role; infer type from channel
            inferred_type = "EXTERNAL_CUSTOMER" if channel.lower() in {"web", "whatsapp", "telegram", "teams"} else "EXTERNAL_CUSTOMER"
            user = User(id=user_id, tenant_id=tenant_id, user_type=inferred_type)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        stmt = (
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id)
            .where(Conversation.user_id == user_id)
            .where(Conversation.channel == channel)
            .where(Conversation.status == "ACTIVE")
        )
        existing = self.db.execute(stmt).scalars().first()
        if existing:
            return existing

        convo = Conversation(
            tenant_id=tenant_id,
            user_id=user_id,
            channel=channel,
            context=context or {},
            channel_context=channel_ctx or {},
        )
        self.db.add(convo)
        self.db.commit()
        self.db.refresh(convo)
        return convo

    def add_message(
        self,
        conversation: Conversation,
        sender_type: str,
        content: str,
        message_type: str = "TEXT",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation.id,
            sender_type=sender_type,
            content=content,
            message_type=message_type,
            meta=metadata or {},
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_recent_messages(self, conversation: Conversation, limit: int = 10) -> List[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.timestamp.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())


