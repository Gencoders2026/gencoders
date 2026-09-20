# RAG-Based Customer Support Assistant

## Overview

This project is a **Retrieval-Augmented Generation (RAG)** based customer support assistant. It uses a customer-support knowledge base containing information such as refund policies, cancellation policies, privacy policies, and troubleshooting guides.

The system retrieves relevant information from the knowledge base and provides it as context to a Large Language Model (LLM), which then generates a relevant and context-aware response. The application is built using **Streamlit**.

## RAG Workflow

```text
Documents
    ↓
Document Loading
    ↓
Text Cleaning
    ↓
Chunking
    ↓
Embeddings
    ↓
FAISS Vector Database
    ↓
Similarity Search / Retrieval
    ↓
Relevant Context
    ↓
LLM
    ↓
Final Response



➤ Document Processing

The knowledge-base documents are first loaded into the system. The text is cleaned to remove unnecessary content and then divided into smaller sections called chunks. Chunking helps the system retrieve only the relevant part of a document when answering a user’s question.

➤ Embeddings & FAISS

Each text chunk is converted into a numerical representation called an embedding using the all-MiniLM-L6-v2 model from Sentence Transformers.

These embeddings are stored in FAISS (Facebook AI Similarity Search). When a user enters a question, the query is also converted into an embedding. FAISS compares it with the stored embeddings and retrieves the most relevant chunks.

➤ Response Generation

The retrieved information is provided as context to the LLM along with the user’s question. The project uses openai/gpt-oss-20b through Groq to generate the final customer-support response.


➤ Technologies Used

* Python – Core development
* Streamlit – User interface
* LangChain – RAG and LLM integration
* Sentence Transformers – Embedding generation
* all-MiniLM-L6-v2 – Embedding model
* FAISS – Vector storage and similarity search
* Groq – LLM inference
* openai/gpt-oss-20b – Response generation


➤ Project Structure
rag/
├── data/
│   └── knowledge_base/       # Customer-support documents
├── app.py                    # Streamlit application
├── build_index.py            # Builds the vector database
├── chunker.py                # Text chunking
├── document_loader.py        # Document loading
├── embeddings.py             # Embedding generation
├── llm.py                    # LLM configuration
├── retriever.py              # Relevant document retrieval
├── text_cleaner.py           # Text preprocessing
├── vector_store.py           # FAISS vector store
├── requirements.txt          # Project dependencies
└── README.md                 # Project documentation


➤ Installation & Setup
1. Clone the Repository
git clone https://github.com/Gencoders2026/gencoders.git
cd gencoders/rag

2. Create a Virtual Environment
● macOS / Linux:
python3 -m venv venv
source venv/bin/activate
● Windows:
python -m venv venv
venv\Scripts\activate

3. Install Dependencies
pip install -r requirements.txt

4. Configure the API Key
Create a .env file inside the rag/ folder:
GROQ_API_KEY=your_api_key_here

5. Build the Vector Database
Build the local FAISS index from the documents in data/knowledge_base/:
python build_index.py

6. Run the Application
streamlit run app.py

---

# Task 6 — Coaching, Response Suggestion & Escalation Risk Monitoring

## Overview

Task 6 adds a real-time **support-assistance module** on top of the
existing agents (Intent & Sentiment Analysis, Customer Simulator and the
RAG Knowledge Recommendation agent). It provides:

* **Coaching & Response Suggestion Agent** — generates context-aware
  response suggestions using customer intent, sentiment, conversation
  history and knowledge-base results, evaluates them for tone /
  clarity / empathy / professionalism, and provides actionable
  communication coaching tips.
* **Escalation Risk Monitor Agent** — continuously recalculates an
  escalation-risk score (0–100) after every customer message, identifies
  indicators (repeated complaints, high frustration, negative sentiment
  streaks, unresolved issues, supervisor requests, legal / reputation
  threats), classifies conversations into **Low / Medium / High /
  Critical**, explains the reasoning, and raises a configurable alert
  with recommended actions (acknowledge frustration, change approach,
  or escalate to a human agent).

## Pipeline

```text
Customer message
    ↓
Intent & Sentiment Analysis Agent   (analysis_core.py)
    ↓
Knowledge Recommendation Agent      (knowledge_bridge.py → rag/ FAISS)
    ↓
Coaching & Response Suggestion Agent(support_assist.py)
    ↓
Escalation Risk Monitor Agent       (support_assist.py, session-aware)
    ↓
Combined payload → Support Console UI
```

## New backend endpoints (FastAPI, port 8000)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/support/analyze` | Full integrated pipeline (session-aware escalation state) |
| POST | `/coaching/evaluate` | Evaluate a drafted response (tone/clarity/empathy/professionalism) |
| GET  | `/escalation/threshold` | View the alert threshold and risk bands |
| POST | `/escalation/threshold` | Update the configurable alert threshold (0–100) |
| GET  | `/escalation/{session_id}` | Escalation-monitor state snapshot for a session |
| POST | `/analyze` | Legacy endpoint, now enriched with knowledge + suggestions |

Risk levels: **Low** 0–24 · **Medium** 25–49 · **High** 50–74 ·
**Critical** 75–100. The alert threshold defaults to **70** (env:
`ESCALATION_ALERT_THRESHOLD`) and can be changed at runtime from the UI
or via `POST /escalation/threshold`.

## Frontend

The React Support Console (`frontend/`, Vite + React Router) now shows:

* 🚨 an **escalation alert banner** with recommended actions when the
  configurable threshold is reached,
* a **Suggested Response** card (context-aware reply + "Use this
  response" + quality-check bars for tone/clarity/empathy/professionalism),
* an **Escalation Risk Monitor** card (risk badge, score bar, indicator
  chips, reasoning, alert-threshold configurator),
* a **"Check my draft"** button that evaluates the agent's typed reply
  before it is sent.

## Running Task 6

```bash
# 1. Backend (FastAPI + support agents + RAG bridge)
cd customer_simulator
python -m uvicorn api:app --host 127.0.0.1 --port 8000

# 2. Frontend (Support Console)
cd frontend
npm install
npm run dev          # http://localhost:5173

# 3. Tests (25 checks: agents + API pipeline)
cd customer_simulator
python -m pytest test_support_assist.py -v
```

### Files

```
customer_simulator/
├── analysis_core.py          # Intent & Sentiment Analysis core
├── knowledge_bridge.py       # Knowledge Recommendation (RAG) bridge
├── support_assist.py         # Coaching agent + Escalation Risk Monitor
├── api.py                    # FastAPI endpoints incl. /support/analyze
└── test_support_assist.py    # 25 pytest checks
frontend/src/
├── services/supportAssistService.js
└── pages/SupportConsole.jsx  # alert banner, suggestion card, monitor card
```
