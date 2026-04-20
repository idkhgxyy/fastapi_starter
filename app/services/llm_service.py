from openai import AsyncOpenAI
import json
from app.core.config import settings
from app.core.logging import logger
from sqlalchemy.orm import Session
from app.schemas.task import TaskCreate
from app.services.task_service import TaskService
from app.services.llm_observability_service import (
    create_llm_call_log,
    elapsed_ms,
    extract_usage,
    serialize_tool_calls,
    start_timer,
)

# 全局复用一个 AsyncOpenAI 客户端
client = None

def get_llm_client() -> AsyncOpenAI:
    global client
    if client is None:
        client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
    return client

# ==========================================
# 1. 定义本地工具函数 (模拟查询天气)
# ==========================================
def get_current_weather(location: str) -> str:
    """模拟天气查询函数，实际中这里可以调用外部天气 API"""
    logger.info(f"==> 执行本地工具: 查询 {location} 的天气")
    # 为了演示，写死几个城市的天气
    weather_data = {
        "北京": "晴天，气温 25°C，微风",
        "上海": "多云，气温 28°C，可能有阵雨",
        "广州": "小雨，气温 26°C，湿度较高"
    }
    # 默认返回
    return weather_data.get(location, f"{location} 天气未知，气温大约 20°C")

# ==========================================
# 2. 定义告诉大模型的工具 Schema (JSON Schema)
# ==========================================
WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "获取指定城市的当前天气情况",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "城市名称，例如：北京、上海"
                }
            },
            "required": ["location"]
        }
    }
}

CREATE_TASK_TOOL = {
    "type": "function",
    "function": {
        "name": "create_task",
        "description": "为当前用户创建一个新的待办任务",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "任务标题，必须简明扼要"
                },
                "description": {
                    "type": "string",
                    "description": "任务的详细描述，如果用户没有提供，可以根据上下文生成或者留空"
                }
            },
            "required": ["title"]
        }
    }
}

async def generate_chat_reply(message: str, db: Session = None, current_user_id: int = None) -> str:
    """
    调用大语言模型生成回复 (带 Tool Calling 支持)
    """
    if not settings.LLM_API_KEY:
        return "【系统提示】大模型 API Key 尚未配置，请在 .env 中设置 LLM_API_KEY。"

    llm_client = get_llm_client()
    started_at = start_timer()
    
    # 初始对话上下文
    messages = [
        {"role": "system", "content": "你是一个有用的 AI 助手，同时你也是用户的私人日程管理专家。你可以调用工具来获取实时信息或帮助用户创建任务。如果工具返回了结果，请用自然语言总结并回答用户。"},
        {"role": "user", "content": message}
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

        response = await llm_client.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=messages,
            tools=[WEATHER_TOOL, CREATE_TASK_TOOL],  # 注入多个工具
            tool_choice="auto",
            temperature=0.1,  # 降低温度，减少乱码概率，提高指令遵循
            max_tokens=1000
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
                if function_name == "get_current_weather":
                    location = arguments.get("location")
                    tool_result = get_current_weather(location=location)
                
                elif function_name == "create_task":
                    # 拦截到创建任务的请求，调用真实的服务层写入数据库！
                    logger.info(f"==> 模型尝试创建任务: {arguments}")
                    if db and current_user_id:
                        task_in = TaskCreate(
                            title=arguments.get("title"),
                            description=arguments.get("description", "")
                        )
                        created_task = TaskService.create_task(db=db, task_in=task_in, owner_id=current_user_id)
                        tool_result = f"任务创建成功！任务ID: {created_task.id}, 标题: {created_task.title}"
                    else:
                        tool_result = "任务创建失败：未获取到数据库连接或用户登录状态。"
                
                # 将工具的执行结果追加到上下文中
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_result
                })
            
            # 第二轮调用
            logger.info("==> [Round 2] 工具结果已返回，正在请求大模型生成最终回答...")
            second_response = await llm_client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
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
                    endpoint="/api/chat",
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
                    endpoint="/api/chat",
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
                endpoint="/api/chat",
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
