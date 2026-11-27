"""Session-scoped pseudonyms for common contact and identity fields."""
from __future__ import annotations

import re
import secrets
import os
from threading import RLock


_PATTERN = re.compile(
    r'(?P<email>(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-]))'
    r'|(?P<identity>(?<![0-9A-Za-z])\d{17}[0-9Xx](?![0-9A-Za-z]))'
    r'|(?P<phone>(?<![0-9A-Za-z])(?:\+?86[ -]?)?1[3-9]\d[ -]?\d{4}[ -]?\d{4}(?![0-9A-Za-z]))'
)
_PROTOCOL_FIELDS = {'id', 'version', 'commit_sha', 'state', 'kind', 'purpose', 'mode', 'disclosure', 'error'}


class PrivacySession:
    def __init__(self):
        self.prefix = secrets.token_hex(8)
        self.values: dict[str, str] = {}
        self.reverse: dict[str, str] = {}
        self.lock = RLock()
        self.manual_terms: list[str] = []
        self.detected_terms: set[str] = set()
        self._rebuild_pattern()
        from backend.services.privacy_ner import status
        self.ner_status = status()
        if os.getenv('APPLYGUARD_PII_NER_MODE', 'auto') == 'required' and self.ner_status['state'] != 'available':
            raise ValueError(self.ner_status['notice'])

    def add_terms(self, terms):
        if not isinstance(terms, list) or len(terms) > 30:
            raise ValueError('敏感词须为列表，最多 30 项。')
        cleaned = []
        for term in terms:
            if not isinstance(term, str) or not 2 <= len(term.strip()) <= 80 or '[AG_' in term:
                raise ValueError('每个敏感词须为 2–80 个字符。')
            cleaned.append(term.strip())
        self.manual_terms = sorted(set(cleaned), key=len, reverse=True)
        self._rebuild_pattern()

    def _rebuild_pattern(self):
        terms=sorted(set(self.manual_terms)|self.detected_terms,key=len,reverse=True)
        existing = r'(?P<already>\[AG_[0-9a-f]{16}_(?:email|identity|phone|custom)_\d+\])'
        custom = '|(?P<custom>' + '|'.join(re.escape(t) for t in terms) + ')' if terms else ''
        self.pattern = re.compile(existing + custom + '|' + _PATTERN.pattern)

    def _token(self, original, kind):
        with self.lock:
            if original not in self.values:
                token = f'[AG_{self.prefix}_{kind}_{len(self.values) + 1}]'
                self.values[original] = token
                self.reverse[token] = original
            return self.values[original]

    def protect(self, value, *, use_ner=True):
        if isinstance(value, str):
            if use_ner and self.ner_status['state']=='available' and len(value)>=2:
                from backend.services.privacy_ner import detect
                try:
                    found=detect(value)
                except Exception:
                    raise ValueError('本地隐私模型检查失败，本次内容未发送；请检查模型或改用本地处理。') from None
                blocked=[m.span() for m in re.finditer(r'\[AG_[0-9a-f]{16}_(?:email|identity|phone|custom)_\d+\]',value)]
                terms={value[left:right] for left,right in found
                       if 2<=right-left<=80 and not any(left<end and right>begin for begin,end in blocked)}
                if terms:
                    with self.lock:
                        if len(self.detected_terms | terms)>200:
                            raise ValueError('待保护实体过多，请缩小材料范围。')
                        self.detected_terms.update(terms)
                        self._rebuild_pattern()
            def replace(match):
                if match.lastgroup == 'already':
                    return match.group(0)
                return self._token(match.group(0), match.lastgroup)
            return self.pattern.sub(replace, value)
        if isinstance(value, list):
            return [self.protect(item,use_ner=use_ner) for item in value]
        if isinstance(value, dict):
            result={}
            for key,item in value.items():
                if key in _PROTOCOL_FIELDS:
                    if isinstance(item,str) and _PATTERN.search(item):
                        raise ValueError('标识字段包含联系方式或证件号，请先修改后再发送。')
                    result[key]=item
                else:
                    result[key]=self.protect(item,use_ner=use_ner)
            return result
        return value

    def restore(self, value):
        if isinstance(value, str):
            with self.lock:
                pairs = list(self.reverse.items())
            for token, original in pairs:
                value = value.replace(token, original)
            return value
        if isinstance(value, list):
            return [self.restore(item) for item in value]
        if isinstance(value, dict):
            return {key: self.restore(item) for key, item in value.items()}
        return value
