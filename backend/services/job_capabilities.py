"""Source-grounded job units and reusable skill concepts for local recommendation."""
from __future__ import annotations

import re
from functools import lru_cache
from backend.services.jd_match_scope import _HEADER, _header_kind

# Each pattern names a capability, not a candidate, employer or target vacancy.
_PATTERNS = {
    "代码智能体": r"code\s*agents?|coding\s*agents?|代码智能体|代码代理|代码任务",
    "开发工具调用": r"使用开发工具|调用开发工具|工具调用|tool[- ]calling|function[- ]calling",
    "长程任务": r"长程任务|长时程|long[- ]horizon|多步推理",
    "指令遵循": r"指令遵循|instruction[- ]following",
    "智能体": r"agents?|智能体",
    "大模型": r"(?:[mv]?llms?)|大(?:语言)?模型|语言模型|qwen[\d.]*|nemotron|llama[\d.]*",
    "后训练": r"后训练|post[- ]?training|sft|lora|微调|fine[- ]?tuning",
    "强化学习": r"强化学习|reinforcement learning|rl(?:hf)?|grpo|ppo|dpo",
    "训练数据": r"训练数据|数据构建|构造.{0,4}数据|数据构造|数据清洗|错误样本|数据回流|训练样本",
    "质量评测": r"评测|benchmark(?:s)?|evaluat(?:ion|e|ed)|消融实验|ragas|留出数据",
    "推理优化": r"推理(?:时延|优化|策略|引擎|性能)|kv\s*cache|gpu\s*profiling|llm inference|推理加速",
    "模型训练": r"模型训练|深度学习训练|训练模型|预训练|神经网络训练|sft|lora|微调|训(?:练|训)代码",
    "机器学习": r"机器学习|machine learning|深度学习|deep learning|神经网络",
    "检索增强": r"rag|检索增强|向量检索|qdrant|retrieval augmented",
    "数据分析": r"数据分析|统计建模|data analysis|数据挖掘|因果推断",
    "材料研发": r"材料加工|材料力学|材料表征|材料学|冶金|合金|高分子|电子功能材料|材料(?:高级)?工程师|材料失效|复合材料",
    "训练推理基础设施": r"ai[ -]*infra|训练推理算子|训推系统|算子(?:库|性能|开发|加速|融合)|算子.{0,4}优化|高性能计算|推理引擎|推理优化|推理加速|inference engine|cuda|cublas|gemm|kv\s*cache|vllm|triton",
    "海关贸易": r"清关|报关|海关|关税|国际贸易|进出口|customs|import.export",
    "供应链履约": r"订单履(?:行|约)|订单管理|供应链(?:管理|履约)|交付计划|supply.chain management|order fulfillment",
    "具身机器人": r"具身|机器人|自动驾驶|robotics?|embodied|autonomous driving",
    "信息安全": r"网络安全|安全与隐私|信息安全|模型安全|数据安全|访问控制|数据权限|隐私保护|access control|cybersecurity|privacy protection",
    "机械设计": r"机械设计|机械结构|精密结构设计|功能结构设计|结构可靠性|力学设计|有限元|力学仿真|精密仪器",
    "分布式系统": r"分布式|distributed systems?|负载均衡",
    "测试开发": r"单元测试|自动化测试|unit tests?|test automation",
    "前端开发": r"前端|react(?:js)?|vue(?:js)?",
    "数据库": r"postgres(?:ql)?|mysql|数据库|sql",
    "金融研究": r"金融|量化研究|投资组合|资产定价|债券|证券|信用利差|资产配置|quantitative (?:research|finance)|financial|fixed income|bond (?:pricing|spread)|portfolio|investment banking|asset allocation",
    "估值回测": r"估值|回测|valuation|back[- ]?test(?:ing)?|asset pricing|sharpe|dcf",
    "软件开发": r"软件开发|开发应用|应用开发|software engineer(?:ing)?|application development|(?:web|mobile|android|ios|desktop) application|backend for|back[- ]end development|software develop(?:er|ment)|full[- ]stack|(?:implemented|built|developed|mocked|created)\s+[^.;。]{0,45}(?:system|application|service|platform|backend|library)",
    "模型评估": r"模型评估|model evaluation|predictive accuracy|模型评测",
    "GPU计算": r"gpus?|gpu computing|gemm|cublas|tpus?|tensor processing units?|graphics processing units?",
    "研究产出": r"论文|共同第一作者|一作|学术研究|研究记录|published|publication",
    "问题分析": r"错误分析|错误样本|误差分析|问题分析|资源开销|定位瓶颈",
}
FRAMEWORKS = {"PyTorch": r"pytorch|torch", "TensorFlow": r"tensorflow", "JAX": r"jax",
              "PaddlePaddle": r"paddlepaddle|paddle|飞桨", "MindSpore": r"mindspore|昇思",
              "Keras": r"keras"}
_PATTERNS.update(FRAMEWORKS)
for _tool in ("Python", "Java", "JavaScript", "CUDA", "C++", "Go", "Docker", "Kubernetes", "Rust", "MATLAB"):
    _PATTERNS[_tool] = re.escape(_tool)
_MATCHERS = {key: re.compile(r"(?<![a-z0-9])(?:" + pattern + r")(?![a-z0-9])", re.I)
             for key, pattern in _PATTERNS.items()}
_GENERIC = re.compile(r"代码能力|编程能力|数据结构|基础算法|沟通|认同团队|团队合作|学习能力|自驱力|coding skills|communication skills", re.I)
_DUTY = re.compile(r"^(?:参与|负责|构建|建设|支持|使用|跟踪|优化|提升|开发|研究|设计|实现|协助|面向|建立|进行|开展|维护|主导|打造|探索|build|maintain|design|develop|implement|support|collaborate|lead|improve|work\s+on)\s*", re.I)
_LIST = re.compile(r"^(?:[-•●]\s*|[\d一二三四五六七八九十]+[.、．)）]\s*)")
_CONTEXT = re.compile(r"^(?:团队介绍|团队简介|公司介绍|部门介绍|关于我们|team overview|about us|我们正在招聘|我们是)", re.I)
_PREF = re.compile(r"优先|加分|preferred|nice[- ]to[- ]have", re.I)
_ANY = re.compile(r"任[一意]|至少一|其中一|之一|either|one of|或", re.I)

@lru_cache(maxsize=8192)
def concepts(text: str) -> frozenset[str]:
    found = set()
    for label, pattern in _MATCHERS.items():
        for match in pattern.finditer(text):
            if not re.search(r"未(?:使用|采用)|没有(?:使用|采用)|不(?:使用|采用)|未用|without\s+|did not use\s+", text[max(0, match.start()-15):match.start()], re.I):
                found.add(label)
                break
    return frozenset(found)


def job_units(source: str, initial: str = ""):
    section = initial
    for raw in source.splitlines():
        line = raw.strip()
        header = _HEADER.match(line)
        if header:
            section = _header_kind(line)
            line = line[header.end():].strip()
        if not line or section not in {"description", "requirement", "bonus"}:
            continue
        for fragment in re.split(r"[；;]|(?<=。)(?=\s*\d+[、.])", line):
            fragment = fragment.strip()
            numbered = _LIST.match(fragment)
            phrase = _LIST.sub("", fragment).strip().rstrip("。").rstrip()
            if not phrase or _CONTEXT.match(phrase) or re.search(r"不(?:要求|需要)|无需|not required|no.{0,32}required", phrase,re.I):
                continue
            if section == "description" and not (numbered or _DUTY.match(phrase)):
                continue
            yield section, phrase


def qualifications(phrase: str):
    # Separate independently qualified clauses. A list of alternatives stays intact.
    parts = re.split(r"(?:、(?=数据结构)|[，,](?=\s*(?:熟练|熟悉|掌握|精通|在.{0,20}(?:研究记录|经验).{0,4}优先|尤其.{0,30}优先|能深入|数据结构|[^，,；。]{2,35}专业优先)))", phrase)
    return [p.strip() for p in parts if p.strip()]


def framework_group(phrase: str):
    return bool("框架" in phrase or re.search(r"framework", phrase, re.I)) and (
        bool(FRAMEWORKS.keys() & concepts(phrase)) or bool(re.search(r"深度学习框架|deep.learning framework", phrase, re.I)))


def priority(phrase: str, section: str):
    if section == "bonus" or _PREF.search(phrase):
        return "preferred"
    if _GENERIC.search(phrase) and not concepts(phrase):
        return "general"
    return "core"


def structure(parsed: dict, unsafe) -> dict:
    source = parsed["source_text"]
    units = [(sec, phrase) for sec, phrase in job_units(source) if not unsafe(phrase)]
    if not units:
        return parsed
    previous = parsed["requirements"]
    result = []
    seen = set()
    for section, phrase in units:
        for part in ([phrase] if section == "description" else qualifications(phrase)):
            if (section, part) in seen:
                continue
            seen.add((section, part))
            template = next((row for row in previous if (row["evidence_text"] in phrase or phrase in row["evidence_text"]) and
                             (part in row["evidence_text"] or row["evidence_text"] in part)), {})
            terms = [term for term in template.get("normalized_terms", []) if term.casefold() in part.casefold()]
            if part == template.get("evidence_text"):
                terms = list(template["normalized_terms"])
            terms.extend(label for label in concepts(part) if label.casefold() in part.casefold())
            weight = priority(part, section)
            options = [name for name in FRAMEWORKS if name in concepts(part)] if framework_group(part) and _ANY.search(part) else []
            result.append({
                "requirement_id": f"req_{len(result)+1:03d}", "text": part, "evidence_text": part,
                "category": "RESPONSIBILITY" if section == "description" else template.get("category", "SKILL"),
                "type": "PREFERRED" if weight == "preferred" else "HARD", "priority": weight,
                "section": section, "alternatives": options,
                "normalized_terms": sorted(set(terms)), "confidence": template.get("confidence", .5),
            })
    first_section = _HEADER.search(source.splitlines()[0]) if source else None
    intro = []
    if not first_section:
        prefix_lines = []
        for line in source.splitlines():
            if _HEADER.match(line):
                break
            prefix_lines.append(line)
        prefix = "\n".join(prefix_lines)
        intro = [row for row in previous if row["evidence_text"] in prefix and
                 (row["category"] == "EDUCATION" or re.search(r"\d{4}届", row["text"]))]
    if not result:
        return parsed
    rows = intro + result
    for i, row in enumerate(rows, 1):
        row["requirement_id"] = f"req_{i:03d}"
    return {**parsed, "requirements": rows}
