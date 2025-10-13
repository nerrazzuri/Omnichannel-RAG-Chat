-- Initial database schema for Omnichannel Enterprise RAG Chatbot Platform
-- Multi-tenant schema design with Row Level Security

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create base schemas
CREATE SCHEMA IF NOT EXISTS tenant_template;
CREATE SCHEMA IF NOT EXISTS public;

-- Create tenant management functions
CREATE OR REPLACE FUNCTION create_tenant_schema(tenant_domain TEXT)
RETURNS TEXT AS $$
DECLARE
    schema_name TEXT := 'tenant_' || tenant_domain;
BEGIN
    EXECUTE format('CREATE SCHEMA %I', schema_name);

    -- Create tables in new schema
    EXECUTE format('
        CREATE TABLE %I.tenants (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(255) NOT NULL,
            domain VARCHAR(255) UNIQUE NOT NULL,
            subscription_tier VARCHAR(50) DEFAULT ''BASIC'',
            settings JSONB DEFAULT ''{}'',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE %I.users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            external_id VARCHAR(255),
            user_type VARCHAR(50) NOT NULL,
            role VARCHAR(50) DEFAULT ''END_USER'',
            preferences JSONB DEFAULT ''{}'',
            last_active_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (tenant_id) REFERENCES %I.tenants(id) ON DELETE CASCADE
        );

        CREATE TABLE %I.conversations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            channel VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT ''ACTIVE'',
            context JSONB DEFAULT ''{}'',
            started_at TIMESTAMP DEFAULT NOW(),
            last_message_at TIMESTAMP DEFAULT NOW(),
            completed_at TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES %I.tenants(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES %I.users(id) ON DELETE CASCADE
        );

        CREATE TABLE %I.messages (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            conversation_id UUID NOT NULL,
            sender_type VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            message_type VARCHAR(50) DEFAULT ''TEXT'',
            metadata JSONB DEFAULT ''{}'',
            timestamp TIMESTAMP DEFAULT NOW(),
            is_processed BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (conversation_id) REFERENCES %I.conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE %I.knowledge_bases (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            tenant_id UUID NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT ''ACTIVE'',
            document_count INTEGER DEFAULT 0,
            last_updated_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (tenant_id) REFERENCES %I.tenants(id) ON DELETE CASCADE
        );

        CREATE TABLE %I.documents (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            knowledge_base_id UUID NOT NULL,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            source_url VARCHAR(500),
            metadata JSONB DEFAULT ''{}'',
            status VARCHAR(50) DEFAULT ''PROCESSING'',
            chunk_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            indexed_at TIMESTAMP,
            FOREIGN KEY (knowledge_base_id) REFERENCES %I.knowledge_bases(id) ON DELETE CASCADE
        );

        CREATE TABLE %I.knowledge_chunks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            document_id UUID NOT NULL,
            content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            embedding VECTOR(1536),
            metadata JSONB DEFAULT ''{}'',
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (document_id) REFERENCES %I.documents(id) ON DELETE CASCADE
        );
    ', schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name, schema_name);

    RETURN schema_name;
END;
$$ LANGUAGE plpgsql;

-- Function to get current tenant context
CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', TRUE)::UUID;
END;
$$ LANGUAGE plpgsql;

-- Enable RLS on all tenant tables
ALTER TABLE tenant_template.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.knowledge_bases ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_template.knowledge_chunks ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for tenant isolation
CREATE POLICY tenant_isolation ON tenant_template.tenants
    FOR ALL USING (id = get_current_tenant_id());

CREATE POLICY user_tenant_isolation ON tenant_template.users
    FOR ALL USING (tenant_id = get_current_tenant_id());

CREATE POLICY conversation_tenant_isolation ON tenant_template.conversations
    FOR ALL USING (tenant_id = get_current_tenant_id());

CREATE POLICY message_tenant_isolation ON tenant_template.messages
    FOR ALL USING (
        conversation_id IN (
            SELECT id FROM tenant_template.conversations
            WHERE tenant_id = get_current_tenant_id()
        )
    );

CREATE POLICY knowledge_base_tenant_isolation ON tenant_template.knowledge_bases
    FOR ALL USING (tenant_id = get_current_tenant_id());

CREATE POLICY document_tenant_isolation ON tenant_template.documents
    FOR ALL USING (
        knowledge_base_id IN (
            SELECT id FROM tenant_template.knowledge_bases
            WHERE tenant_id = get_current_tenant_id()
        )
    );

CREATE POLICY knowledge_chunk_tenant_isolation ON tenant_template.knowledge_chunks
    FOR ALL USING (
        document_id IN (
            SELECT id FROM tenant_template.documents
            WHERE knowledge_base_id IN (
                SELECT id FROM tenant_template.knowledge_bases
                WHERE tenant_id = get_current_tenant_id()
            )
        )
    );

-- Create indexes for performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_users_tenant_id ON tenant_template.users(tenant_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_conversations_tenant_id ON tenant_template.conversations(tenant_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_conversations_user_id ON tenant_template.conversations(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_conversations_status ON tenant_template.conversations(status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_messages_conversation_id ON tenant_template.messages(conversation_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_messages_timestamp ON tenant_template.messages(timestamp);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_documents_knowledge_base_id ON tenant_template.documents(knowledge_base_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_knowledge_bases_tenant_id ON tenant_template.knowledge_bases(tenant_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_template_knowledge_chunks_document_id ON tenant_template.knowledge_chunks(document_id);
