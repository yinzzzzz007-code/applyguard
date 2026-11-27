"""Optional, local-only ONNX PII recognizer. Never downloads or transmits input."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path

from backend.services.local_store import local_dir, ROOT

MODEL_SHA256 = '59d961cb82813dfc2695509269e4a75f764f495c05a03dcfb13c9e6c0816abbb'
TOKENIZER_SHA256 = 'f34b44a6dc8a0eef651bfa10e8325057530152606a69d9c3b6ae02efb1558f0a'
DIRECT_IDENTIFIERS = {'GIVENNAME', 'SURNAME', 'EMAIL', 'TELEPHONENUM', 'IDCARDNUM',
                      'PASSPORTNUM', 'DRIVERLICENSENUM', 'TAXNUM', 'SOCIALNUM', 'CREDITCARDNUMBER'}
NAME_LABELS = {'GIVENNAME', 'SURNAME'}
COMMON_SURNAMES='王李张刘陈杨黄赵周吴徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董潘袁于余叶蒋杜苏魏程吕丁沈任姚卢姜崔钟谭陆汪范金石廖贾夏韦傅方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严武戴莫孔向汤'
NAME_SUBJECT=re.compile(r'(['+COMMON_SURNAMES+r'][\u4e00-\u9fff]{1,2}?)(?=参与|负责|完成|开发|设计|实现|主导|协助|分析|测试|编写|在)')
CHINESE_SURNAMES = frozenset('赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公')
MAX_TEXT_CHARS = 40000
_LOAD_LOCK = threading.Lock()


def model_directory():
    configured=os.getenv('APPLYGUARD_PII_NER_DIR','').strip()
    if configured:return Path(configured).resolve()
    local=local_dir()/'models/privacy-ner'
    bundled=ROOT/'data/local/models/privacy-ner'
    return (local if (local/'config.json').is_file() else bundled).resolve()


def status():
    if os.getenv('APPLYGUARD_PII_NER_MODE', 'auto') == 'off':
        return {'state':'disabled', 'notice':'本地隐私模型已关闭。'}
    root = model_directory()
    if not all((root / p).is_file() for p in ('config.json', 'tokenizer.json', 'onnx/model_quantized.onnx')):
        return {'state':'missing', 'notice':'未安装本地隐私模型，仍使用格式规则和自定义敏感词。'}
    if not importlib.util.find_spec('onnxruntime') or not importlib.util.find_spec('tokenizers'):
        return {'state':'missing_runtime', 'notice':'隐私模型运行依赖不可用，仍使用格式规则和自定义敏感词。'}
    return {'state':'available', 'notice':'已检测到本地隐私模型，首次使用时校验；识别结果仍需人工核对。'}


def _sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


@lru_cache(maxsize=1)
def _load(root: str):
    from onnxruntime import InferenceSession, SessionOptions
    from tokenizers import Tokenizer
    directory=Path(root)
    model=directory/'onnx/model_quantized.onnx'
    tokenizer_file=directory/'tokenizer.json'
    if _sha(model)!=MODEL_SHA256 or _sha(tokenizer_file)!=TOKENIZER_SHA256:
        raise ValueError('本地隐私模型校验失败，请重新安装。')
    config_bytes=(directory/'config.json').read_bytes()
    if hashlib.sha1(f'blob {len(config_bytes)}\0'.encode()+config_bytes).hexdigest()!='809f6e0ca7fbcf348d847c129007939a51c21548':
        raise ValueError('本地隐私模型配置校验失败，请重新安装。')
    config=json.loads(config_bytes)
    labels=config.get('id2label')
    if not isinstance(labels,dict) or len(labels)!=41:
        raise ValueError('本地隐私模型标签无效。')
    tok=Tokenizer.from_file(str(tokenizer_file))
    tok.enable_truncation(max_length=512)
    options=SessionOptions()
    options.intra_op_num_threads=2
    session=InferenceSession(str(model),options,providers=['CPUExecutionProvider'])
    return tok,session,labels


def detect(text: str) -> list[tuple[int,int]]:
    if not text or len(text)<2:return []
    if len(text)>MAX_TEXT_CHARS:raise ValueError('待检查内容过长，请拆分后再发送。')
    import numpy as np
    with _LOAD_LOCK:
        tok,model,labels=_load(str(model_directory()))
    spans=[]
    for start in range(0,len(text),268):
        chunk=text[start:start+300]
        if not chunk:break
        enc=tok.encode(chunk)
        if len(enc.ids)>=512:
            raise ValueError('本地隐私模型输入超过分词上限，请缩小材料范围。')
        logits=model.run(None, {'input_ids':np.asarray([enc.ids],dtype=np.int64),
                                'attention_mask':np.asarray([enc.attention_mask],dtype=np.int64)})[0][0]
        labels_out=logits.argmax(axis=-1)
        active=None
        for idx,((left,right),number) in enumerate(zip(enc.offsets,labels_out)):
            label=labels.get(str(int(number)),'O')
            category=label[2:] if label.startswith(('B-','I-')) else ''
            row=logits[idx]; peak=float(row.max()); confidence=1.0/float(np.exp(row-peak).sum())
            if not (right>left and category in DIRECT_IDENTIFIERS and confidence>=0.5):
                if active:spans.append(active);active=None
                continue
            pair=(start+left,start+right,category)
            if active and pair[0]<=active[1] and (category==active[2] or category in NAME_LABELS and active[2] in NAME_LABELS):
                active=(active[0],max(active[1],pair[1]),category)
            else:
                if active:spans.append(active)
                active=pair
        if active:spans.append(active)
    spans.extend((m.start(1),m.end(1),'GIVENNAME') for m in NAME_SUBJECT.finditer(text)
                 if m.group(1) not in {'项目','团队','系统','工作','用户','公司','学生'})
    merged=[]
    for left,right,category in sorted(spans):
        if category=='GIVENNAME' and left>0 and text[left-1] in CHINESE_SURNAMES:
            left-=1
        if category in NAME_LABELS and right-left<2:continue
        if merged and left<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],right))
        else:merged.append((left,right))
    return merged
