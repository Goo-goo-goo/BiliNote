"""按 provider_id / model_name 解析 GPT 实例（自测题、复习资料等路由共用）。"""
from typing import Optional

from app.gpt.base import GPT
from app.gpt.gpt_factory import GPTFactory
from app.models.model_config import ModelConfig
from app.exceptions.provider import ProviderError
from app.enmus.exception import ProviderErrorEnum
from app.services.provider import ProviderService
from app.utils.logger import get_logger

logger = get_logger(__name__)


def resolve_gpt(model_name: Optional[str], provider_id: Optional[str]) -> GPT:
    provider = ProviderService.get_provider_by_id(provider_id)
    if not provider:
        logger.error(f"[resolve_gpt] 未找到模型供应商: provider_id={provider_id}")
        raise ProviderError(code=ProviderErrorEnum.NOT_FOUND, message=ProviderErrorEnum.NOT_FOUND.message)
    config = ModelConfig(
        api_key=provider["api_key"],
        base_url=provider["base_url"],
        model_name=model_name,
        provider=provider["type"],
        name=provider["name"],
    )
    return GPTFactory().from_config(config)
