import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError(
        "GROQ_API_KEY not found in .env"
    )


llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=api_key,
    temperature=0.2
)


def generate_answer(query, results):

    context = "\n\n".join(
        result["text"]
        for result in results
    )

    prompt = f"""
You are an AI customer support assistant.

Your job is to answer the user's support question
using the provided knowledge base.

IMPORTANT RULES:

1. Use the knowledge base as the primary source
   for support-related questions.

2. Do not invent policies, prices, procedures,
   or company information.

3. If the requested support information is not
   available in the context, politely explain that
   the information is not available.

4. Give a clear, natural and helpful answer.

5. Do not mention "retrieved chunks", "FAISS",
   "embeddings", or internal technical details.

Knowledge Base Context:
------------------------
{context}
------------------------

User Question:
{query}

Answer:
"""

    response = llm.invoke(prompt)

    return response.content.strip()