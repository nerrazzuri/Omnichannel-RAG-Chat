"""
SQLAlchemy data models for the Omnichannel Enterprise RAG Chatbot Platform.
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, JSON, ForeignKey, Index
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from sqlalchemy.dialects import postgresql

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type.

    Uses PostgreSQL UUID type, otherwise stores as CHAR(36) string.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value if dialect.name == "postgresql" else str(value)
        # Coerce strings to UUID
        coerced = uuid.UUID(str(value))
        return coerced if dialect.name == "postgresql" else str(coerced)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

class Tenant(Base):
    """Tenant model representing an organization."""
    __tablename__ = "tenants"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    subscription_tier = Column(String(50), default="BASIC")
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="tenant", cascade="all, delete-orphan")
    knowledge_bases = relationship("KnowledgeBase", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name}, domain={self.domain})>"

class User(Base):
    """User model for both internal staff and external customers."""
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID(), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(255))  # Channel-specific user identifier
    user_type = Column(String(50), nullable=False)  # INTERNAL_STAFF or EXTERNAL_CUSTOMER
    role = Column(String(50), default="END_USER")  # ADMIN, MANAGER, AGENT, END_USER
    preferences = Column(JSON, default=dict)
    last_active_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, tenant_id={self.tenant_id}, user_type={self.user_type})>"

class Conversation(Base):
    """Conversation model maintaining context across channels."""
    __tablename__ = "conversations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID(), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    channel = Column(String(50), nullable=False)  # whatsapp, wechat, line, telegram, web, teams
    status = Column(String(50), default="ACTIVE")  # ACTIVE, COMPLETED, ESCALATED
    context = Column(JSON, default=dict)  # Conversation state and metadata
    channel_context = Column(JSON, default=dict)  # Per-channel identifiers and state
    started_at = Column(DateTime, default=func.now())
    last_message_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)

    # Relationships
    tenant = relationship("Tenant", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation(id={self.id}, tenant_id={self.tenant_id}, channel={self.channel})>"

class Message(Base):
    """Message model for individual communications."""
    __tablename__ = "messages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(GUID(), ForeignKey("conversations.id"), nullable=False)
    sender_type = Column(String(50), nullable=False)  # USER, SYSTEM, HUMAN_AGENT
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default="TEXT")  # TEXT, IMAGE, FILE, BUTTON_RESPONSE
    meta = Column('metadata', JSON, default=dict)  # Channel-specific message data
    timestamp = Column(DateTime, default=func.now())
    is_processed = Column(Boolean, default=False)  # Whether RAG processing completed

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, sender_type={self.sender_type})>"

class KnowledgeBase(Base):
    """Knowledge base model for organizing documents."""
    __tablename__ = "knowledge_bases"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(GUID(), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, BUILDING, ARCHIVED
    document_count = Column(Integer, default=0)
    last_updated_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="knowledge_bases")
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, tenant_id={self.tenant_id}, name={self.name})>"

class Document(Base):
    """Document model for knowledge base content."""
    __tablename__ = "documents"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    knowledge_base_id = Column(GUID(), ForeignKey("knowledge_bases.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_url = Column(String(500))
    meta = Column('metadata', JSON, default=dict)  # Author, publish_date, tags, etc.
    status = Column(String(50), default="PROCESSING")  # PROCESSING, INDEXED, FAILED
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    indexed_at = Column(DateTime)

    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, knowledge_base_id={self.knowledge_base_id}, title={self.title})>"

class KnowledgeChunk(Base):
    """Knowledge chunk model with vector embeddings."""
    __tablename__ = "knowledge_chunks"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)  # Chunk text content (~700 characters)
    chunk_index = Column(Integer, nullable=False)  # Position within document
    embedding = Column(JSON)  # Vector embedding stored as JSON array
    meta = Column('metadata', JSON, default=dict)  # Chunk-level metadata
    created_at = Column(DateTime, default=func.now())

    # Relationships
    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<KnowledgeChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"
