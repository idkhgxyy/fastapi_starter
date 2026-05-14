from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_active_user
from app.schemas.rag import DocumentResponse, RAGQueryRequest, RAGQueryResponse
from app.services.rag_service import RAGService
from app.services.llm_service import get_llm_client
from app.core.config import settings
from app.services.llm_observability_service import create_llm_call_log, elapsed_ms, extract_usage, start_timer
from app.worker.tasks import process_document_task
from app.utils.file_parser import parse_file, get_supported_extensions

router = APIRouter()

SUPPORTED_EXTENSIONS = get_supported_extensions()
SUPPORTED_EXT_TEXT = ", ".join(SUPPORTED_EXTENSIONS)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="上传文档并异步构建知识库（支持 .txt / .md / .pdf）",
    tags=["RAG"],
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    上传文档（支持 .txt / .md / .pdf），先解析并保存纯文本内容，再异步执行切分和向量化。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    name_lower = file.filename.lower()
    if not any(name_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {SUPPORTED_EXT_TEXT}",
        )

    raw_bytes = await file.read()

    try:
        parsed = parse_file(file.filename, raw_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    if not parsed.plain_text.strip():
        raise HTTPException(status_code=400, detail="File contains no extractable text.")

    rag_service = RAGService(db)
    doc = None
    try:
        doc = rag_service.create_document_record(
            filename=file.filename,
            file_type=parsed.file_type,
            content=parsed.plain_text,
            owner_id=current_user.id,
        )
        task = process_document_task.delay(doc.id)
        doc = rag_service.attach_processing_task(
            document_id=doc.id,
            owner_id=current_user.id,
            task_id=task.id,
        )
        return doc
    except Exception as e:
        if doc is not None:
            rag_service.mark_document_failed(document_id=doc.id, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


@router.get("/documents", response_model=list[DocumentResponse], summary="查看当前用户的知识库文档", tags=["RAG"])
async def list_documents(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    rag_service = RAGService(db)
    return rag_service.list_documents_for_user(owner_id=current_user.id)


@router.get("/documents/{document_id}", response_model=DocumentResponse, summary="查看文档处理状态", tags=["RAG"])
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    rag_service = RAGService(db)
    document = rag_service.get_document_for_user(document_id=document_id, owner_id=current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


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
        chunks = await rag_service.retrieve_relevant_chunks(
            query=request.query,
            owner_id=current_user.id,
            top_k=request.top_k,
        )
        
        if not chunks:
            return RAGQueryResponse(
                query=request.query,
                answer="知识库中暂无已处理完成的相关文档，请先上传文档并等待处理完成。",
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
