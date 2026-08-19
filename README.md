# 🤖 EduBot — AI-Powered Educational Chatbot

<p align="center">
  <strong>A production-quality hybrid AI chatbot with Intelligent Routing & RAG</strong><br>
  Hybrid AI + Knowledge Base • Intelligent Routing • Source-Cited Answers • Streaming Responses
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/LangChain-0.3-green" alt="LangChain" />
  <img src="https://img.shields.io/badge/FAISS-Vector%20DB-orange" alt="FAISS" />
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License" />
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **Hybrid AI Mode** | Answers from general knowledge OR knowledge base documents — automatically decides |
| 🔀 **Intelligent Routing** | Semantic similarity scoring determines whether to use RAG or direct LLM |
| 🔍 **RAG (Retrieval-Augmented Generation)** | Upload PDFs, DOCX, and TXT files — answers grounded in your documents |
| 💬 **Streaming Responses** | Real-time token-by-token output via Server-Sent Events |
| 🧵 **Conversation Memory** | Multi-turn conversations with windowed context across both modes |
| 📄 **Source Citations** | Every RAG answer cites the document name, page number, and confidence score |
| 💡 **Answer Mode Indicator** | Clearly shows whether the answer came from knowledge base (📚) or general knowledge (💡) |
| 🔒 **Admin Knowledge Base** | Admin-only document management — students just ask questions |
| 📁 **Multi-Format Ingestion** | Supports PDF, DOCX, and TXT document uploads |
| 📜 **Chat History** | All conversations are saved and can be reviewed later |
| 🎨 **Modern UI** | Dark theme with glassmorphism, gradients, and micro-animations |
| 🐳 **Docker Ready** | One-command deployment with Docker Compose |

---

## 🏗️ Architecture

```
┌─────────────────┐     HTTP/SSE      ┌──────────────────────────────────────────┐
│                 │  ◄──────────────►  │            FastAPI Backend               │
│  React Frontend │                   │                                          │
│  (Vite)         │                   │  API ──► Chat Service ──► RAG Engine     │
│                 │                   │              │         (Intelligent       │
│  • Chat UI      │                   │         Memory Mgr    Router)            │
│  • No uploads   │                   │              │         ↙      ↘          │
│  • Mode badges  │                   │          SQLite    FAISS   Groq LLM     │
└─────────────────┘                   │                                          │
                                      │  Admin API ──► Document Processor        │
                                      │                    ↓                     │
                                      │               PDF/DOCX/TXT → Chunks     │
                                      └──────────────────────────────────────────┘
```

### How Intelligent Routing Works

```
User Question
      ↓
Search FAISS for relevant document chunks
      ↓
Check semantic similarity scores
      ↓
┌─────────────────────┐     ┌─────────────────────┐
│ Score ≥ threshold    │     │ Score < threshold    │
│ → RAG Mode           │     │ → Direct LLM Mode   │
│ • Answer from docs  │     │ • Answer from LLM    │
│ • Include citations │     │ • General knowledge  │
│ • 📚 Knowledge base │     │ • 💡 General knowledge│
└─────────────────────┘     └─────────────────────┘
```

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------"|
| Frontend | React + Vite | Chat interface with SSE streaming |
| Backend | FastAPI (Python) | REST API with async support |
| RAG | LangChain | Document retrieval and prompt construction |
| Vector DB | FAISS | Semantic similarity search |
| Embeddings | all-MiniLM-L6-v2 | Local text embedding (384 dimensions) |
| LLM | Groq (Llama 3.1 8B) | Ultra-fast free inference |
| Database | SQLite (PostgreSQL-ready) | Chat history and document metadata |
| Deployment | Docker Compose | Containerized deployment |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** ([Download](https://python.org/downloads))
- **Node.js 18+** ([Download](https://nodejs.org))
- **Groq API Key** (free at [console.groq.com](https://console.groq.com))

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-chatbot.git
cd ai-chatbot
```

### 2. Backend Setup

```bash
# Create a virtual environment
cd backend
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
copy ..\.env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 3. Frontend Setup

```bash
cd ../frontend
npm install

# Create .env file
copy .env.example .env
```

### 4. Run the Application

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

### 5. Open in Browser

- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health

---

## 📡 API Endpoints

### Student-Facing (No Auth Required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send a message (SSE streaming response) |
| `GET` | `/api/documents` | List knowledge base documents (read-only) |
| `GET` | `/api/conversations` | List all conversations |
| `GET` | `/api/conversations/{id}` | Get conversation with messages |
| `GET` | `/api/health` | Health check |

### Admin-Only (Requires `X-Admin-Key` Header)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/admin/documents/upload` | Upload PDF, DOCX, or TXT to knowledge base |
| `GET` | `/api/admin/documents` | List all documents with status |
| `DELETE` | `/api/admin/documents/{id}` | Delete a document |
| `POST` | `/api/admin/rebuild-index` | Rebuild FAISS index |
| `GET` | `/api/admin/status` | Knowledge base status |

Full interactive API documentation available at `/docs` (Swagger UI).

### Admin Upload Example (cURL)

```bash
curl -X POST http://localhost:8000/api/admin/documents/upload \
  -H "X-Admin-Key: edubot-admin-key-change-me" \
  -F "file=@./my_notes.pdf"
```

---

## 🔀 Chat Behaviour

EduBot **automatically decides** how to answer each question:

| Question | Mode | Why |
|----------|------|-----|
| "What is Python?" | 💡 Direct LLM | General knowledge — no document needed |
| "Explain Newton's Second Law" | 📚 RAG (if notes exist) or 💡 Direct | Uses docs if relevant notes are indexed |
| "What is PW's scholarship policy?" | 📚 RAG | Organization-specific — retrieved from knowledge base |
| "Write a Python program for Binary Search" | 💡 Direct LLM | Code generation — LLM handles this natively |
| "Summarize Chapter 7 from OS notes" | 📚 RAG | Explicitly references uploaded material |

**No student action required** — students simply ask questions. Admins upload documents once, and the system routes automatically.

---

## 🐳 Docker Deployment

```bash
# Set your API key
# Windows:
set GROQ_API_KEY=your_key_here
# Linux/Mac:
export GROQ_API_KEY=your_key_here

# Build and run
docker-compose up --build
```

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## 📁 Project Structure

```
ai-chatbot/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints (chat, admin, documents, history, health)
│   │   ├── core/         # Business logic (chat service, RAG engine, memory, doc processor)
│   │   ├── models/       # Data models (Pydantic schemas, SQLAlchemy models, enums)
│   │   ├── services/     # External services (LLM, embeddings, FAISS vector store)
│   │   ├── db/           # Database setup (engine, sessions, initialization)
│   │   ├── utils/        # Utilities (logging, exceptions, prompt templates)
│   │   ├── config.py     # Configuration management (env vars)
│   │   └── main.py       # Application entry point (FastAPI)
│   ├── data/             # Runtime data (uploads, vector store, SQLite DB)
│   ├── tests/            # Test suite
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/   # React components (ChatWindow, MessageBubble, etc.)
│   │   ├── hooks/        # Custom hooks (useChat)
│   │   ├── services/     # API client (SSE streaming)
│   │   ├── styles/       # CSS (dark theme, glassmorphism)
│   │   └── utils/        # Constants
│   └── package.json
├── docker-compose.yml
└── README.md
```

---

## ⚙️ Configuration

All settings are configurable via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | (required) | Your Groq API key |
| `LLM_MODEL_NAME` | `llama-3.1-8b-instant` | LLM model to use |
| `LLM_MAX_TOKENS` | `1024` | Max tokens per response |
| `LLM_TEMPERATURE` | `0.7` | Response creativity (0.0–1.0) |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | Local embedding model |
| `RETRIEVAL_TOP_K` | `4` | Number of chunks to retrieve |
| `RAG_SIMILARITY_THRESHOLD` | `0.35` | Routing threshold (0.0–1.0) |
| `MEMORY_WINDOW_SIZE` | `10` | Past messages for context |
| `ADMIN_API_KEY` | `edubot-admin-key-change-me` | Admin endpoint protection |
| `CHUNK_SIZE` | `500` | Document chunk size (chars) |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `DATABASE_URL` | `sqlite:///data/chatbot.db` | Database connection |

---

## 🔄 Switching to PostgreSQL

The app uses SQLite by default. To switch to PostgreSQL for production:

1. Install PostgreSQL
2. Update `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/edubot
   ```
3. Add `asyncpg` to `requirements.txt`:
   ```
   asyncpg==0.30.0
   ```
4. That's it! SQLAlchemy handles the rest.

---

## 🗺️ Future Roadmap

- [ ] User authentication (OAuth2/JWT)
- [ ] Admin dashboard UI
- [ ] Summary memory (compress old conversations)
- [ ] OCR for scanned PDFs
- [ ] Re-ranking retrieved chunks (cross-encoder)
- [ ] Rate limiting
- [ ] WebSocket support
- [ ] Mobile-responsive widget mode
- [ ] Analytics and usage tracking

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file.

---

<p align="center">
  Built with ❤️ by Harsh | Powered by Groq, LangChain & FAISS
</p>
