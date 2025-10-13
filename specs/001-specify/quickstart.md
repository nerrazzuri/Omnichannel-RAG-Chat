# Quickstart Guide: Omnichannel Enterprise RAG Chatbot Platform

## Overview

This guide provides a step-by-step setup for the Omnichannel Enterprise RAG Chatbot Platform, enabling rapid development and testing of the conversational AI system.

## Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Memory**: 16GB RAM minimum, 32GB recommended
- **Storage**: 100GB SSD available space
- **Network**: Stable internet connection for external API access

### Software Dependencies
- **Docker**: 20.10+
- **Docker Compose**: 1.29+
- **Git**: 2.30+
- **Python**: 3.11+
- **Node.js**: 20+ (for frontend development)
- **PostgreSQL Client**: 15+

## 1. Environment Setup

### Clone Repository
```bash
git clone <repository-url>
cd omnichannel-chatbot-platform
```

### Configure Environment Variables
```bash
cp .env.example .env
```

Edit `.env` file with your configuration:
```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/chatbot_dev

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# AI Services (Choose one provider)
OPENAI_API_KEY=sk-your-openai-key-here
# OR
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_KEY=your-azure-key-here

# Vector Database
QDRANT_URL=http://localhost:6333

# Authentication
JWT_SECRET=your-jwt-secret-key-min-32-chars
JWT_EXPIRES_IN=1h

# Channel Integrations (Optional for development)
WHATSAPP_VERIFY_TOKEN=your-verify-token
WHATSAPP_ACCESS_TOKEN=your-access-token
TEAMS_APP_ID=your-teams-app-id
TEAMS_APP_SECRET=your-teams-app-secret

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

## 2. Infrastructure Setup

### Start Local Infrastructure
```bash
# Start PostgreSQL, Redis, and Qdrant
docker-compose -f infrastructure/docker-compose.dev.yml up -d

# Verify services are running
docker-compose -f infrastructure/docker-compose.dev.yml ps
```

Expected services:
- **PostgreSQL**: Database for conversations, users, and tenant data
- **Redis**: Session management and caching
- **Qdrant**: Vector database for knowledge embeddings

### Database Setup
```bash
# Run database migrations
cd backend && python -m alembic upgrade head

# Seed initial data (tenants, admin users)
cd backend && python scripts/seed_dev_data.py
```

## 3. Backend Services

### Install Python Dependencies
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

### Start FastAPI Services
```bash
# Start the RAG core service
uvicorn src.ai_core.main:app --reload --host 0.0.0.0 --port 8001

# Start the API gateway service (in another terminal)
uvicorn src.gateway.main:app --reload --host 0.0.0.0 --port 8000
```

### Start Channel Webhook Services
```bash
# Start NestJS webhook handlers (in another terminal)
cd backend/src/channels
npm install
npm run start:dev
```

## 4. Frontend Setup

### Install Node.js Dependencies
```bash
cd frontend
npm install
```

### Start Development Server
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## 5. Knowledge Base Setup

### Upload Sample Documents
```bash
# Using the API directly
curl -X POST http://localhost:8000/v1/tenant/{tenant-id}/upload \
  -H "Authorization: Bearer {your-jwt-token}" \
  -F "files=@docs/sample-product-docs.pdf" \
  -F "metadata={\"category\":\"product_docs\",\"tags\":[\"sample\"]}" \
```

### Verify Document Processing
```bash
# Check upload status
curl http://localhost:8000/v1/tenant/{tenant-id}/knowledge

# Query the system
curl -X POST http://localhost:8000/v1/query \
  -H "Authorization: Bearer {your-jwt-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "{tenant-id}",
    "message": "What are the main product features?",
    "channel": "web"
  }'
```

## 6. Channel Integration Testing

### WhatsApp Testing (Optional)
1. Set up WhatsApp Business API test account
2. Configure webhook URL to `http://localhost:8000/webhooks/whatsapp`
3. Send test messages through WhatsApp

### Microsoft Teams Testing (Optional)
1. Create Teams bot in Azure Bot Service
2. Configure webhook URL to `http://localhost:8000/webhooks/teams`
3. Add bot to Teams channel and send messages

## 7. Development Workflow

### Running Tests
```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend tests
cd frontend && npm test

# Integration tests
cd backend && pytest tests/integration/ -v
```

### Code Quality Checks
```bash
# Backend linting
cd backend && flake8 src/ && mypy src/

# Frontend linting
cd frontend && npm run lint

# Security scanning
cd backend && safety check
```

### Debugging and Monitoring

#### View Application Logs
```bash
# Backend logs
tail -f backend/logs/app.log

# Database logs
docker-compose -f infrastructure/docker-compose.dev.yml logs postgresql
```

#### Monitor System Health
```bash
# Check API health
curl http://localhost:8000/v1/health

# View Grafana dashboard (if configured)
open http://localhost:3001
```

## 8. Troubleshooting

### Common Issues

**Database Connection Issues**:
```bash
# Check if PostgreSQL is running
docker-compose -f infrastructure/docker-compose.dev.yml logs postgresql

# Verify connection string in .env
# Test manual connection
psql $DATABASE_URL
```

**RAG Service Not Responding**:
```bash
# Check if Qdrant is running
docker-compose -f infrastructure/docker-compose.dev.yml logs qdrant

# Verify OpenAI API key is set
echo $OPENAI_API_KEY
```

**Webhook Signature Verification Failing**:
```bash
# Verify webhook secret is correctly set
echo $WHATSAPP_VERIFY_TOKEN

# Check webhook logs for signature details
tail -f backend/logs/webhook.log
```

## 9. Performance Optimization

### Development Optimizations
```bash
# Enable debug logging for troubleshooting
export LOG_LEVEL=DEBUG

# Use smaller embedding models for faster processing
export EMBEDDING_MODEL=text-embedding-3-small

# Enable Redis caching for faster responses
export REDIS_CACHE_TTL=3600
```

### Monitoring Key Metrics
- **Response Time**: Track API response times in application logs
- **Database Performance**: Monitor slow queries in PostgreSQL logs
- **Vector Search Performance**: Monitor Qdrant query times
- **Memory Usage**: Monitor container resource usage

## 10. Next Steps

### Production Deployment
1. Review production environment configurations
2. Set up proper secret management (Vault/KMS)
3. Configure monitoring and alerting (Prometheus/Grafana)
4. Set up CI/CD pipelines (GitHub Actions)

### Advanced Features
1. **Multi-tenant Configuration**: Set up additional tenants for testing
2. **Custom Knowledge Bases**: Upload organization-specific documents
3. **Channel Integration**: Connect real WhatsApp/Teams accounts
4. **Analytics Dashboard**: Enable usage tracking and reporting

### Getting Help
- **Documentation**: Check `/docs` directory for detailed guides
- **API Documentation**: Visit `http://localhost:8000/docs` for interactive API docs
- **Architecture Guide**: Review `docs/architecture-guide.md` for system overview

This quickstart guide gets you up and running with a local development environment. For production deployment, refer to the infrastructure documentation in `/infrastructure`.
