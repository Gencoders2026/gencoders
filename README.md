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
