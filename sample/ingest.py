import sys, types
if sys.platform == "win32" and "pwd" not in sys.modules:
    sys.modules["pwd"] = types.SimpleNamespace(getpwuid=lambda uid: ("user", "user", "user", "user"))

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import pandas as pd
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

# 🆕 Modern LangChain imports (no deprecation warnings)
try:
    # Newer LangChain Community structure (>=0.2.10)
    from langchain_community.document_loaders.pdf import PyPDFLoader
    from langchain_community.document_loaders.word_document import Docx2txtLoader
    from langchain_community.document_loaders.csv_loader import CSVLoader
    from langchain_community.document_loaders.excel import UnstructuredExcelLoader
    from langchain_community.document_loaders.text import TextLoader
except ModuleNotFoundError:
    # Fallback for slightly older releases (<0.2.10)
    from langchain_community.document_loaders import (
        PyPDFLoader,
        Docx2txtLoader,
        CSVLoader,
        UnstructuredExcelLoader,
        TextLoader,
    )

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

# ----------------------------------------------------------
# ⚙️ 1️⃣ Setup
# ----------------------------------------------------------
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "enterprise_data"
CHROMA_PATH = BASE_DIR / "chroma_db"
INDEX_LOG = BASE_DIR / "index_log.json"

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
BATCH_SIZE = 100
MAX_WORKERS = 5

# ----------------------------------------------------------
# 🧱 Helper: Metadata + Hashing
# ----------------------------------------------------------
def file_hash(path: Path):
    """Compute a short hash to detect changes."""
    stat = path.stat()
    content = f"{path.name}-{stat.st_size}-{stat.st_mtime}"
    return hashlib.md5(content.encode()).hexdigest()

def load_index_log():
    if INDEX_LOG.exists():
        with open(INDEX_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_index_log(log):
    with open(INDEX_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

def sanitize_metadata(meta: dict) -> dict:
    """Ensure all metadata values are Chroma-safe primitives."""
    clean_meta = {}
    for k, v in meta.items():
        if isinstance(v, (list, dict)):
            clean_meta[k] = json.dumps(v, ensure_ascii=False)
        elif not isinstance(v, (str, int, float, bool)) and v is not None:
            clean_meta[k] = str(v)
        else:
            clean_meta[k] = v
    return clean_meta

# ----------------------------------------------------------
# 🧩 Loaders
# ----------------------------------------------------------
def load_file(path: Path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        loader = PyPDFLoader(str(path))
        return loader.load()
    elif ext == ".docx":
        try:
            loader = Docx2txtLoader(str(path))
            return loader.load()
        except Exception:
            text = Path(path).read_text(errors="ignore")
            return [Document(page_content=text, metadata={"source": path.name})]
    elif ext == ".csv":
        loader = CSVLoader(file_path=str(path))
        return loader.load()
    elif ext == ".xlsx":
        sheets = pd.read_excel(path, sheet_name=None)
        text = ""
        for name, df in sheets.items():
            text += f"\n=== Sheet: {name} ===\n"
            text += df.to_string(index=False)
        return [Document(page_content=text, metadata={"source": path.name})]
    else:
        loader = TextLoader(str(path), encoding="utf-8")
        return loader.load()

# ----------------------------------------------------------
# 🧠 Chunking
# ----------------------------------------------------------
def chunk_documents(docs, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    return splitter.split_documents(docs)

# ----------------------------------------------------------
# ⚡ Batch Embedding
# ----------------------------------------------------------
def embed_in_batches(chunks, embeddings, batch_size=BATCH_SIZE):
    """Parallel batched embeddings using ThreadPoolExecutor."""
    all_vectors = []
    batches = [chunks[i:i+batch_size] for i in range(0, len(chunks), batch_size)]

    def embed_batch(batch):
        return embeddings.embed_documents([c.page_content for c in batch])

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(embed_batch, batch): batch for batch in batches}
        for future in as_completed(futures):
            try:
                vectors = future.result()
                all_vectors.extend(vectors)
            except Exception as e:
                print(f"⚠️ Batch embedding failed: {e}")
    return all_vectors

# ----------------------------------------------------------
# 🚀 Ingestion Pipeline
# ----------------------------------------------------------
def ingest():
    """Incrementally ingests new or modified files into the Chroma vector store."""

    # --- 1️⃣ Initialize embeddings + Chroma vector DB ---
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", tiktoken_model_name="cl100k_base")
    vectordb = Chroma(
        persist_directory=str(CHROMA_PATH),
        embedding_function=embeddings
    )

    index_log = load_index_log()
    all_docs = []

    # --- 2️⃣ Iterate through all files and subfolders ---
    for item in DATA_PATH.iterdir():
        if item.name == "metadata.json":
            continue

        if item.is_file():
            files = [item]
        elif item.is_dir():
            files = [f for f in item.iterdir() if f.is_file()]
        else:
            continue

        for file in files:
            try:
                fhash = file_hash(file)

                # Skip unchanged files based on hash
                if index_log.get(file.name) == fhash:
                    print(f"⏩ Skipping {file.name} (unchanged)")
                    continue

                # Load and sanitize documents
                docs = load_file(file)
                for d in docs:
                    d.metadata = sanitize_metadata(d.metadata)
                    d.metadata["source"] = file.name
                    d.metadata["path"] = str(file.relative_to(DATA_PATH))

                all_docs.extend(docs)
                index_log[file.name] = fhash
                print(f"✅ Loaded {file.name} ({len(docs)} docs)")

            except Exception as e:
                print(f"⚠️ Skipped {file.name} due to {e}")

    # --- 3️⃣ Skip if nothing new ---
    if not all_docs:
        print("✅ No new or updated documents to process.")
        return

    # --- 4️⃣ Chunk documents ---
    print(f"\n📚 Total new documents: {len(all_docs)}")
    print("🧩 Splitting into chunks...")
    chunks = chunk_documents(all_docs)
    print(f"✅ Generated {len(chunks)} chunks")

    # --- 5️⃣ Batch embedding (safe for rate limits) ---
    print("🔢 Creating embeddings in parallel...")
    vectors = embed_in_batches(chunks, embeddings)
    print(f"✅ Embedded {len(vectors)} vectors")

    # --- 6️⃣ Store in Chroma vector DB ---
    print("💾 Storing in Chroma vector DB...")

    # ✅ Modern Chroma does not use `.persist()` or `embeddings` arg in add_texts
    vectordb.add_texts(
        texts=[c.page_content for c in chunks],
        metadatas=[c.metadata for c in chunks],
    )

    # Data automatically persisted when `persist_directory` is defined
    print(f"\n🚀 Ingestion complete. Vector DB saved at: {CHROMA_PATH}")

    # --- 7️⃣ Update local index log ---
    save_index_log(index_log)
    print("🗂️ Index log updated successfully.")

# ----------------------------------------------------------
# 🏁 Entry
# ----------------------------------------------------------
if __name__ == "__main__":
    ingest()
