# Third-party notices

## Resume Matcher bullet selector

`backend/services/third_party/resume_matcher_bullet_selector.py` retains the unmodified implementation from [`srbhr/Resume-Matcher`](https://github.com/srbhr/Resume-Matcher), upstream commit `9c05e423dfde44a5b4bb398d2dc7507194252ded`, path `apps/backend/app/services/bullet_selector.py`.

Copyright notices and license terms are retained under the Apache License, Version 2.0. A copy of that license is in [third_party_licenses/Apache-2.0.txt](third_party_licenses/Apache-2.0.txt). ApplyGuard's `ResumeSelector` only adapts its own Claim objects to this upstream bullet-selection interface.

## ASu Resume Skills metric arithmetic

`backend/services/third_party/asu_metric_validation.py` retains the unmodified `fail` and `validate_metric` functions from [`Claycui828/ASu-resume-skills`](https://github.com/Claycui828/ASu-resume-skills), upstream commit `f460582b1a48c7770496d7999ae3a14a2ce0452b`, path `skills/asu-resume-audit-skill/scripts/validate_report.py`.

Copyright (c) 2026 Claycui828. The MIT license text is in [third_party_licenses/ASu-MIT.txt](third_party_licenses/ASu-MIT.txt). ApplyGuard's Career Vault adapter calls this arithmetic-only function for optional structured metric data. No upstream Skill prompt, personal-data example, final Claim Validator, or report renderer was copied.
