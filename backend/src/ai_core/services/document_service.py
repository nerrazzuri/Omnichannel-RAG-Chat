"""
Document processing: chunking and embedding using OpenAI.
"""
from typing import List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from shared.database.models import Document, KnowledgeChunk, KnowledgeBase
from shared.utils.storage import write_metadata
from openai import OpenAI
import os, hashlib, struct, random
import io
import csv
from docx import Document as DocxDocument
from pptx import Presentation
from openpyxl import load_workbook


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def embed(self, inputs: List[str]) -> List[List[float]]:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            # Batch requests to respect OpenAI per-request token limits
            def estimate_tokens(text: str) -> int:
                # Rough heuristic: 4 chars per token
                return max(1, len(text) // 4)

            MAX_TOKENS_PER_REQUEST = 280_000  # keep below 300k limit
            embeddings: List[List[float]] = []
            batch: List[str] = []
            tokens_in_batch = 0
            for t in inputs:
                t_tokens = estimate_tokens(t)
                if batch and tokens_in_batch + t_tokens > MAX_TOKENS_PER_REQUEST:
                    resp = self.client.embeddings.create(
                        model="text-embedding-3-small",
                        input=batch,
                    )
                    embeddings.extend([d.embedding for d in resp.data])
                    batch = []
                    tokens_in_batch = 0
                batch.append(t)
                tokens_in_batch += t_tokens

            if batch:
                resp = self.client.embeddings.create(
                    model="text-embedding-3-small",
                    input=batch,
                )
                embeddings.extend([d.embedding for d in resp.data])

            return embeddings
        # Fallback deterministic embedding (no external dependency)
        vectors: List[List[float]] = []
        dim = 256
        for text in inputs:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            # Expand hash deterministically
            rnd = random.Random(h)
            vec = [rnd.uniform(-1.0, 1.0) for _ in range(dim)]
            vectors.append(vec)
        return vectors

    def process_and_store(self, tenant_id: str, title: str, content: str, knowledge_base_id: str) -> Tuple[str, int]:
        try:
            # Validate tenant_id is a valid UUID
            import uuid
            try:
                uuid.UUID(tenant_id)
            except ValueError:
                raise ValueError(f"Invalid tenant_id: {tenant_id}. Must be a valid UUID.")
            
            # Ensure a knowledge base exists for this tenant
            kb_id = self._get_or_create_knowledge_base(tenant_id, knowledge_base_id)

            # Create document
            doc = Document(title=title, content=content, knowledge_base_id=kb_id, status="PROCESSING")
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)

            # Chunk and embed
            chunks = chunk_text(content)
            if not chunks:
                raise ValueError("No chunks could be created from the content")
            
            embeddings = self.embed(chunks)

            # Store chunks
            for idx, (chunk_text_val, emb) in enumerate(zip(chunks, embeddings)):
                kc = KnowledgeChunk(document_id=doc.id, content=chunk_text_val, chunk_index=idx, embedding=emb)
                self.db.add(kc)
            doc.status = "INDEXED"
            doc.chunk_count = len(chunks)
            self.db.add(doc)
            self.db.commit()
            
            # Write metadata.json for downstream processing
            metadata: Dict[str, Any] = {
                "tenant_id": tenant_id,
                "document_id": str(doc.id),
                "knowledge_base_id": kb_id,
                "title": title,
                "chunk_count": doc.chunk_count,
                "status": doc.status,
            }
            base_path = os.getenv("DOCUMENT_STORAGE_PATH", os.path.join(os.getcwd(), "storage"))
            try:
                write_metadata(base_path, tenant_id, str(doc.id), metadata)
            except Exception as e:
                # Log but don't fail if metadata write fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to write metadata: {e}")
            
            return str(doc.id), len(chunks)
        except Exception as e:
            # If there's an error, rollback the transaction
            self.db.rollback()
            raise

    def _get_or_create_knowledge_base(self, tenant_id: str, provided_kb_id: str) -> str:
        import uuid
        
        # Validate tenant_id
        try:
            tenant_uuid = uuid.UUID(tenant_id)
        except ValueError:
            raise ValueError(f"Invalid tenant_id format: {tenant_id}")
        
        # If a valid kb id is provided and exists, use it
        if provided_kb_id and provided_kb_id != "00000000-0000-0000-0000-000000000000":
            try:
                kb_uuid = uuid.UUID(provided_kb_id)
                kb = self.db.get(KnowledgeBase, kb_uuid)
                if kb:
                    return str(kb.id)
            except ValueError:
                # Invalid UUID format, skip
                pass

        # Try to find default KB for tenant
        kb = (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.tenant_id == tenant_uuid)
            .order_by(KnowledgeBase.created_at.asc())
            .first()
        )
        if kb:
            return str(kb.id)

        # Create a new knowledge base for this tenant
        new_kb = KnowledgeBase(tenant_id=tenant_uuid, name="Default", status="ACTIVE", document_count=0)
        self.db.add(new_kb)
        self.db.commit()
        self.db.refresh(new_kb)
        return str(new_kb.id)

    def extract_text_from_file(self, filename: str, data: bytes) -> str:
        name = filename.lower()
        if name.endswith('.txt') or name.endswith('.csv'):
            try:
                return data.decode('utf-8')
            except Exception:
                return data.decode('latin-1', errors='ignore')
        if name.endswith('.docx'):
            buf = io.BytesIO(data)
            d = DocxDocument(buf)
            return '\n'.join(p.text for p in d.paragraphs)
        if name.endswith('.pptx'):
            buf = io.BytesIO(data)
            prs = Presentation(buf)
            texts: List[str] = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, 'text'):
                        texts.append(shape.text)
            return '\n'.join(texts)
        if name.endswith('.xlsx'):
            buf = io.BytesIO(data)
            wb = load_workbook(buf, data_only=True)
            texts: List[str] = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    texts.append('\t'.join('' if v is None else str(v) for v in row))
            return '\n'.join(texts)
        # PDF handled by PyPDF2
        if name.endswith('.pdf'):
            from PyPDF2 import PdfReader
            buf = io.BytesIO(data)
            reader = PdfReader(buf)
            texts: List[str] = []
            for page in reader.pages:
                texts.append(page.extract_text() or '')
            return '\n'.join(texts)
        # Fallback raw decode
        try:
            return data.decode('utf-8')
        except Exception:
            return data.decode('latin-1', errors='ignore')

    def extract_rows_from_file(self, filename: str, data: bytes) -> List[str]:
        name = filename.lower()
        rows: List[str] = []
        if name.endswith('.csv'):
            try:
                text = data.decode('utf-8-sig', errors='ignore')
            except Exception:
                text = data.decode('latin-1', errors='ignore')
            reader = csv.reader(io.StringIO(text))
            # Re-serialize each row via csv.writer to preserve quoting and commas inside fields
            for r in reader:
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(r)
                rows.append(buf.getvalue().strip('\n'))
        elif name.endswith('.xlsx'):
            buf = io.BytesIO(data)
            wb = load_workbook(buf, data_only=True)
            for ws in wb.worksheets:
                for r in ws.iter_rows(values_only=True):
                    # Use csv.writer to serialize each row consistently
                    buf_row = io.StringIO()
                    writer = csv.writer(buf_row)
                    writer.writerow(['' if v is None else v for v in r])
                    rows.append(buf_row.getvalue().strip('\n'))
        return rows

    def process_rows_and_store(self, tenant_id: str, title: str, rows: List[str], knowledge_base_id: str) -> Tuple[str, int]:
        try:
            # Validate tenant_id
            import uuid
            try:
                uuid.UUID(tenant_id)
            except ValueError:
                raise ValueError(f"Invalid tenant_id: {tenant_id}. Must be a valid UUID.")
            
            if not rows:
                raise ValueError("No rows provided to process")
            
            kb_id = self._get_or_create_knowledge_base(tenant_id, knowledge_base_id)
            preview = '\n'.join(rows[:5]) + ('\n...' if len(rows) > 5 else '')
            doc = Document(title=title, content=preview, knowledge_base_id=kb_id, status="PROCESSING")
            
            # Capture header columns if present (first row)
            if rows:
                try:
                    header_reader = csv.reader(io.StringIO(rows[0]))
                    header = next(header_reader)
                    doc.meta = {"columns": [h.strip().lower() for h in header]}
                    # If first row is header, skip it for chunk storage
                    data_rows = rows[1:]
                except Exception:
                    data_rows = rows
            else:
                data_rows = rows
            
            if not data_rows:
                raise ValueError("No data rows found after header extraction")
            
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)

            embeddings = self.embed(data_rows)
            for idx, (row_text, emb) in enumerate(zip(data_rows, embeddings)):
                kc = KnowledgeChunk(document_id=doc.id, content=row_text, chunk_index=idx, embedding=emb)
                self.db.add(kc)
            doc.status = "INDEXED"
            doc.chunk_count = len(data_rows)
            self.db.add(doc)
            self.db.commit()

            metadata: Dict[str, Any] = {
                "tenant_id": tenant_id,
                "document_id": str(doc.id),
                "knowledge_base_id": kb_id,
                "title": title,
                "chunk_count": doc.chunk_count,
                "status": doc.status,
            }
            base_path = os.getenv("DOCUMENT_STORAGE_PATH", os.path.join(os.getcwd(), "storage"))
            try:
                write_metadata(base_path, tenant_id, str(doc.id), metadata)
            except Exception as e:
                # Log but don't fail if metadata write fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to write metadata: {e}")
            
            return str(doc.id), len(rows)
        except Exception as e:
            # Rollback on error
            self.db.rollback()
            raise


