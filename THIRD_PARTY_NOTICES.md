# Third-party notices

## Hisn00w ASu-skills original great-resume resources (2026-10-30)

`third_party/asu-skills/` retains six byte-identical files from
[`Hisn00w/ASu-skills`](https://github.com/Hisn00w/ASu-skills), commit
`d27fd2a3864c48472a5c8ed942410098ba9cd35f` (2026-10-28 01:14:31 UTC):
the MIT LICENSE, `skills/great-resume/SKILL.md`, its two evidence references,
`assets/career-claim-ledger-template.json`, and `scripts/validate_claim_ledger.py`.
Copyright (c) 2026 Hisn00w. The full original [MIT license](third_party/asu-skills/LICENSE)
and Git blob/SHA256 manifest in `third_party/asu-skills/UPSTREAM.json` are retained.

ApplyGuard's `backend/services/asu_resume.py` injects the unchanged writing resources
into its explicitly requested polish operation. It supplies application-specific
scope and structured-output constraints; upstream status labels never grant
ApplyGuard verification. Claim checking, approval, history, and interface remain
ApplyGuard implementations. The ledger template/validator are retained reference
tools, not replacements for claim-truth verification. No global plugin is installed.
This is separate from the older Claycui828 arithmetic helper described below.

AI Career Radar was rechecked on 2026-10-30: main is still
`0ca459b3f6975d93a08cc5eea7adfca7e2a89b5c` (2026-09-28 04:03:17 UTC).
The complete repository tree, README and package manifests contain no identified
project license grant. No new source copying is performed; the existing API adapter
remains in use pending a suitable license or explicit author permission.

## AI Career Radar API interoperability

ApplyGuard's opportunity library and loopback HTTP adapter interoperate with [`Haoyu-Gu/ai-career-radar`](https://github.com/Haoyu-Gu/ai-career-radar), inspected at commit `0ca459b3f6975d93a08cc5eea7adfca7e2a89b5c`. Only its public `GET /api/jobs` and `GET /api/jobs/{id}` response shapes are used. No upstream source code, UI assets, configuration, personal profile, model scoring weights, or runtime database is redistributed. No license file was present in that inspected revision. See `docs/career-radar-integration.md` for the independently implemented integration and its limits.

## Resume Matcher bullet selector

`backend/services/third_party/resume_matcher_bullet_selector.py` retains the unmodified implementation from [`srbhr/Resume-Matcher`](https://github.com/srbhr/Resume-Matcher), upstream commit `9c05e423dfde44a5b4bb398d2dc7507194252ded`, path `apps/backend/app/services/bullet_selector.py`.

Copyright notices and license terms are retained under the Apache License, Version 2.0. A copy of that license is in [third_party_licenses/Apache-2.0.txt](third_party_licenses/Apache-2.0.txt). ApplyGuard's `ResumeSelector` only adapts its own Claim objects to this upstream bullet-selection interface.

## ASu Resume Skills metric arithmetic

`backend/services/third_party/asu_metric_validation.py` retains the unmodified `fail` and `validate_metric` functions from [`Claycui828/ASu-resume-skills`](https://github.com/Claycui828/ASu-resume-skills), upstream commit `f460582b1a48c7770496d7999ae3a14a2ce0452b`, path `skills/asu-resume-audit-skill/scripts/validate_report.py`.

Copyright (c) 2026 Claycui828. The MIT license text is in [third_party_licenses/ASu-MIT.txt](third_party_licenses/ASu-MIT.txt). ApplyGuard's Career Vault adapter calls this arithmetic-only function for optional structured metric data. No upstream Skill prompt, personal-data example, final Claim Validator, or report renderer was copied.

## Resume Matcher JD input helpers (C)

`backend/services/third_party/resume_matcher_keywords.py` retains `_INJECTION_PATTERNS`, `_sanitize_user_input`, and `_validate_string_list_field` from the same Resume Matcher commit above, original path `apps/backend/app/services/improver.py`. The bodies of these selected helpers are unchanged; C added only module imports and a provenance docstring. The Apache-2.0 license above covers this file as well.

`JDParser` calls the input sanitization and list validation helpers. Its source-span verification, Parsed JD adapter, model transport, deterministic fallback, Claim Validator, Risk Engine, and Router are ApplyGuard code. Upstream `extract_job_keywords` was not copied because it imports Resume Matcher app services and returns keyword groups rather than ApplyGuard requirements with checked source spans. Plan-Then-Execute was not copied; its reuse requires redistribution evidence that is not in this repository, so C implements the router locally. ASu's full `validate_data` targets a different report schema and is not used for ApplyGuard claim truth decisions.


# 本次集成的依赖与研究来源

- zleap-sag 0.15.0：直接运行的核心引擎，MIT。保留安装包 LICENSE 的副本于 `third_party_licenses/zleap-sag-0.15.0-MIT.txt`。源码入口 https://github.com/Zleap-AI/zleap ，应用说明 https://github.com/Zleap-AI/SAG 。
- SAG 应用：参考官方说明，MIT 文本保存于 `third_party_licenses/SAG-MIT.txt`。未复制整套应用界面。
- FActScore：https://github.com/shmsw25/FActScore 。参考原子事实分解与支持度评估思想；本次是适配实现，未复制其完整运行管线。官方 MIT 文本作为来源记录保留。
- ALCE：https://github.com/princeton-nlp/ALCE 。参考引文支持度评测思想；没有运行官方基准。官方 MIT 文本作为来源记录保留。

原有 ApplyGuard 源码与文件仍保留上游声明。本文件不改变其许可，也不代表对整套项目授予新的许可。其他传递依赖遵守各自随包许可；本地锁文件记录已安装版本。

## Kinetic reel、Three.js 与本机托管字体（2026-10-30）

新版通用新手引导复用 tuzhechen2005/opus-video-skills 的 kinetic-reel
模板核心，提交 59744a69c7b916cfbe4c4ec84006b0c2f5e2fde1。
原模板与 MIT 许可见 vendor/kinetic-reel/，适配生成脚本见
scripts/build-kinetic-adapter.py 和 scripts/kinetic-score.mjs。
原作者及 Three.js 的 MIT 声明保留在
[前端许可](frontend/public/licenses/kinetic-reel-and-three-MIT.txt)。
这部分不能归作 Gitvextor 独立原创。

Anton、Archivo Black、Instrument Serif 字体本机托管，
各自 OFL 许可保存在 frontend/public/assets/fonts/ 中。
配乐由模板合成器适配生成，无外部音频采样；用户主动开启声音后播放。
