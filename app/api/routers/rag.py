import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.logging import logger
from app.schemas.rag import DocumentResponse, RAGQueryRequest, RAGQueryResponse
from app.services.cost_guard import budget_reject_message, check_budget
from app.services.llm_observability_service import (
    create_llm_call_log,
    elapsed_ms,
    extract_usage,
    start_timer,
)
from app.services.llm_service import get_llm_client
from app.services.pricing_service import estimate_cost_cny
from app.services.rag_service import RAGService, append_session_message, load_session_history
from app.services.semantic_cache import lookup_semantic_cache, store_semantic_cache
from app.utils.file_parser import get_supported_extensions, legacy_office_error_message, parse_file
from app.worker.tasks import process_document_task

router = APIRouter()

SUPPORTED_EXTENSIONS = get_supported_extensions()
SUPPORTED_EXT_TEXT = ", ".join(SUPPORTED_EXTENSIONS)

# 单个文件上限。pptx/docx 动辄几十 MB，不设限的话一次上传就能把 2G 机器的
# api 容器内存打满（解析时整个文件会读进内存）。
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _sse(payload: dict) -> str:
    """把 dict 包装成一条 SSE data 帧。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="上传文档并异步构建知识库（支持 .txt / .md / .pdf / .docx / .pptx）",
    tags=["RAG"],
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    上传文档（支持 .txt / .md / .pdf / .docx / .pptx），先解析并保存纯文本内容，
    再异步执行切分和向量化。.doc / .ppt 老格式会返回需要另存为新格式的提示。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    if len(file.filename) > 255:
        raise HTTPException(status_code=400, detail="Filename too long (max 255 characters).")

    name_lower = file.filename.lower()

    # 老格式先单独拦：否则会落到下面的白名单分支，用户只看到 "Unsupported file type"
    legacy_message = legacy_office_error_message(file.filename)
    if legacy_message:
        raise HTTPException(status_code=400, detail=legacy_message)

    if not any(name_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Supported: {SUPPORTED_EXT_TEXT}",
        )

    # 只读到上限+1 字节，既能把超限文件挡掉，又不会把整个大文件塞进内存
    raw_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            # 用字面量而不是 status.HTTP_413_*：该常量在新版 Starlette 里改了名，
            # 固定数字可同时兼容 requirements 允许的旧版本
            status_code=413,
            detail=f"文件过大：单个文件上限 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB。",
        )

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


@router.get(
    "/documents",
    response_model=list[DocumentResponse],
    summary="查看当前用户的知识库文档",
    tags=["RAG"],
)
async def list_documents(
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user)
):
    rag_service = RAGService(db)
    return rag_service.list_documents_for_user(owner_id=current_user.id)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="查看文档处理状态",
    tags=["RAG"],
)
async def get_document(
    document_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)
):
    rag_service = RAGService(db)
    document = rag_service.get_document_for_user(document_id=document_id, owner_id=current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@router.delete(
    "/documents/{document_id}",
    summary="删除指定文档（含已处理的向量块）",
    tags=["RAG"],
)
async def delete_document(
    document_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_active_user)
):
    rag_service = RAGService(db)
    document = rag_service.delete_document(document_id=document_id, owner_id=current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return JSONResponse(
        content={"message": f"文档 '{document.filename}' 已删除", "document_id": document.id}
    )


@router.get(
    "/search",
    summary="知识库纯检索（只返回相关片段，不调用 LLM、零 LLM 成本）",
    tags=["RAG"],
)
async def search_knowledge_base(
    query: str = Query(..., min_length=1, description="检索关键词或句子"),
    top_k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """轻量搜索：向量化后直接返回最相关的文档片段，适合"查一下"场景。"""
    rag_service = RAGService(db)
    chunks = await rag_service.retrieve_relevant_chunks(
        query=query, owner_id=current_user.id, top_k=top_k
    )
    return {
        "query": query,
        "results": [{"document_id": c.document_id, "content": c.content} for c in chunks],
    }


@router.post(
    "/query", response_model=RAGQueryResponse, summary="基于知识库检索并回答", tags=["RAG"]
)
async def query_knowledge_base(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    1. 接收用户 Query 并计算向量
    2. 使用 pgvector 检索最相似的文档块 (top_k)
    3. 组装 prompt，调用 LLM 生成答案

    成本治理：与聊天链路同标准 —— 预算熔断 + 语义缓存 + 定价中心记账。
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 成本熔断：预算触顶拒绝调用（此接口此前绕过了治理，现已补齐）
    budget = check_budget(db, current_user.id)
    if not budget.allowed:
        raise HTTPException(status_code=402, detail=budget_reject_message(budget))

    rag_service = RAGService(db)
    session_history = []
    if request.session_id:
        session_history = await load_session_history(current_user.id, request.session_id)
    is_first_turn = not session_history

    # 查询向量只算一次，缓存查询/检索/写缓存复用，避免三次 embedding
    query_vector = None
    try:
        query_vector = (await rag_service.get_embeddings([request.query]))[0]
    except Exception as exc:
        logger.warning(f"RAG 查询向量化失败，后续检索将重试: {exc}")

    # 语义缓存只在会话首轮读写：多轮回答依赖上文，复用会张冠李戴
    if is_first_turn and query_vector is not None:
        cache_hit = await lookup_semantic_cache(
            db,
            current_user.id,
            request.query,
            require_sources=True,
            query_vector=query_vector,
        )
        if cache_hit is not None:
            entry, similarity = cache_hit
            if request.session_id:
                await append_session_message(
                    current_user.id, request.session_id, "user", request.query
                )
                await append_session_message(
                    current_user.id, request.session_id, "assistant", entry.answer
                )
            return RAGQueryResponse(
                query=request.query,
                answer=(
                    f"（缓存命中 · 相似度 {similarity:.0%} · 已节省 ¥{entry.original_cost_cny:.4f}）\n\n"
                    f"{entry.answer}"
                ),
                source_chunks=entry.source_chunks or [],
            )

    started_at = start_timer()
    try:
        knowledge = await rag_service.build_knowledge_context(
            query=request.query,
            owner_id=current_user.id,
            top_k=request.top_k,
            query_vector=query_vector,
        )

        if not knowledge.context:
            # 区分"确实没有文档"与"有文档但这次没检索到"，后者不该误导用户去上传
            answer = (
                "知识库中暂无已处理完成的相关文档，请先上传文档并等待处理完成。"
                if knowledge.total_ready_documents == 0
                else "暂未在知识库中检索到与问题相关的内容。可以换个说法再试，或等文档摘要生成后再问。"
            )
            return RAGQueryResponse(
                query=request.query,
                answer=answer,
                source_chunks=[],
            )

        # 3. 组装 Prompt（参考资料块由 RAGService 统一渲染，含全局问题的摘要兜底）
        system_prompt = (
            "你是一个专业的问答助手。请基于以下提供的参考资料，准确回答用户的问题。\n"
            "如果你不知道答案，或者参考资料中没有相关信息，请直接说明，不要编造。\n\n"
            f"{knowledge.context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.query},
        ]

        if request.session_id:
            messages = (
                [{"role": "system", "content": system_prompt}]
                + session_history
                + [{"role": "user", "content": request.query}]
            )

        llm_info = get_llm_client(current_user)
        response = await llm_info.client.chat.completions.create(
            model=llm_info.model_name,
            messages=messages,
            temperature=0.1,  # 降低 temperature 以保证 RAG 问答的稳定性
        )
        response_text = response.choices[0].message.content
        prompt_tokens, completion_tokens, total_tokens = extract_usage(response)

        if request.session_id:
            await append_session_message(current_user.id, request.session_id, "user", request.query)
            await append_session_message(
                current_user.id, request.session_id, "assistant", response_text
            )
        create_llm_call_log(
            db,
            user_id=current_user.id,
            endpoint="/api/v1/rag/query",
            prompt=request.query,
            response=response_text,
            tool_calls=None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=elapsed_ms(started_at),
            status="success",
            model_name=llm_info.model_name,
            provider="rag_query",
        )
        # 语义缓存只在首轮写入（多轮回答依赖上文，不能复用）
        if is_first_turn:
            await store_semantic_cache(
                db,
                current_user.id,
                request.query,
                response_text,
                llm_info.model_name,
                prompt_tokens,
                completion_tokens,
                estimate_cost_cny(db, llm_info.model_name, prompt_tokens, completion_tokens),
                source_chunks=knowledge.source_labels(),
                query_vector=query_vector,
            )

        return RAGQueryResponse(
            query=request.query, answer=response_text, source_chunks=knowledge.source_labels()
        )

    except Exception as e:
        create_llm_call_log(
            db,
            user_id=current_user.id,
            endpoint="/api/v1/rag/query",
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


@router.post("/query/stream", summary="基于知识库检索并流式回答 (SSE)", tags=["RAG"])
async def query_knowledge_base_stream(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    与阻塞接口同标准：预算熔断 + 语义缓存 + 定价中心记账。

    注意：预算必须在建立流之前判断（流一旦开始推送就无法再回 402），
    而记账/缓存/历史必须放在 [DONE] 之前——客户端收到 DONE 会立即断开，
    Starlette 随之取消本生成器，放在 DONE 之后的 await 型收尾会被截断。
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 成本熔断：预算触顶直接拒绝，不产生 embedding / LLM 调用
    budget = check_budget(db, current_user.id)
    if not budget.allowed:
        raise HTTPException(status_code=402, detail=budget_reject_message(budget))

    rag_service = RAGService(db)
    session_history = []
    if request.session_id:
        session_history = await load_session_history(current_user.id, request.session_id)
    is_first_turn = not session_history

    # 查询向量只算一次，缓存查询/检索/写缓存复用，避免三次 embedding
    query_vector = None
    try:
        query_vector = (await rag_service.get_embeddings([request.query]))[0]
    except Exception as exc:
        logger.warning(f"RAG 查询向量化失败，后续检索将重试: {exc}")

    # 语义缓存只在会话首轮读写：多轮回答依赖上文，复用会张冠李戴
    if is_first_turn and query_vector is not None:
        cache_hit = await lookup_semantic_cache(
            db,
            current_user.id,
            request.query,
            require_sources=True,
            query_vector=query_vector,
        )
        if cache_hit is not None:
            entry, similarity = cache_hit
            note = f"（缓存命中 · 相似度 {similarity:.0%} · 已节省 ¥{entry.original_cost_cny:.4f}）\n\n"

            async def _replay():
                if request.session_id:
                    await append_session_message(
                        current_user.id, request.session_id, "user", request.query
                    )
                    await append_session_message(
                        current_user.id, request.session_id, "assistant", entry.answer
                    )
                yield _sse({"content": note})
                yield _sse({"content": entry.answer})
                yield _sse({"source_chunks": entry.source_chunks or []})
                yield "data: [DONE]\n\n"

            return StreamingResponse(_replay(), media_type="text/event-stream")

    knowledge = await rag_service.build_knowledge_context(
        query=request.query,
        owner_id=current_user.id,
        top_k=request.top_k,
        query_vector=query_vector,
    )

    if not knowledge.context:
        empty_answer = (
            "知识库中暂无已处理完成的相关文档，请先上传文档并等待处理完成。"
            if knowledge.total_ready_documents == 0
            else "暂未在知识库中检索到与问题相关的内容。可以换个说法再试，或等文档摘要生成后再问。"
        )

        async def _empty():
            yield _sse({"content": empty_answer, "source_chunks": []})
            yield "data: [DONE]\n\n"

        return StreamingResponse(_empty(), media_type="text/event-stream")

    system_prompt = (
        "你是一个专业的问答助手。请基于以下提供的参考资料，准确回答用户的问题。\n"
        "如果你不知道答案，或者参考资料中没有相关信息，请直接说明，不要编造。\n\n"
        f"{knowledge.context}"
    )

    source_chunk_contents = knowledge.source_labels()
    started_at = start_timer()

    async def _stream():
        llm_info = get_llm_client(current_user)
        full_response = ""
        prompt_tokens = completion_tokens = total_tokens = 0

        stream_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.query},
        ]

        if request.session_id:
            await append_session_message(current_user.id, request.session_id, "user", request.query)
            stream_messages = (
                [{"role": "system", "content": system_prompt}]
                + session_history
                + [{"role": "user", "content": request.query}]
            )

        try:
            response = await llm_info.client.chat.completions.create(
                model=llm_info.model_name,
                messages=stream_messages,
                temperature=0.1,
                stream=True,
                # 末尾 chunk 携带 usage，用于记账与成本统计
                stream_options={"include_usage": True},
            )
            async for chunk in response:
                if getattr(chunk, "usage", None):
                    prompt_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0
                    total_tokens = getattr(chunk.usage, "total_tokens", 0) or 0

                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield _sse({"content": content})

            # ---- 收尾必须全部在 [DONE] 之前 ----
            if request.session_id and full_response:
                await append_session_message(
                    current_user.id, request.session_id, "assistant", full_response
                )

            cost_cny = estimate_cost_cny(db, llm_info.model_name, prompt_tokens, completion_tokens)
            create_llm_call_log(
                db,
                user_id=current_user.id,
                endpoint="/api/v1/rag/query/stream",
                prompt=request.query,
                response=full_response or None,
                tool_calls=None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=elapsed_ms(started_at),
                status="success",
                model_name=llm_info.model_name,
                provider="rag_query",
            )
            if full_response and is_first_turn:
                await store_semantic_cache(
                    db,
                    current_user.id,
                    request.query,
                    full_response,
                    llm_info.model_name,
                    prompt_tokens,
                    completion_tokens,
                    cost_cny,
                    source_chunks=source_chunk_contents,
                    query_vector=query_vector,
                )

            yield _sse({"source_chunks": source_chunk_contents})
            yield "data: [DONE]\n\n"
        except Exception as e:
            create_llm_call_log(
                db,
                user_id=current_user.id,
                endpoint="/api/v1/rag/query/stream",
                prompt=request.query,
                response=None,
                tool_calls=None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=elapsed_ms(started_at),
                status="failed",
                error_message=str(e),
                model_name=llm_info.model_name,
                provider="rag_query",
            )
            yield _sse({"error": str(e)})

    return StreamingResponse(_stream(), media_type="text/event-stream")
