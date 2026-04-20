import asyncio
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select
from openai import AsyncOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.core.logging import logger

# Initialize OpenAI client for SiliconFlow
openai_client = AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL
)

class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", " ", ""]
        )

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """调用 Embedding API 获取向量表示"""
        try:
            # 去除多余的空格，减少无意义 token
            texts = [text.replace("\n", " ") for text in texts]
            response = await openai_client.embeddings.create(
                input=texts,
                model=settings.EMBEDDING_MODEL_NAME
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            raise e

    async def process_document(self, filename: str, content: str) -> Document:
        """处理文档：切分、生成向量并存入数据库"""
        # 1. 存入主文档表
        db_doc = Document(filename=filename, content=content)
        self.db.add(db_doc)
        self.db.flush()  # 获取 db_doc.id

        # 2. 文本切分
        chunks = self.text_splitter.split_text(content)
        if not chunks:
            self.db.commit()
            return db_doc

        # 3. 批量获取向量 (如果 chunks 很多可以分批调用，这里简化直接全量)
        # 为避免 API 超时，分批处理
        batch_size = 10
        embeddings = []
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_embeddings = await self.get_embeddings(batch_chunks)
            embeddings.extend(batch_embeddings)

        # 4. 存入向量表
        db_chunks = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            db_chunk = DocumentChunk(
                document_id=db_doc.id,
                chunk_index=idx,
                content=chunk_text,
                embedding=embedding
            )
            db_chunks.append(db_chunk)
            
        self.db.add_all(db_chunks)
        self.db.commit()
        self.db.refresh(db_doc)
        
        return db_doc

    async def retrieve_relevant_chunks(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        """根据 query 检索最相关的 DocumentChunks"""
        # 1. 对 query 生成向量
        query_embeddings = await self.get_embeddings([query])
        query_vector = query_embeddings[0]

        # 2. 向量检索 (L2 距离)
        # <=> 为 cosine distance, <-> 为 L2 distance, <#> 为 inner product
        # pgvector 推荐标准化后用 cosine distance
        stmt = select(DocumentChunk).order_by(
            DocumentChunk.embedding.cosine_distance(query_vector)
        ).limit(top_k)
        
        result = self.db.execute(stmt)
        return result.scalars().all()
