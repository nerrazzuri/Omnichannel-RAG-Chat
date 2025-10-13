# Data Model: Omnichannel Enterprise RAG Chatbot Platform

## Core Entities

### Tenant
Represents an organization using the platform with its own users, knowledge bases, and configurations.

**Fields**:
- `id`: UUID, Primary Key
- `name`: String (255), Organization name
- `domain`: String (255), Unique domain identifier
- `settings`: JSONB, Tenant-specific configurations
- `subscription_tier`: Enum (BASIC, PROFESSIONAL, ENTERPRISE)
- `created_at`: Timestamp
- `updated_at`: Timestamp

**Relationships**:
- One-to-many with User (tenant owner and members)
- One-to-many with KnowledgeBase
- One-to-many with Conversation

### User
Individual interacting with the system, either as internal staff or external customer.

**Fields**:
- `id`: UUID, Primary Key
- `tenant_id`: UUID, Foreign Key → Tenant.id
- `external_id`: String (255), Channel-specific user identifier
- `user_type`: Enum (INTERNAL_STAFF, EXTERNAL_CUSTOMER)
- `role`: Enum (ADMIN, MANAGER, AGENT, END_USER)
- `preferences`: JSONB, User-specific settings (language, notification preferences)
- `last_active_at`: Timestamp
- `created_at`: Timestamp

**Relationships**:
- Many-to-one with Tenant
- One-to-many with Conversation (as participant)

### Conversation
A session of interaction between a user and the system, maintaining context across channels.

**Fields**:
- `id`: UUID, Primary Key
- `tenant_id`: UUID, Foreign Key → Tenant.id
- `user_id`: UUID, Foreign Key → User.id
- `channel`: Enum (WHATSAPP, WECHAT, LINE, TELEGRAM, WEB, TEAMS)
- `status`: Enum (ACTIVE, COMPLETED, ESCALATED)
- `context`: JSONB, Conversation state and metadata
- `started_at`: Timestamp
- `last_message_at`: Timestamp
- `completed_at`: Timestamp, Nullable

**Relationships**:
- Many-to-one with Tenant
- Many-to-one with User
- One-to-many with Message

### Message
Individual communication within a conversation containing user input and system responses.

**Fields**:
- `id`: UUID, Primary Key
- `conversation_id`: UUID, Foreign Key → Conversation.id
- `sender_type`: Enum (USER, SYSTEM, HUMAN_AGENT)
- `content`: Text, Message content
- `message_type`: Enum (TEXT, IMAGE, FILE, BUTTON_RESPONSE)
- `metadata`: JSONB, Channel-specific message data
- `timestamp`: Timestamp
- `is_processed`: Boolean, Whether RAG processing completed

**Relationships**:
- Many-to-one with Conversation

### KnowledgeBase
Collection of verified information and documents that power the RAG system for a tenant.

**Fields**:
- `id`: UUID, Primary Key
- `tenant_id`: UUID, Foreign Key → Tenant.id
- `name`: String (255), Knowledge base identifier
- `description`: Text, Nullable
- `status`: Enum (ACTIVE, BUILDING, ARCHIVED)
- `document_count`: Integer, Number of documents indexed
- `last_updated_at`: Timestamp
- `created_at`: Timestamp

**Relationships**:
- Many-to-one with Tenant
- One-to-many with Document

### Document
Individual document or content source within a knowledge base.

**Fields**:
- `id`: UUID, Primary Key
- `knowledge_base_id`: UUID, Foreign Key → KnowledgeBase.id
- `title`: String (255)
- `content`: Text, Document text content
- `source_url`: String (500), Nullable, Original source location
- `metadata`: JSONB, Document metadata (author, publish_date, tags)
- `status`: Enum (PROCESSING, INDEXED, FAILED)
- `chunk_count`: Integer, Number of text chunks created
- `created_at`: Timestamp
- `indexed_at`: Timestamp, Nullable

**Relationships**:
- Many-to-one with KnowledgeBase
- One-to-many with KnowledgeChunk

### KnowledgeChunk
Text segment from a document with vector embeddings for similarity search.

**Fields**:
- `id`: UUID, Primary Key
- `document_id`: UUID, Foreign Key → Document.id
- `content`: Text, Chunk text content (≈700 characters)
- `chunk_index`: Integer, Position within document
- `embedding`: Vector (1536 dimensions), Text embedding for similarity search
- `metadata`: JSONB, Chunk-level metadata
- `created_at`: Timestamp

**Relationships**:
- Many-to-one with Document

## State Transitions

### Conversation Lifecycle
```
NEW → ACTIVE → [ESCALATED | COMPLETED]
  ↑       ↓
  └───────┘
```

- **NEW**: Conversation created, waiting for first message
- **ACTIVE**: Ongoing conversation with message exchange
- **ESCALATED**: Transferred to human agent for complex queries
- **COMPLETED**: Conversation ended by user or system

### Document Processing Pipeline
```
UPLOADED → PROCESSING → CHUNKING → EMBEDDING → INDEXED
    ↑           ↓           ↓          ↓         ↓
    └───────────┴───────────┴──────────┴─────────┘
```

- **UPLOADED**: File uploaded to system
- **PROCESSING**: Text extraction and preprocessing
- **CHUNKING**: Document split into semantic segments
- **EMBEDDING**: Vector generation for each chunk
- **INDEXED**: Available for similarity search

## Validation Rules

### Business Rules
1. **Tenant Isolation**: All queries must include tenant_id for data access
2. **User Context**: Conversations maintain user identity across channel switches
3. **Knowledge Freshness**: Documents must be re-indexed when content changes
4. **Message Limits**: Conversations limited to reasonable message counts for performance

### Data Integrity Constraints
- Tenant IDs must be valid UUIDs and exist in tenant table
- User external_ids must be unique within each channel per tenant
- Document chunks must maintain reference integrity to parent documents
- Conversation context must include channel and user identification

## Performance Considerations

### Indexing Strategy
- **Primary Indexes**: id, tenant_id, created_at on all major tables
- **Composite Indexes**: (tenant_id, user_id) for conversation queries
- **Partial Indexes**: Active conversations only for performance
- **Vector Indexes**: HNSW for fast similarity search in Qdrant

### Partitioning Strategy
- **Time-based Partitioning**: Conversations and messages by month
- **Tenant-based Partitioning**: Knowledge bases by tenant_id for isolation
- **Hot/Cold Storage**: Recent conversations in fast storage, archived in cold storage

## Security Model

### Access Control
- **Row Level Security (RLS)**: PostgreSQL RLS policies enforce tenant isolation
- **API Level Filtering**: All endpoints validate tenant context
- **Audit Logging**: All data access logged with user and tenant context

### Encryption
- **At Rest**: AES-256 encryption for sensitive data fields
- **In Transit**: TLS 1.3 for all database connections
- **Backup Encryption**: Encrypted database backups with key rotation
