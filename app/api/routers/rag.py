from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.schemas.rag import DocumentResponse, RAGQueryRequest, RAGQueryResponse
from app.services.rag_service import RAGService
from app.services.llm_service import get_llm_client
from app.core.config import settings
from app.services.llm_observability_service import create_llm_call_log, elapsed_ms, extract_usage, start_timer

router = APIRouter()

@router.post("/upload", response_model=DocumentResponse, summary="上传文档并构建知识库", tags=["RAG"])
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _current_user = Depends(get_current_active_user)
):
    """
    上传 .txt 等纯文本文档。
    服务会自动进行文本切分、Embedding 计算并存入 PostgreSQL (pgvector)。
    """
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported for now.")
    
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 text.")
    
    if not content.strip():
        raise HTTPException(status_code=400, detail="File is empty.")

    rag_service = RAGService(db)
    try:
        doc = await rag_service.process_document(filename=file.filename, content=content)
        return {
            "id": doc.id,
            "filename": doc.filename,
            "content": doc.content,
            "chunks_count": len(doc.chunks)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@router.post("/query", response_model=RAGQueryResponse, summary="基于知识库检索并回答", tags=["RAG"])
async def query_knowledge_base(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    1. 接收用户 Query 并计算向量
    2. 使用 pgvector 检索最相似的文档块 (top_k)
    3. 组装 prompt，调用 LLM (Qwen2.5) 生成答案
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    rag_service = RAGService(db)
    started_at = start_timer()
    try:
        # 1 & 2: 向量化并检索
        chunks = await rag_service.retrieve_relevant_chunks(request.query, request.top_k)
        
        if not chunks:
            return RAGQueryResponse(
                query=request.query,
                answer="知识库中没有找到相关信息。",
                source_chunks=[]
            )
        
        # 3. 组装 Prompt
        context_texts = []
        for i, chunk in enumerate(chunks, 1):
            context_texts.append(f"[相关片段 {i}]:\n{chunk.content}")
            
        context_str = "\n\n".join(context_texts)
        
        system_prompt = (
            "你是一个专业的问答助手。请基于以下提供的参考资料，准确回答用户的问题。\n"
            "如果你不知道答案，或者参考资料中没有相关信息，请直接说明，不要编造。\n\n"
            f"=== 参考资料 ===\n{context_str}\n=== 结束 ==="
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.query}
        ]
        
        llm_client = get_llm_client()
        response = await llm_client.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=messages,
            temperature=0.1,  # 降低 temperature 以保证 RAG 问答的稳定性
        )
        response_text = response.choices[0].message.content
        prompt_tokens, completion_tokens, total_tokens = extract_usage(response)
        create_llm_call_log(
            db,
            user_id=current_user.id,
            endpoint="/api/rag/query",
            prompt=request.query,
            response=response_text,
            tool_calls=None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=elapsed_ms(started_at),
            status="success",
        )
        
        return RAGQueryResponse(
            query=request.query,
            answer=response_text,
            source_chunks=[c.content for c in chunks]
        )
        
    except Exception as e:
        create_llm_call_log(
            db,
            user_id=current_user.id,
            endpoint="/api/rag/query",
            prompt=request.query,
            response=None,
            tool_calls=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=elapsed_ms(started_at),
            status="failed",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")
