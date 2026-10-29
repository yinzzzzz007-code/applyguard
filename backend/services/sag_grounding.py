# Gitvextor的原型：SAG 集成、事实核验与错改保护（姜凌天，2026-10-30）。
# Third-party methods and licenses: see THIRD_PARTY_NOTICES.md.
"""Local, version-scoped retrieval using the real optional zleap-sag engine."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_LOCKS: dict[str, threading.Lock] = {}
_LOCK = threading.Lock()


class GroundingUnavailable(RuntimeError):
    """A requested grounding stage could not be completed; never a verified result."""


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def evidence_snapshot(sources: list[dict]) -> str:
    return fingerprint(sorted(sources, key=lambda source: source['source_id']))


def search_queries(text: str) -> list[tuple[str, str]]:
    """Search for disconfirming evidence as well as similar wording."""
    return [('support', text),
        ('refutation', text + '\n查找与上述陈述相反的原文：未使用、未完成、非负责人、团队贡献、限制条件、否定。'),
        ('correction', text + '\n查找更正、勘误、撤回、修订后的数字和职责、旧稿作废或计划变更的原文。')]


class SAGRetriever:
    """Index immutable evidence snapshots; query only each claim's allowed sources.

    No event summaries, generated graph labels, or out-of-scope chunks become
    factual evidence. Original text and server-owned metadata are authoritative.
    """

    def __init__(self):
        self.stats={'search_calls':0,'cache_hits':0,'indexed_sources':0}

    @staticmethod
    def cache_key(query, strategy):
        return fingerprint(['query-v2',strategy,query['text'],sorted(query['source_ids']),search_queries(query['text'])])

    def retrieve_many(self, queries: list[dict], sources: list[dict], candidate_id: str) -> dict:
        if not queries:
            return {}
        if not sources:
            return {query['claim_id']: [] for query in queries}
        digest = evidence_snapshot(sources)
        directory = Path(os.getenv('APPLYGUARD_GROUNDING_DIR', str(ROOT / 'data/local/grounding')))
        settings = [os.getenv(name,'') for name in ['APPLYGUARD_AI_MODEL','APPLYGUARD_AI_BASE_URL',
            'APPLYGUARD_EMBEDDING_MODEL','APPLYGUARD_EMBEDDING_DIMENSIONS']]
        directory = directory / fingerprint(candidate_id)[:20] / digest / fingerprint(['0.15.0','minimal',settings])[:20]
        with _LOCK:
            lock = _LOCKS.setdefault(str(directory.resolve()), threading.Lock())
        # DataEngine has an event-loop lifecycle; never share it across HTTP threads.
        with lock:
            try:
                return asyncio.run(self._retrieve(queries, sources, candidate_id, directory))
            except GroundingUnavailable:
                raise
            except Exception:
                # Provider exceptions can contain request/configuration data.
                raise GroundingUnavailable('SAG索引或检索失败；请检查本机依赖、模型配置与网络。') from None

    async def _retrieve(self, queries: list[dict], sources: list[dict], candidate: str, directory: Path) -> dict:
        try:
            from zleap.sag import DataEngine, EngineConfig
            from zleap.sag.config import EmbeddingConfig, LLMConfig, RuntimeLimits
            from zleap.sag.pipeline import (
                SourceDescriptor, SearchRequest, SearchScope, SearchOptions,
                QueryProcessingOptions, GraphSearchOptions, SelectionOptions,
                SearchOutputOptions, ExtractionOptions, ExtractionLimits,
                ExtractionExecutionOptions,
            )
        except ImportError:
            raise GroundingUnavailable('尚未安装SAG引擎，请安装requirements-sag.txt。') from None
        key = os.getenv('APPLYGUARD_AI_API_KEY', '')
        if not key:
            raise GroundingUnavailable('未配置模型密钥，SAG无法建立事件与实体索引。')
        strategy = os.getenv('APPLYGUARD_GROUNDING_STRATEGY', 'full_expand')
        if strategy not in {'vector', 'full_expand'}:
            raise GroundingUnavailable('检索策略必须为vector或full_expand。')
        directory.mkdir(parents=True, exist_ok=True)
        dimensions = int(os.getenv('APPLYGUARD_EMBEDDING_DIMENSIONS', '1536'))
        if not 1 <= dimensions <= 8192:
            raise GroundingUnavailable('向量维度配置无效。')
        timeout = float(os.getenv('APPLYGUARD_GROUNDING_TIMEOUT', '110'))
        config = EngineConfig(
            storage_mode='normal', data_dir=str(directory / 'index'), language='en', log_level='ERROR',
            llm=LLMConfig(api_key=key, model=os.getenv('APPLYGUARD_AI_MODEL', 'gpt-4o-mini'),
                base_url=os.getenv('APPLYGUARD_AI_BASE_URL', 'https://api.chatanywhere.tech/v1'),
                temperature=0, max_tokens=4000, timeout=timeout, max_retries=0,
                structured_output_mode='json_schema'),
            embedding=EmbeddingConfig(model=os.getenv('APPLYGUARD_EMBEDDING_MODEL', 'text-embedding-3-small'),
                schema_dimensions=dimensions, timeout=timeout, max_retries=0),
            runtime_limits=RuntimeLimits(llm_concurrency=2, embedding_concurrency=2),
        )
        by_id = {source['source_id']: source for source in sources}
        if len(by_id) != len(sources) or any(source['candidate_id'] != candidate for source in sources):
            raise GroundingUnavailable('证据编号重复或不属于当前候选人。')
        source_group = 'candidate_' + fingerprint(candidate)[:24]
        marker = directory / 'indexed.json'
        output = {}
        async with DataEngine(config, data_source_id=source_group) as engine:
            if not marker.exists():
                for source in sources:
                    self.stats['indexed_sources'] += 1
                    path = directory / (source['source_id'] + '.md')
                    path.write_text(source['text'], encoding='utf-8')
                    reference = await engine.ingest(path, descriptor=SourceDescriptor(
                        source_type='article', source_id=source['source_id'], title=source['title'],
                        creator_id=candidate, metadata={'experience_id':source['experience_id'],
                            'evidence_id':source['evidence_id'], 'sha256':source['sha256']}))
                    await engine.extract(reference, ExtractionOptions(contract='minimal', max_retries=1,
                        limits=ExtractionLimits(max_events_per_chunk=5, max_entities_per_event=8),
                        execution=ExtractionExecutionOptions(max_concurrency=2, request_rejection_retries=0)))
                temporary = marker.with_suffix('.tmp')
                temporary.write_text(json.dumps({'snapshot':evidence_snapshot(sources)}), encoding='utf-8')
                temporary.replace(marker)
            semaphore=asyncio.Semaphore(max(1,min(3,int(os.getenv('APPLYGUARD_SEARCH_CONCURRENCY','2')))))
            cache_dir=directory/'query-cache-v2'
            cache_dir.mkdir(exist_ok=True)
            async def retrieve_query(query):
                allowed = set(query['source_ids']) & set(by_id)
                if not allowed:
                    output[query['claim_id']] = []
                    return
                cache_path=cache_dir/(self.cache_key(query,strategy)+'.json')
                if cache_path.exists():
                    try:
                        cached=json.loads(cache_path.read_text(encoding='utf-8'))
                        if (cached.get('snapshot')==evidence_snapshot(sources) and
                            all(row['source_id'] in allowed and row['retrieval_channels']
                                and set(row['retrieval_channels'])<={'support','refutation','correction'} for row in cached['hits'])):
                            output[query['claim_id']]=[{**by_id[row['source_id']],
                                'chunk_id':str(row.get('chunk_id','')),'retrieval_channels':row['retrieval_channels']} for row in cached['hits']]
                            self.stats['cache_hits'] += 1
                            return
                    except (ValueError,KeyError,TypeError):pass
                hits = []
                async def search_one(channel, search_text):
                    async with semaphore:
                        self.stats['search_calls'] += 1
                        result = await engine.search(SearchRequest(query=search_text,
                        scope=SearchScope(data_source_ids=(source_group,), source_ids=tuple(sorted(allowed))),
                        options=SearchOptions(strategy=strategy, top_k=5, return_type='chunk', guard=False,
                            structured_output_mode='json_schema',
                            query=QueryProcessingOptions(rewrite=False,
                                entity_extraction='llm' if strategy == 'full_expand' else 'disabled'),
                            graph=GraphSearchOptions(enabled=strategy == 'full_expand',
                                max_hops=2 if strategy == 'full_expand' else 0),
                            selection=SelectionOptions(enabled=False),
                            output=SearchOutputOptions(return_graph=False, include_stage_stats=True))))
                    return channel,result
                responses=await asyncio.gather(*(search_one(channel,text) for channel,text in search_queries(query['text'])))
                for channel,result in responses:
                    for chunk in result.chunks:
                        value = chunk.model_dump(mode='json')
                        source = by_id.get(value.get('source_id'))
                        if not source or source['source_id'] not in allowed:
                            continue
                        raw = value.get('content', '')
                        if not isinstance(raw, str) or not raw.strip():
                            continue
                        if raw not in source['text'] and source['text'] not in raw:
                            continue
                        previous = next((h for h in hits if h['source_id'] == source['source_id']), None)
                        if previous:
                            if channel not in previous['retrieval_channels']:
                                previous['retrieval_channels'].append(channel)
                        else:
                            # Expand to this retrieved original to retain adjacent corrections.
                            hits.append({**source, 'chunk_id':str(value.get('chunk_id', '')),
                                'retrieval_channels':[channel]})
                output[query['claim_id']] = hits
                # Cache only identifiers; canonical text and provenance are rebuilt from current sources.
                cache_path.write_text(json.dumps({'snapshot':evidence_snapshot(sources),'hits':[
                    {k:h[k] for k in ('source_id','chunk_id','retrieval_channels')} for h in hits]}),encoding='utf-8')
            # Query concurrency is bounded by the same semaphore; indexing remains serialized.
            await asyncio.gather(*(retrieve_query(query) for query in queries))
        return output
