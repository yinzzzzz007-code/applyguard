from .baidu import Baidu
from .bytedance_seed import BytedanceSeed
from .huawei import Huawei

SOURCES = {adapter.source_id: adapter for adapter in (Baidu, Huawei, BytedanceSeed)}
