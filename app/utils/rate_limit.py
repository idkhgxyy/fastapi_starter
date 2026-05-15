import time
import uuid

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import settings
from app.core.logging import logger

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


class RateLimiter:
    """
    基于 Redis ZSET 的滑动窗口限流器
    """

    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds

    async def __call__(self, request: Request):
        # 优先使用 Authorization Token 的 hash 或者 IP 作为限流 key
        auth_header = request.headers.get("Authorization")
        if auth_header:
            client_id = hash(auth_header)
        else:
            client_id = request.client.host if request.client else "unknown"

        key = f"rate_limit:{client_id}:{request.url.path}"

        current = time.time()
        window_start = current - self.seconds
        member_id = str(uuid.uuid4())

        try:
            async with redis_client.pipeline(transaction=True) as pipe:
                # 移除时间窗口之前的数据
                pipe.zremrangebyscore(key, 0, window_start)
                # 统计当前窗口内的请求数
                pipe.zcard(key)
                # 将当前请求加入窗口
                pipe.zadd(key, {member_id: current})
                # 设置过期时间，避免长期占用内存
                pipe.expire(key, self.seconds)
                results = await pipe.execute()

            request_count = results[1]

            if request_count >= self.times:
                logger.warning(f"Rate limit exceeded for {key}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                )
        except HTTPException:
            raise
        except Exception as e:
            # 如果 Redis 挂了，降级放行，不影响核心业务
            logger.error(f"Rate limit redis error: {e}")
