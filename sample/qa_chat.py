import os
from pathlib import Path
from dotenv import load_dotenv
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# ----------------------------------------------------------
# ⚙️ 1️⃣ Environment Setup
# ----------------------------------------------------------
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_PATH = BASE_DIR / "chroma_db"

# ----------------------------------------------------------
# 🧩 2️⃣ Initialize Components
# ----------------------------------------------------------
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

vectordb = Chroma(
    persist_directory=str(CHROMA_PATH),
    embedding_function=embeddings
)

llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.3)

# ----------------------------------------------------------
# 🧠 3️⃣ Prompt Template
# ----------------------------------------------------------
PROMPT_TEMPLATE = """
You are a professional corporate assistant with access to internal company documents.

Use the information from the CONTEXT below to answer the QUESTION as accurately and helpfully as possible.
If the answer can be inferred or summarized from the context, provide it clearly.
If the context truly lacks the relevant information, reply with:
"I don’t have that information in the current database."

Always include short source citations at the end.

---
CONTEXT:
{context}
---
QUESTION:
{question}
---
Answer:
"""

prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=PROMPT_TEMPLATE
)

qa_chain = LLMChain(llm=llm, prompt=prompt)

# ----------------------------------------------------------
# 🔍 4️⃣ Retrieval
# ----------------------------------------------------------
def retrieve_docs(user_query, k=6):
    """
    Retrieve top-k relevant chunks for a query.
    """
    results = vectordb.similarity_search(user_query, k=k)
    return results

# ----------------------------------------------------------
# 🧠 5️⃣ Generate Answer
# ----------------------------------------------------------
def generate_answer(user_query):
    """
    Generate an answer using retrieved context and GPT reasoning.
    """
    docs = retrieve_docs(user_query, k=6)

    if not docs:
        return "⚠️ No relevant documents found in the knowledge base."

    # Combine retrieved chunks
    context_text = "\n\n".join(d.page_content for d in docs)

    # Modern LangChain call
    result = qa_chain.invoke({
        "context": context_text,
        "question": user_query
    })

    response_text = ""
    if isinstance(result, dict):
        response_text = result.get("text", "").strip()
    else:
        response_text = str(result).strip()

    # Build citation list
    sources = []
    for d in docs:
        src = d.metadata.get("source", "unknown")
        sources.append(src)

    # Remove duplicates and empty values
    sources = sorted(set(s for s in sources if s))
    sources_str = "\n".join(f"• {s}" for s in sources)

    return f"🧠 **Answer:**\n{response_text}\n\n📚 **Sources:**\n{sources_str}"

# ----------------------------------------------------------
# 💬 6️⃣ Interactive CLI Chat
# ----------------------------------------------------------
if __name__ == "__main__":
    print("🤖 Enterprise Knowledge Assistant ready.")
    print("Type 'exit' to quit.\n")

    while True:
        query = input("Ask > ").strip()
        if query.lower() in ["exit", "quit"]:
            break

        answer = generate_answer(query)
        print("\n" + answer + "\n" + "-" * 80)
