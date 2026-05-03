import pytest
import json
from unittest.mock import MagicMock
from app.services.llm_service import generate_chat_reply
from app.schemas.task import TaskCreate

# 伪造的响应消息类
class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

# 伪造的工具调用相关类
class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

class FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = FakeFunction(name, arguments)

class FakeChoice:
    def __init__(self, message):
        self.message = message

class FakeCompletion:
    def __init__(self, choices):
        self.choices = choices
        # 模拟 usage
        self.usage = MagicMock()
        self.usage.prompt_tokens = 10
        self.usage.completion_tokens = 10
        self.usage.total_tokens = 20

@pytest.mark.asyncio
async def test_generate_chat_reply_with_tool_calling(mocker):
    """
    测试大模型触发 Tool Calling (create_task) 的业务逻辑。
    使用 pytest-mock 拦截对 openai 客户端的调用。
    """
    # 1. 伪造数据库会话和用户 ID
    mock_db = MagicMock()
    user_id = 1

    # 2. 拦截 TaskService.create_task 以验证是否被正确调用
    mock_created_task = MagicMock()
    mock_created_task.id = 999
    mock_created_task.title = "买牛奶"
    mock_create_task = mocker.patch("app.services.llm_service.TaskService.create_task", return_value=mock_created_task)

    # 3. 拦截 get_llm_client 以返回一个 Mock 客户端
    mock_llm_client = MagicMock()
    mock_completions_create = mocker.AsyncMock()
    mock_llm_client.chat.completions.create = mock_completions_create
    mocker.patch("app.services.llm_service.get_llm_client", return_value=mock_llm_client)
    
    # 构造第一轮返回（模型决定调用 create_task 工具）
    fake_tool_call = FakeToolCall(
        id="call_123",
        name="create_task",
        arguments=json.dumps({"title": "买牛奶", "description": "去超市买两瓶牛奶"})
    )
    first_response = FakeCompletion(choices=[FakeChoice(message=FakeMessage(tool_calls=[fake_tool_call]))])
    
    # 构造第二轮返回（模型总结工具的执行结果）
    second_response = FakeCompletion(choices=[FakeChoice(message=FakeMessage(content="好的，我已经为您创建了任务：买牛奶。"))])
    
    # 设置 mock 连续返回这两个结果
    mock_completions_create.side_effect = [first_response, second_response]

    # 4. 执行待测试的函数
    user_message = "帮我创建一个任务，去超市买两瓶牛奶"
    reply = await generate_chat_reply(message=user_message, db=mock_db, current_user_id=user_id)

    # 5. 验证执行结果
    # 验证最终回复是否为第二轮的 content
    assert "买牛奶" in reply
    
    # 验证大模型接口被调用了两次 (第一轮解析意图，第二轮总结)
    assert mock_completions_create.call_count == 2
    
    # 验证本地业务层 TaskService.create_task 是否被使用正确的参数调用
    mock_create_task.assert_called_once()
    called_args, called_kwargs = mock_create_task.call_args
    
    # 验证传入的 db 和 owner_id
    assert called_kwargs["db"] == mock_db
    assert called_kwargs["owner_id"] == user_id
    
    # 验证解析出的 Pydantic Schema 参数
    task_in = called_kwargs["task_in"]
    assert isinstance(task_in, TaskCreate)
    assert task_in.title == "买牛奶"
    assert task_in.description == "去超市买两瓶牛奶"

@pytest.mark.asyncio
async def test_generate_chat_reply_no_tool_call(mocker):
    """
    测试大模型未触发 Tool Calling 时的普通对话逻辑。
    """
    mock_db = MagicMock()
    user_id = 1
    
    mock_llm_client = MagicMock()
    mock_completions_create = mocker.AsyncMock()
    mock_llm_client.chat.completions.create = mock_completions_create
    mocker.patch("app.services.llm_service.get_llm_client", return_value=mock_llm_client)
    
    # 构造返回（普通聊天，无 tool_calls）
    fake_response = FakeCompletion(choices=[FakeChoice(message=FakeMessage(content="你好！我是你的助手。"))])
    mock_completions_create.return_value = fake_response
    
    reply = await generate_chat_reply(message="你好", db=mock_db, current_user_id=user_id)
    
    assert reply == "你好！我是你的助手。"
    assert mock_completions_create.call_count == 1
