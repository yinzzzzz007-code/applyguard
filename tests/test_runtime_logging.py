import io
import logging
import sys
import unittest
from unittest.mock import patch

from backend.services.runtime_logging import configure_text_streams


class RuntimeLoggingTests(unittest.TestCase):
    def test_gbk_stream_does_not_interrupt_successful_unicode_log(self):
        data = io.BytesIO()
        stream = io.TextIOWrapper(data,encoding='gbk')
        with patch.object(sys,'stdout',stream),patch.object(sys,'stderr',stream):
            configure_text_streams()
            logger = logging.Logger('isolated-test')
            logger.addHandler(logging.StreamHandler(sys.stderr))
            logger.warning('✓ 向量生成完成')
            stream.flush()
            self.assertIn('✓ 向量生成完成',data.getvalue().decode('utf-8'))
        stream.close()

    def test_windowed_executable_without_standard_streams_can_log(self):
        with patch.object(sys,'stdout',None),patch.object(sys,'stderr',None):
            configure_text_streams()
            try:
                sys.stderr.write('✓ Unicode diagnostic\n')
                sys.stderr.flush()
            finally:
                sys.stdout.close()
                sys.stderr.close()
