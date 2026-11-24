"""Retrieve attributable project passages independently of the strict selection gate."""
from __future__ import annotations

import re
from functools import lru_cache
from backend.services.job_capabilities import FRAMEWORKS, concepts, framework_group

_BACKGROUND = {"Python", "Java", "Go", "研究产出", "问题分析"}
_TRAINING = {"后训练", "模型训练", "强化学习"}
_RELATED = {"代码智能体": {"智能体"}, "质量评测": {"问题分析"},
            "机器学习": _TRAINING, "大模型": {"后训练", "推理优化"},
            "问题分析": {"质量评测", "推理优化"}}
_NEGATION = re.compile(r"(?:未(?:曾)?(?:使用|参与|实现|负责|做过|进行)|没有(?:使用|参与|训练|微调)|不使用|仅(?:调用|使用).{0,16}API|did not use|without training)", re.I)
_STOP = {"and", "the", "for", "with", "or", "using", "skills", "experience", "required",
         "preferred", "knowledge", "ability", "familiar", "proficient", "work", "good", "build",
         "engineering", "based", "role", "working", "team", "design", "code", "data", "model", "ai"}

def passages(exp):
    values = [exp.get("title", ""), exp.get("summary", ""), exp.get("role", ""), *(exp.get("skills") or []), *(exp.get("responsibilities") or []),
              *(row.get("text", "") for row in exp.get("claims") or [])]
    return list(dict.fromkeys(piece.strip() for value in values
                              for piece in re.split(r"(?<=[。；;])|\n", value) if piece.strip()))


@lru_cache(maxsize=8192)
def tokens(text):
    return frozenset(word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,30}", text)
                     if word.casefold() not in _STOP)


def missing_financial_context(wanted, found):
    return {"金融研究", "估值回测"} <= wanted and not found.intersection({"金融研究", "估值回测"})


def match_passage(phrase, text, alternatives=()):
    wanted, found = concepts(phrase), concepts(text)
    if _NEGATION.search(text) or missing_financial_context(wanted, found):
        return None
    if framework_group(phrase):
        allowed = set(alternatives) or (wanted & FRAMEWORKS.keys()) or set(FRAMEWORKS)
        if alternatives and "等" in phrase:
            allowed = set(FRAMEWORKS)
        explicit = sorted(allowed & found)
        if explicit:
            return .94, "direct", explicit
        if found & _TRAINING:
            return .48, "framework", sorted(found & _TRAINING)
        return None

    hits = wanted & found
    work = wanted & {"后训练", "模型训练", "强化学习", "质量评测", "训练数据", "推理优化", "问题分析"}
    alternative_hit = bool(re.search(r"或|\bor\b", phrase, re.I) and hits & {"大模型", "强化学习"} and {"大模型", "强化学习"} <= wanted)
    if work and not hits.intersection(work) and not alternative_hit:
        if hits & {"CUDA", "GPU计算", "分布式系统"} and "质量评测" in work:
            return .53, "related", sorted(hits)
        if not ("推理优化" in found and "问题分析" in work):
            return None
    exact_tokens = tokens(phrase) & tokens(text)
    if hits or exact_tokens:
        labels = sorted(hits) or sorted(exact_tokens)
        if "代码智能体" in wanted and "代码智能体" not in hits and not hits.intersection(work):
            if not hits - {"大模型", "机器学习"}:
                return None
            return .51, "related", labels
        if "质量评测" in hits and re.search(r"软件工程|代码任务", phrase) and not re.search(r"软件工程|代码任务|coding agent|code agent", text, re.I):
            return .65, "related", labels
        specific = hits - _BACKGROUND
        score = min(.96, .69 + .09 * len(specific) + .025 * len(exact_tokens))
        return score, "direct", labels
    inferred = sorted(w for w in wanted if found.intersection(_RELATED.get(w, ())))
    if inferred:
        return .47, "related", inferred
    return None


def best_passage(phrase, lines, alternatives=()):
    best = None
    for line in lines:
        hit = match_passage(phrase, line, alternatives)
        if hit and (best is None or (hit[0], len(hit[2])) > (best[0], len(best[2]))):
            best = (*hit, line)
    return best


def discovery(requirement, experience):
    if requirement.get("category") == "EDUCATION":
        return None
    phrase = requirement.get("evidence_text") or requirement["text"]
    options = tuple(requirement.get("alternatives", []))
    hit = best_passage(phrase, passages(experience), options)
    source_hit = None
    for source in experience.get("evidence_sources") or []:
        if source.get("verification_status") != "VERIFIED" or not str(source.get("source_reference", "")).startswith("local-evidence://"):
            continue
        match = best_passage(phrase, source["description"].splitlines(), options)
        if match and match[1] == "direct" and (source_hit is None or match[0] > source_hit[0][0]):
            source_hit = (match, source["evidence_id"], source["source_reference"])
    if not hit and not source_hit:
        return None
    if source_hit and (not hit or source_hit[0][0] > hit[0]):
        hit = source_hit[0]
    score, kind, labels, quote = hit
    payload = {"title": experience.get("title") or experience["experience_id"], "kind": kind,
               "terms": labels, "quote": quote, "score": round(score, 2)}
    if source_hit:
        payload.update(material_id=source_hit[1], material_quote=source_hit[0][3], material_reference=source_hit[2])
    quotes = "\n".join(filter(None, (quote, payload.get("material_quote"))))
    pending = []
    if re.search(r"真实软件工程|real.world software engineering", phrase, re.I) and not re.search(
        r"软件工程|代码任务|代码仓库|缺陷修复|swe[- ]?bench|coding agent|software engineering|pull requests?", quotes, re.I
    ):
        pending.append("真实软件工程任务场景")
    if re.search(r"主导|牵头|led a project", phrase, re.I) and not re.search(
        r"主导|牵头|负责人|第一作者|一作|project lead|first author", quotes, re.I
    ):
        pending.append("本人主导的具体工作")
    if re.search(r"有影响力|significant impact|impactful", phrase, re.I):
        pending.append("项目或论文的实际影响")
    if pending:
        payload.update(kind="related", pending_context=pending, score=min(score, .65))
    return payload


def semantic_leads(requirements, experiences):
    from backend.services.job_recommendation import locations, vectorize
    directory, _ = locations()
    if not all((directory / name).is_file() for name in ("tokenizer.json", "model_quantized.onnx")):
        return {}
    queries = [(r["requirement_id"], r["text"]) for r in requirements if r.get("section")
               and r.get("priority") != "general" and r["category"] != "EDUCATION" and not framework_group(r["text"])
               and not (concepts(r["text"]) & {"代码智能体", "模型训练", "强化学习", "后训练"})]
    candidates = [(e, line) for e in experiences for line in passages(e) if len(line) >= 16]
    if not queries or not candidates:
        return {}
    try:
        import numpy as np
        vec = np.asarray(vectorize([s for _,s in queries] + [s for _,s in candidates]), dtype=np.float32)
        sims = vec[:len(queries)] @ vec[len(queries):].T
    except (ImportError, OSError, RuntimeError, ValueError):
        return {}
    results = {}
    for i, (rid, phrase) in enumerate(queries):
        wanted = concepts(phrase)
        for j in np.flatnonzero(sims[i] >= .70):
            exp, line = candidates[j]
            if _NEGATION.search(line) or missing_financial_context(wanted, concepts(line)):
                continue
            key = (rid, exp["experience_id"])
            score = min(.69, round(float(sims[i,j]) * .8, 2))
            if score > results.get(key, {}).get("score", 0):
                results[key] = {"kind": "related", "score": score, "title": exp["title"],
                                "quote": line, "terms": ["语义相近"]}
    return results
