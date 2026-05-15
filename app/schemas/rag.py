from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    chunks_count: int
    processing_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = Field(3, ge=1, le=10)


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    source_chunks: List[str]
