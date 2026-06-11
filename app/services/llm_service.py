import asyncio
import ast
import json
import operator
from dataclasses import dataclass
from typing import Optional, Union

import psutil
from openai import AsyncOpenAI
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from sqlalchemy import select
from sqlalchemy.orm import Session
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import logger
from app.models.task import Task
from app.models.user import User
from app.services.llm_observability_service import (
    create_llm_call_log,
    elapsed_ms,
    extract_usage,
    serialize_tool_calls,
    start_timer,
)
from app.services.mcp_service import MCPService
from app.utils.encryption import decrypt_api_key

# 全局复用一个 AsyncOpenAI 客户端 (针对未配置自有 Key 的情况)
_global_client = None


@dataclass
class LLMClientInfo:
    client: Union[AsyncOpenAI, "MockLLMClient"]
    model_name: str


# ==========================================
# MockLLMClient — 无需 API Key 的模拟客户端
# ==========================================
class _MockUsage:
    prompt_tokens = 10
    completion_tokens = 20
    total_tokens = 30


class _MockDelta:
    def __init__(self, content: str = "", reasoning_content: str = None):
        self.content = content
        self.reasoning_content = reasoning_content


class _MockChoice:
    def __init__(self, delta: _MockDelta = None, message_content: str = ""):
        if delta is not None:
            self.delta = delta
        else:
            self.message = _MockMessage(content=message_content)


class _MockMessage:
    def __init__(self, content: str):
        self.content = content
        self.tool_calls = None


class _MockChunk:
    def __init__(self, delta: _MockDelta):
        self.choices = [_MockChoice(delta=delta)]


class _MockResponse:
    def __init__(self, content: str):
        self.choices = [_MockChoice(message_content=content)]
        self.usage = _MockUsage()


class _MockChatCompletions:
    async def create(self, model: str, messages: list, **kwargs) -> _MockResponse:
        stream = kwargs.get("stream", False)
        if stream:
            return self._stream_response()
        return _MockResponse(content="这是 Mock 模式的回复。系统正以离线演示模式运行，未连接真实 LLM API。你可以继续体验对话流程，但所有回复均为预设内容。")

    async def _stream_response(self):
        content = "这是 Mock 模式下的流式回复，用于演示目的。系统当前运行在 Mock 模式，未连接真实 LLM API。"
        for char in content:
            yield _MockChunk(delta=_MockDelta(content=char))
            await asyncio.sleep(0.01)
        yield _MockChunk(delta=_MockDelta(content=""))


class _MockChat:
    completions = _MockChatCompletions()


class MockLLMClient:
    """模拟 LLM 客户端，返回预设回复，无需 API Key"""
    chat = _MockChat()
    api_key = "mock"


def get_llm_client(user: User = None) -> LLMClientInfo:
    """
    动态获取 LLM 客户端和模型名称。
    优先使用用户自定义的配置（支持多租户独立 Key），若用户未配置，则回退到系统全局配置。
    当 LLM_MOCK=true 时，返回 MockLLMClient，无需任何 API Key。
    """
    if settings.LLM_MOCK:
        logger.info("==> LLM Mock 模式已开启，使用模拟客户端")
        return LLMClientInfo(client=MockLLMClient(), model_name="mock-model")

    if user and user.has_custom_llm_key:
        api_key = decrypt_api_key(user.llm_api_key_encrypted)
        base_url = user.llm_base_url or settings.LLM_BASE_URL
        model_name = user.llm_model_name or settings.LLM_MODEL_NAME

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        return LLMClientInfo(client=client, model_name=model_name)
    else:
        global _global_client
        if _global_client is None:
            _global_client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )
        return LLMClientInfo(client=_global_client, model_name=settings.LLM_MODEL_NAME)


# ==========================================
# 1. 定义本地工具函数 (模拟查询天气与系统状态)
# ==========================================
def get_current_weather(location: str) -> str:
    """模拟天气查询函数，实际中这里可以调用外部天气 API"""
    logger.info(f"==> 执行本地工具: 查询 {location} 的天气")
    # 为了演示，写死几个城市的天气
    weather_data = {
        "北京": "晴天，气温 25°C，微风",
        "上海": "多云，气温 28°C，可能有阵雨",
        "广州": "小雨，气温 26°C，湿度较高",
    }
    # 默认返回
    return weather_data.get(location, f"{location} 天气未知，气温大约 20°C")


def get_system_status() -> str:
    """查询服务器当前的系统负载、内存与磁盘占用状态"""
    logger.info("==> 执行本地工具: 查询系统状态")
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        status_info = (
            f"【CPU 使用率】: {cpu_percent}%\n"
            f"【内存使用率】: {memory.percent}% (已用: {memory.used / (1024**3):.2f}GB, 总计: {memory.total / (1024**3):.2f}GB)\n"
            f"【磁盘使用率】: {disk.percent}% (已用: {disk.used / (1024**3):.2f}GB, 总计: {disk.total / (1024**3):.2f}GB)"
        )
        return status_info
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return "无法获取系统状态信息。"


def list_tasks(db: Session, user_id: int, status: str = None) -> str:
    logger.info(f"==> 执行本地工具: 查询任务列表 (user_id={user_id}, status={status})")
    try:
        stmt = select(Task).where(Task.owner_id == user_id)
        if status:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.created_at.desc()).limit(10)
        tasks = list(db.scalars(stmt).all())
        if not tasks:
            return "当前没有任务。"
        lines = []
        for t in tasks:
            lines.append(f"  - [ID:{t.id}] [{t.status}] {t.title}")
            if t.description:
                lines.append(f"    描述: {t.description}")
        return "当前任务列表:\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"查询任务列表失败: {e}")
        return "查询任务列表时发生错误。"


_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
}

_ALLOWED_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
}


def _safe_eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不支持的常量类型: {type(node.value).__name__}")

    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        return _ALLOWED_OPS[op_type](left, right)

    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        operand = _safe_eval_node(node.operand)
        return _ALLOWED_OPS[op_type](operand)

    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("只允许直接函数名调用")
        func_name = node.func.id
        if func_name not in _ALLOWED_FUNCS:
            raise ValueError(f"不支持的函数: {func_name}")
        args = [_safe_eval_node(arg) for arg in node.args]
        return _ALLOWED_FUNCS[func_name](*args)

    else:
        raise ValueError(f"不支持的表达式类型: {type(node).__name__}")


def safe_eval(expr: str) -> float:
    """安全计算数学表达式，使用 AST 而非 eval()"""
    node = ast.parse(expr.strip(), mode="eval").body
    return _safe_eval_node(node)


def calculate(expression: str) -> str:
    logger.info(f"==> 执行本地工具: 计算表达式 '{expression}'")
    try:
        result = safe_eval(expression)
        return f"计算结果: {expression} = {result}"
    except Exception as e:
        return f"计算失败: {e}"


# 工具 Schema 与处理器已统一托管于 MCPService
# 新增工具时只需在 mcp_service.py 中注册即可


async def _llm_completion_with_retry(llm_client, **kwargs):
    """LLM API 调用，带指数退避重试（应对 429 限流和临时网络问题）"""
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=lambda retry_state: logger.warning(
            f"LLM API 调用失败 (第 {retry_state.attempt_number} 次重试): "
            f"{retry_state.outcome.exception()}"
        ),
    ):
        with attempt:
            return await llm_client.chat.completions.create(**kwargs)


async def generate_chat_reply(message: str, db: Session = None, current_user_id: int = None) -> str:
    """
    调用大语言模型生成回复 (带 Tool Calling 支持)
    """
    user = db.get(User, current_user_id) if db and current_user_id else None

    info = get_llm_client(user)

    if not info.client.api_key:
        return "【系统提示】大模型 API Key 尚未配置，请在系统或个人设置中配置。"

    started_at = start_timer()

    # 初始对话上下文
    messages = [
        {
            "role": "system",
            "content": "你是一个有用的 AI 助手，同时你也是用户的私人日程管理专家。你可以调用工具来获取实时信息或帮助用户创建任务。如果工具返回了结果，请用自然语言总结并回答用户。",
        },
        {"role": "user", "content": message},
    ]
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    tool_calls_payload = None
    final_reply = None

    try:
        # 第一轮调用：告诉模型用户的问题，并附带工具列表
        logger.info("==> [Round 1] 正在请求大模型...")

        # 针对部分模型（如 Qwen2.5）强化 Prompt
        system_prompt = (
            "你是一个有用的 AI 助手，同时你也是用户的私人日程管理专家。"
            "当用户要求你创建任务、复习计划、日程等事项时，你必须使用 'create_task' 工具来创建任务，不要仅仅用文字回答。"
            "调用工具时请直接返回合法的 JSON 格式工具调用指令，不要在前面或后面附加任何乱码或多余文本。"
        )
        messages[0]["content"] = system_prompt

        response = await _llm_completion_with_retry(
            info.client,
            model=info.model_name,
            messages=messages,
            tools=MCPService.list_tools(),
            tool_choice="auto",
            temperature=0.1,
            max_tokens=1000,
        )

        response_message = response.choices[0].message
        prompt_tokens, completion_tokens, used_tokens = extract_usage(response)
        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_tokens += used_tokens

        # 检查模型是否决定调用工具
        if response_message.tool_calls:
            logger.info("==> 模型决定调用工具！")
            messages.append(response_message)
            tool_calls_payload = serialize_tool_calls(response_message.tool_calls)

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                tool_result = ""
                if function_name == "create_task":
                    logger.info(f"==> 模型尝试创建任务: {arguments}")
                    if db and current_user_id:
                        tool_result = await MCPService.call_tool(
                            name=function_name,
                            arguments=arguments,
                            db=db,
                            user_id=current_user_id,
                        )
                    else:
                        tool_result = "任务创建失败：未获取到数据库连接或用户登录状态。"

                elif function_name == "list_tasks":
                    tool_result = await MCPService.call_tool(
                        name=function_name,
                        arguments=arguments,
                        db=db,
                        user_id=current_user_id,
                    )

                else:
                    tool_result = await MCPService.call_tool(
                        name=function_name,
                        arguments=arguments,
                    )

                # 将工具的执行结果追加到上下文中
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": tool_result,
                    }
                )

            # 第二轮调用
            logger.info("==> [Round 2] 工具结果已返回，正在请求大模型生成最终回答...")
            second_response = await _llm_completion_with_retry(
                info.client,
                model=info.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
            )
            prompt_tokens, completion_tokens, used_tokens = extract_usage(second_response)
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens
            total_tokens += used_tokens
            final_reply = second_response.choices[0].message.content
            if db:
                create_llm_call_log(
                    db,
                    user_id=current_user_id,
                    endpoint="/api/v1/chat",
                    prompt=message,
                    response=final_reply,
                    tool_calls=tool_calls_payload,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=elapsed_ms(started_at),
                    status="success",
                )
            return final_reply

        else:
            logger.info("==> 模型没有调用工具，直接返回了回答。")
            final_reply = response_message.content
            if db:
                create_llm_call_log(
                    db,
                    user_id=current_user_id,
                    endpoint="/api/v1/chat",
                    prompt=message,
                    response=final_reply,
                    tool_calls=None,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=elapsed_ms(started_at),
                    status="success",
                )
            return final_reply

    except Exception as e:
        logger.error(f"LLM API 调用失败: {str(e)}")
        if db:
            create_llm_call_log(
                db,
                user_id=current_user_id,
                endpoint="/api/v1/chat",
                prompt=message,
                response=final_reply,
                tool_calls=tool_calls_payload,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                total_tokens=total_tokens,
                latency_ms=elapsed_ms(started_at),
                status="failed",
                error_message=str(e),
            )
        return f"【系统提示】模型调用失败，请检查网络或 API 配置。错误详情: {str(e)}"


async def generate_chat_reply_stream(message: str, db: Session = None, current_user_id: int = None):
    """
    流式调用大语言模型生成回复 (SSE)。不支持 Tool Calling，如果需要 Tool Calling 建议先判断。
    这里为了演示，提供最基础的流式输出支持。
    """
    user = db.get(User, current_user_id) if db and current_user_id else None
    info = get_llm_client(user)

    if not info.client.api_key:
        yield 'data: {"error": "API Key 未配置"}\n\n'
        return

    messages = [
        {"role": "system", "content": "你是一个有用的 AI 助手。"},
        {"role": "user", "content": message},
    ]

    try:
        response = await info.client.chat.completions.create(
            model=info.model_name, messages=messages, temperature=0.7, stream=True
        )

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            payload = {}
            if getattr(delta, "reasoning_content", None):
                payload["reasoning"] = delta.reasoning_content
            if delta.content:
                payload["content"] = delta.content
            if payload:
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"LLM Stream 调用失败: {str(e)}")
        data = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"data: {data}\n\n"
