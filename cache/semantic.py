import os
import langchain
import structlog
from langchain_openai import OpenAIEmbeddings

logger = structlog.get_logger()


def setup_cache() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    try:
        from langchain_community.cache import RedisSemanticCache
        langchain.llm_cache = RedisSemanticCache(
            redis_url=redis_url,
            embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        )
        logger.info("semantic_cache_enabled", redis_url=redis_url)
    except Exception as e:
        # Degrade gracefully — cache is a performance optimization, not a hard requirement
        logger.warning("semantic_cache_unavailable", error=str(e))
