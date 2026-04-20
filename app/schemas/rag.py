from pydantic import BaseModel
from typing import List, Optional

class DocumentResponse(BaseModel):
    id: int
    filename: str
    content: str
    chunks_count: int

    class Config:
        from_attributes = True

class RAGQueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 3

class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    source_chunks: List[str]
