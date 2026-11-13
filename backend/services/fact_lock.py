"""Source-bound facts and conservative edit checks for supported resume text.

This guard does not declare a proposal true. It only prevents a previously
supported detail from silently disappearing before the normal atomic verifier.
"""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from backend.services.edit_invariants import equivalent_point_detail, lost_qualifiers, qualifier_inventory

QUANTITY = (r"-?\d+(?:\.\d+)?(?:\s*(?:[%％]|个百分点|percentage\s+points?|pp\b|"
            r"milliseconds?\b|ms\b|seconds?\b|secs?\b|s\b|毫秒|秒|个?星期|个?周|天|人|个|次|年|万元|万|GB\b|MB\b))?")
# Calendar weeks and calendar days have a fixed conversion. Months and workdays do not.
CN_DIGITS = "零一二三四五六七八九"
CN_DAY_NUMBER = r"(?:[一二两三四五六七八九]?十[一二三四五六七八九]?|[一二两三四五六七八九])"
NUMBER = re.compile(r"(?<![0-9A-Za-z_.])" + QUANTITY +
                    r"|(?<![零〇一二两三四五六七八九十百千万第])" + CN_DAY_NUMBER + r"(?:天|个?周|个?星期)", re.I)
# Normalise the direction before comparing. "to B from A" preserves "from A to B".
TRANSITION = re.compile(
    rf"(?:\bfrom\s+|[从由])(?P<start>{QUANTITY})\s*"
    rf"(?:(?:(?:up|down)\s+)?\bto\s+|(?:提高|提升|上升|降低|下降|调整|升|增|降)?[至到]|变为|→|->)\s*(?P<end>{QUANTITY})"
    rf"|\bto\s+(?P<last>{QUANTITY})\s+from\s+(?P<first>{QUANTITY})", re.I)
METRIC = re.compile(r"\b(?:precision|recall|accuracy|latency|duration|throughput|cost|revenue|pass rate)\b"
                    r"|精确率|召回率|准确率|延迟|时延|耗时|吞吐量|成本|收入|通过率", re.I)
TARGET = re.compile(r"(?:[甲乙丙丁]方案|\bplan\s+[a-z]\b)", re.I)
EXPLICIT_SCOPE = re.compile(r'测试环境|生产环境|预生产环境|预发布环境|\b(?:test|testing|production|staging|sandbox)\s+environment\b|\bin\s+(?:production|staging|sandbox)\b', re.I)
ASSIGNED_ACTION = re.compile(
    r'(?P<person>[\u4e00-\u9fff]{1,4}?|\b[A-Z][a-z]{1,20})\s*'
    r'(?P<verb>负责|测试|部署|开发|实现|\b(?:tested|handled|deployed|implemented|developed)\b)\s*'
    r'(?P<object>[^，,；;。.!?\n]{1,100})', re.I)
APPROX_BEFORE = re.compile(
    r"(?:\b(?:approximately|roughly|about|around)|[约≈~]|近似|大约)"
    r"(?:为|(?:降低|提升|减少|增加|提高|下降)(?:了)?)?\s*$", re.I)
TECH = re.compile(r"(?<![A-Za-z0-9])(?:Python|JavaScript|TypeScript|Java|C\+\+|C#|"
                  r"PostgreSQL|SQL|Vue|React|Redis|Docker|Kubernetes|PyTorch|TensorFlow|"
                  r"Go|Rust|Spark|Flink)(?![A-Za-z0-9])", re.I)
CLAUSE = re.compile(r"[，,；;。.!?\n]+")
ROLE = re.compile(r"(?P<person>[\u4e00-\u9fff]{1,6}?(?:同学)?|[A-Z][a-z]{1,18})\s*"
                  r"(?P<verb>只负责|仅负责|负责|实现|开发|主导|协助|led|built|"
                  r"implemented|developed|assisted|helped|supported|owned)", re.I)
REVERSE_ROLE = re.compile(r"(?P<item>[^，,；;。.!?\n]{1,30}?)由(?P<person>[\u4e00-\u9fff]{1,4}?)"
                          r"(?:协助)?(?:负责|开发|实现)")
OWNER = re.compile(r"(?P<person>[\u4e00-\u9fff]{2,4})(?:是|为|担任)(?:项目)?负责人")
PASSIVE_OWNER = re.compile(r"(?:该)?项目由(?P<person>[\u4e00-\u9fff]{2,4})(?:负责|牵头)")
NEGATIVE_ROLE = re.compile(r"(?:未|没有|不|并未)(?:参与|负责|开发|实现)")


def source_bound_ledger(original: str, check: dict | None, sources: list[dict]) -> list[dict]:
    """Expose only checked facts with exact quotes from the current source snapshot."""
    if not isinstance(check, dict) or not check.get("complete"):
        return []
    by_id = {s.get("source_id"): s for s in sources if isinstance(s, dict)}
    rows = []
    for atom in check.get("atoms", []):
        if atom.get("relation") != "SUPPORTED":
            continue
        citations = atom.get("citations", [])
        if not isinstance(citations, list) or not citations:
            continue
        bindings = []
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            source = by_id.get(citation.get("source_id"))
            quote = citation.get("quote")
            if (source and isinstance(quote, str) and len(quote.strip()) >= 3
                    and quote in source.get("text", "")
                    and citation.get("source_sha256") == source.get("sha256")
                    and citation.get("source_version") == source.get("version")):
                start = source.get('text_offset', 0) + source['text'].find(quote)
                bindings.append({"source_id": source["source_id"], "quote": quote,
                                 "start": start, "end": start + len(quote),
                                 "source_sha256": source["sha256"],
                                 "source_version": source["version"]})
        if len(bindings) == len(citations):
            rows.append({"atom_id": atom.get("atom_id"), "text": atom["text"],
                         "bindings": bindings,
                         "quantity_links": _quantity_links(atom['text'])})
    return rows


def _numeric_key(value: str) -> str:
    value = re.sub(r"\s+", "", value).casefold()
    value = value.replace("％", "%")
    value = re.sub(r"percentagepoints?|个百分点", "pp", value)
    calendar = re.fullmatch(r"(-?\d+(?:\.\d+)?|" + CN_DAY_NUMBER + r")(天|个?星期|个?周)", value)
    if calendar:
        digits = calendar[1].replace("两", "二")
        if "十" in digits:
            tens, ones = digits.split("十")
            amount = (CN_DIGITS.index(tens) if tens else 1) * 10 + (CN_DIGITS.index(ones) if ones else 0)
        elif digits in CN_DIGITS:
            amount = CN_DIGITS.index(digits)
        else:
            amount = Decimal(digits)
        days = Decimal(amount) * (1 if calendar[2] == "天" else 7)
        return format(days.normalize(), 'f') + '天'
    duration = re.fullmatch(r"(-?\d+(?:\.\d+)?)(ms|milliseconds?|毫秒|s|secs?|seconds?|秒)", value)
    if duration:
        amount = Decimal(duration[1])
        if duration[2] not in {'ms', 'millisecond', 'milliseconds', '毫秒'}:
            amount *= 1000
        digits = format(amount, 'f')
        return (digits.rstrip('0').rstrip('.') if '.' in digits else digits) + 'ms'
    return value


def _numbers(text: str) -> Counter:
    return Counter(_numeric_key(m.group()) for m in NUMBER.finditer(text))


def _transitions(text: str):
    paths = []
    for match in TRANSITION.finditer(text):
        start = match['start'] or match['first']
        end = match['end'] or match['last']
        # Limit the metric to the same clause; a decimal point belongs to a value.
        clause = re.split(r"[，,；;。!?\n]|(?<!\d)\.|\.(?!\d)", text[:match.start()])[-1]
        names = list(METRIC.finditer(clause))
        metric = names[-1].group().casefold() if names else ''
        paths.append((metric, _numeric_key(start), _numeric_key(end)))
    return paths


def _approximate_values(text: str) -> Counter:
    result = Counter()
    for number in NUMBER.finditer(text):
        if (APPROX_BEFORE.search(text[:number.start()]) or
                re.match(r"\s*左右", text[number.end():])):
            result[_numeric_key(number.group())] += 1
    return result


def _quantity_links(text: str) -> list[dict]:
    """Extract explicit named targets and metrics; missing syntax is not evidence."""
    links = []
    for kind, pattern in (('target', TARGET), ('metric', METRIC)):
        matches = list(pattern.finditer(text))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            segment = text[match.end():end]
            values = _numbers(segment)
            if values:
                links.append({'kind': kind, 'name': re.sub(r'\s+', '', match.group()).casefold(),
                              'values': sorted(values.elements()),
                              'approximate': sorted(_approximate_values(segment).elements())})
    return links


def _linked_quantity_findings(original: str, proposal: str) -> list[str]:
    issues = []
    for kind, label in (('target', '对象'), ('metric', '指标')):
        before = [row for row in _quantity_links(original) if row['kind'] == kind]
        if len(before) < 2:
            continue
        after = [row for row in _quantity_links(proposal) if row['kind'] == kind]
        def indexed(rows):
            return Counter((row['name'], tuple(row['values']), tuple(row['approximate'])) for row in rows)
        if indexed(before) != indexed(after):
            issues.append(f'{label}与数值或近似限定的对应关系改变或无法确认')
    return issues


def _numeric_links(original: str, proposal: str) -> list[str]:
    """Catch explicit rebindings while allowing independent clauses to be reordered."""
    old, new = _transitions(original), _transitions(proposal)
    issues = []
    for metric in {m for m, _, _ in old} & {m for m, _, _ in new}:
        before = Counter((a, b) for m, a, b in old if m == metric)
        after = Counter((a, b) for m, a, b in new if m == metric)
        if before.total() == after.total() and before != after:
            issues.append("改变指标的起止数值：" + (metric or "原文数值区间"))
    old_approx, new_approx = _approximate_values(original), _approximate_values(proposal)
    lost = (old_approx - new_approx) & _numbers(proposal)
    added = (new_approx - old_approx) & _numbers(original)
    changed = lost | added
    if changed:
        issues.append("近似限定改变了对应数值：" + "、".join(sorted(changed)))
    return issues


def _relative_percent(text: str, value: str) -> bool:
    number = re.match(r"-?\d+(?:\.\d+)?", value)
    if not number:
        return False
    same = re.escape(number.group()) + r"\s*[%％]"
    return bool(re.search(r"(?:" + same + r".{0,18}(?:relative|相对)|"
                          r"(?:relative|相对).{0,18}" + same + r")", text, re.I))


def _technologies(text: str) -> set[str]:
    return {m.group().casefold() for m in TECH.finditer(text)}


def _role_pairs(text: str) -> set[tuple[str, str]]:
    """Preserve explicit person-to-technology links within the same clause."""
    pairs = set()
    for clause in CLAUSE.split(text):
        for match in ROLE.finditer(clause):
            if match["person"] in {"协助", "独立", "仅仅", "只", "仅", "未", "不", "没", "没有",
                                    "并未", "负责", "实现", "开发", "主导"}:
                continue
            # Stop at a second role declaration in the same clause.
            remainder = clause[match.end():]
            next_role = ROLE.search(remainder)
            if next_role:
                remainder = remainder[:next_role.start()]
            for tech in _technologies(remainder):
                pairs.add((match["person"].casefold(), tech))
        for match in REVERSE_ROLE.finditer(clause):
            for tech in _technologies(match["item"]):
                pairs.add((match["person"].casefold(), tech))
    return pairs


def _negative_role_tech(text: str) -> set[str]:
    denied = set()
    for clause in CLAUSE.split(text):
        for match in NEGATIVE_ROLE.finditer(clause):
            denied.update(_technologies(clause[match.end():match.end() + 35]))
    return denied


def locked_edit_findings(original: str, proposal: str, original_check: dict | None) -> list[str]:
    """Require review on provable losses, preserving ordinary paraphrase elsewhere."""
    if not isinstance(original_check, dict) or original_check.get("relation") != "SUPPORTED":
        return []
    if not original_check.get("complete"):
        return ["原句事实拆分不完整，不能自动采用润色。"]
    return wording_invariants(original, proposal)


# Compare only explicit active subjects. Unknown syntax remains with the semantic reviewer.
ACTIVE_ROLE = re.compile(r"\b(?P<person>I|We|[A-Z][a-z]+)\s+(?P<role>assisted|helped|led|headed|spearheaded)\b")
TRANSITIVE = re.compile(r"\b(?P<subject>[A-Z][a-z]+)\s+(?P<verb>interviewed|mentored|supervised|trained)"
                        r"\s+(?P<object>[A-Z][a-z]+)\b")


DIRECT_DELEGATION = re.compile(r"(?:^|[，,；;。!?\n])\s*([\u4e00-\u9fffA-Za-z]{2,24}?)\s*"
                               r"(委托|授权|聘请)\s*([\u4e00-\u9fffA-Za-z]{2,})")


def _actor_changes(original: str, proposal: str) -> list[str]:
    def roles(text):
        return {(m['person'], 'support' if m['role'] in {'assisted','helped'} else 'lead')
                for m in ACTIVE_ROLE.finditer(text)}
    old, new = roles(original), roles(proposal)
    changes = ["改变支持或主导职责的归属：" + person for person,role in sorted(new-old)
               if any(previous == person for previous,_ in old-new)]
    triples = {m.groups() for m in TRANSITIVE.finditer(proposal)}
    for m in TRANSITIVE.finditer(original):
        actor, verb, recipient = m.groups()
        if (recipient,verb,actor) in triples and (actor,verb,recipient) not in triples:
            changes.append("对调了行动人与对象：" + actor + " / " + recipient)
    for old_subject, verb, old_rest in DIRECT_DELEGATION.findall(original):
        for subject, new_verb, rest in DIRECT_DELEGATION.findall(proposal):
            if (verb == new_verb and subject != old_subject
                    and old_rest.startswith(subject) and rest.startswith(old_subject)):
                changes.append("对调了发起方与受托方：" + old_subject + " / " + subject)
    return changes


def _assignment_changes(original: str, proposal: str) -> list[str]:
    def assignments(text):
        return {(m['person'].casefold(), re.sub(r'\s+', ' ', (m['verb'] + ' ' + m['object']).strip()).casefold())
                for clause in CLAUSE.split(text) for m in ASSIGNED_ACTION.finditer(clause)}
    old, new = assignments(original), assignments(proposal)
    if (len({p for p, _ in old}) >= 2 and {p for p, _ in old} == {p for p, _ in new}
            and Counter(a for _, a in old) == Counter(a for _, a in new) and old != new):
        return ['改变了明确人员与具体职责的对应关系']
    return []


def _scope_changes(original: str, proposal: str) -> list[str]:
    def scopes(text):
        normal = {'测试环境': 'test', 'test environment': 'test', 'testing environment': 'test',
                  '生产环境': 'production', 'production environment': 'production', 'in production': 'production',
                  '预生产环境': 'staging', '预发布环境': 'staging', 'staging environment': 'staging',
                  'in staging': 'staging', 'sandbox environment': 'sandbox', 'in sandbox': 'sandbox'}
        return {normal[m.group().casefold()] for m in EXPLICIT_SCOPE.finditer(text)}
    old, new = scopes(original), scopes(proposal)
    return ['改变或遗漏明确的测试／生产环境'] if old != new and (old or new) else []


def _participial_estimate(original_estimate: str, proposal: str, person: str) -> bool:
    """Recognise 'Rae drafted a plan, estimating 20%' with one unambiguous subject."""
    pattern = (rf"(?:^|[.;!?]\s*){re.escape(person)}\s+(?:completed|prepared|drafted|created|wrote|finished)"
               r"\s+(?P<object>[^,;.!?]{1,120}),\s*(?:estimating|projecting|forecasting)\s+(?P<estimate>[^;!?]*)")
    old_clause = re.split(r"[;!?]|\.(?!\d)", original_estimate, maxsplit=1)[0]
    old_value = NUMBER.search(old_clause)
    for match in re.finditer(pattern, proposal, re.I):
        if re.search(r"\b(?:and|who|which|that|while|with|as|because)\b", match['object'], re.I):
            continue
        new_clause = re.split(r"[;!?]|\.(?!\d)", match['estimate'], maxsplit=1)[0]
        new_value = NUMBER.search(new_clause)
        if old_value and new_value and _numeric_key(old_value.group()) == _numeric_key(new_value.group()):
            return True
    return False


def reversed_cited_transition(text: str, quoted: str) -> bool:
    """Only a named, explicitly reversed path; allow another quote to supply the right path."""
    claims = _transitions(text)
    if not claims:
        return False
    sources = set(_transitions(quoted))
    return any(metric and start != end and (metric,end,start) in sources and
               (metric,start,end) not in sources for metric,start,end in claims)


def wording_invariants(original: str, proposal: str) -> list[str]:
    """Text-only constraints; this comparison establishes no source support."""
    findings = (_numeric_links(original, proposal) + _linked_quantity_findings(original, proposal)
                + _actor_changes(original, proposal) + _assignment_changes(original, proposal)
                + _scope_changes(original, proposal))
    old_deployed = 'not_deployed' in qualifier_inventory(original)
    new_deployed = 'not_deployed' in qualifier_inventory(proposal)
    if old_deployed != new_deployed:
        findings.append('改变或遗漏尚未部署的状态')
    # A passive estimate can keep the number while dropping the named estimator.
    for match in re.finditer(r"\b([A-Z][a-z]+)\s+(?:estimated|projected|forecast)\b", original):
        person = match[1]
        name = re.escape(person)
        explicit = rf"\b{name}\s+(?:(?:has|had)\s+)?(?:estimated|projected|forecast)|\b{name}['’]s\s+(?:estimate|projection|forecast)|(?:estimated|projected|forecast)\s+by\s+{name}\b"
        if not (re.search(explicit, proposal, re.I) or
                _participial_estimate(original[match.end():], proposal, person)):
            findings.append("省略了估算人：" + person)
    leadership = r'主导|牵头|独立负责|独立完成|\b(?:led|headed|spearheaded|independently)\b'
    if re.search(leadership, proposal, re.I) and not re.search(leadership, original, re.I):
        findings.append("新增主导或独立职责")
    for item in lost_qualifiers(original, proposal):
        findings.append("遗漏原句限定条件：" + item["detail"])
    old_numbers, new_numbers = _numbers(original), _numbers(proposal)
    old_forms = {_numeric_key(m.group()): m.group().strip()
                 for m in NUMBER.finditer(original)}
    for value in new_numbers - old_numbers:
        findings.append("新增数字／单位：" + value)
    for tech in sorted(_technologies(proposal) - _technologies(original)):
        findings.append("新增技术：" + tech)
    for value in old_numbers - new_numbers:
        if (equivalent_point_detail(old_forms[value], original, proposal)
                and not _relative_percent(proposal, old_forms[value])):
            continue
        findings.append("遗漏或改变原有数字／单位：" + value)
    for tech in sorted(_technologies(original) - _technologies(proposal)):
        findings.append("遗漏原有技术：" + tech)
    for person, tech in sorted(_role_pairs(original) - _role_pairs(proposal)):
        findings.append("改变人物与技术的归属：" + person + " / " + tech)
    for tech in sorted(_negative_role_tech(original) - _negative_role_tech(proposal)):
        findings.append("删除未负责该技术的限制：" + tech)
    old_owners = {m["person"] for pattern in (OWNER, PASSIVE_OWNER)
                  for m in pattern.finditer(original)}
    new_owners = {m["person"] for pattern in (OWNER, PASSIVE_OWNER)
                  for m in pattern.finditer(proposal)}
    for person in sorted(old_owners - new_owners):
        findings.append("遗漏原文明确的负责人：" + person)
    return list(dict.fromkeys(findings))
