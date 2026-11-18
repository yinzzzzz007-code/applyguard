"""Local multilingual MiniLM adapter for the SAG embedding registry."""

import asyncio
from functools import lru_cache
from pathlib import Path

from zleap.sag.config import EmbeddingConfig
from zleap.sag.core.adapters import registry
from zleap.sag.core.adapters.defaults import OpenAIEmbeddingAdapter, OpenAILLMAdapter
from zleap.sag.core.ai.models import LLMMessage

from backend.services.model_client import json_schema_instruction, uses_deepseek_api


class LocalEmbeddingConfig(EmbeddingConfig):
    model_directory: Path


@lru_cache(maxsize=2)
def _load_model(directory: Path):
    from onnxruntime import InferenceSession, SessionOptions
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(directory / 'tokenizer.json'))
    tokenizer.enable_truncation(max_length=128)
    tokenizer.enable_padding(pad_token='<pad>', pad_id=tokenizer.token_to_id('<pad>'))
    options = SessionOptions()
    options.intra_op_num_threads = 2
    model = InferenceSession(str(directory / 'model_quantized.onnx'), options,
                             providers=['CPUExecutionProvider'])
    return tokenizer, model


class LocalMiniLM:
    def __init__(self, config: LocalEmbeddingConfig):
        self.directory = config.model_directory

    def _embed(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        tokenizer, model = _load_model(self.directory)
        encoded = tokenizer.encode_batch(texts)
        mask = np.asarray([item.attention_mask for item in encoded], dtype=np.int64)
        tokens, = model.run(['last_hidden_state'], {
            'input_ids': np.asarray([item.ids for item in encoded], dtype=np.int64),
            'attention_mask': mask,
            'token_type_ids': np.asarray([item.type_ids for item in encoded], dtype=np.int64),
        })
        masked = mask[:, :, None]
        pooled = (tokens * masked).sum(axis=1) / masked.sum(axis=1).clip(min=1)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-12)
        return (pooled / norms).tolist()

    async def batch_generate(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed, texts) if texts else []

    async def generate(self, text: str) -> list[float]:
        return (await self.batch_generate([text]))[0]


def _embedding_adapter(config=None):
    if isinstance(config, LocalEmbeddingConfig):
        return LocalMiniLM(config)
    return OpenAIEmbeddingAdapter(config=config)


class DeepSeekLLMAdapter(OpenAILLMAdapter):
    @staticmethod
    def _messages(messages, schema):
        return [LLMMessage(role='system', content=json_schema_instruction(schema)), *messages]

    async def chat_with_schema(self, messages, response_schema, **kwargs):
        return await super().chat_with_schema(self._messages(messages, response_schema), response_schema, **kwargs)

    async def chat_with_schema_once(self, messages, response_schema, **kwargs):
        return await super().chat_with_schema_once(self._messages(messages, response_schema), response_schema, **kwargs)


def _llm_adapter(config=None):
    if config is not None and uses_deepseek_api(config.base_url or ''):
        return DeepSeekLLMAdapter(config=config)
    return OpenAILLMAdapter(config=config)


def local_embedding(directory: Path) -> LocalEmbeddingConfig:
    # SAG 0.15 selects its default embedding adapter and passes the configured object.
    registry.register('embedding', 'openai', _embedding_adapter)
    registry.register('llm', 'openai', _llm_adapter)
    return LocalEmbeddingConfig(model='paraphrase-multilingual-MiniLM-L12-v2',
                                schema_dimensions=384, model_directory=directory)
