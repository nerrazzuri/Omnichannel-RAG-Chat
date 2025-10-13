import React from 'react';

const HomePage: React.FC = () => {
  return (
    <div style={{
      fontFamily: 'Arial, sans-serif',
      maxWidth: '800px',
      margin: '0 auto',
      padding: '20px',
      backgroundColor: '#f5f5f5',
      minHeight: '100vh'
    }}>
      <header style={{
        backgroundColor: '#007acc',
        color: 'white',
        padding: '20px',
        borderRadius: '8px',
        marginBottom: '20px'
      }}>
        <h1>Omnichannel Enterprise RAG Chatbot Platform</h1>
        <p>Frontend Application - Development Mode</p>
      </header>

      <main style={{
        backgroundColor: 'white',
        padding: '20px',
        borderRadius: '8px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <h2>🚀 Services Status</h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginTop: '20px' }}>
          <div style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '5px' }}>
            <h3>AI Core Service</h3>
            <p>Status: <span style={{ color: '#28a745' }}>✅ Running</span></p>
            <p>Port: 8000</p>
            <p>Endpoint: /v1/health</p>
          </div>

          <div style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '5px' }}>
            <h3>Gateway Service</h3>
            <p>Status: <span style={{ color: '#28a745' }}>✅ Running</span></p>
            <p>Port: 3001</p>
            <p>Endpoint: /api/health</p>
          </div>

          <div style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '5px' }}>
            <h3>Frontend Service</h3>
            <p>Status: <span style={{ color: '#28a745' }}>✅ Running</span></p>
            <p>Port: 3000</p>
            <p>Framework: Next.js</p>
          </div>
        </div>

        <div style={{ marginTop: '30px', padding: '20px', backgroundColor: '#e9ecef', borderRadius: '5px' }}>
          <h3>📋 Implementation Status</h3>
          <p><strong>Phase 1 (Setup):</strong> ✅ Complete - Project structure, dependencies, Docker builds</p>
          <p><strong>Phase 2 (Foundational):</strong> ✅ Complete - Database, authentication, caching, logging</p>
          <p><strong>Next Steps:</strong> Begin User Story 1 implementation (Customer Inquiry Resolution)</p>
        </div>

        <div style={{ marginTop: '20px' }}>
          <h3>🔧 Development Commands</h3>
          <pre style={{
            backgroundColor: '#f8f9fa',
            padding: '15px',
            borderRadius: '5px',
            overflow: 'auto'
          }}>
{`# Start all services
docker-compose up

# Start individual services
cd backend && python src/ai_core/main.py
cd gateway && npm run start:dev
cd frontend && npm run dev

# Run tests
cd backend && python -m pytest tests/
cd gateway && npm test
`}
          </pre>
        </div>
      </main>

      <footer style={{
        marginTop: '20px',
        textAlign: 'center',
        color: '#6c757d',
        padding: '10px'
      }}>
        <p>Omnichannel Enterprise RAG Chatbot Platform - Frontend Dashboard</p>
        <p>Implementation Status: ✅ Foundation Complete | 🚧 User Stories In Progress</p>
      </footer>
    </div>
  );
};

export default HomePage;
