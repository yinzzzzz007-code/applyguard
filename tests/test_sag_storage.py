import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend.services import sag_storage as storage
from backend.services.sag_grounding import GroundingUnavailable

class SagStorageTests(unittest.TestCase):
    def tearDown(self):
        storage.resolve_index_directory.cache_clear()
        storage.check_index_directory.cache_clear()

    def test_unsupported_source_uses_compatible_cache_without_moving_materials(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{}):
            source=Path(root)/'portable';target=Path(root)/'compatible'
            def check(value):
                if Path(value)==source:raise GroundingUnavailable('unsupported')
                Path(value).mkdir(parents=True,exist_ok=True)
            with patch.object(storage,'check_index_directory',side_effect=check),patch.object(storage,'fallback_directories',return_value=[target]):
                self.assertEqual(storage.resolve_index_directory(str(source)),target.resolve())
                self.assertFalse(source.exists())
                self.assertEqual(Path(os.environ['TMP']),target.parent/'tmp')

    def test_supported_explicit_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as root,patch.object(storage,'fallback_directories',side_effect=AssertionError('must not relocate')):
            self.assertEqual(storage.resolve_index_directory(root),Path(root).resolve())

    def test_no_writable_fallback_reports_failure(self):
        with patch.object(storage,'check_index_directory',side_effect=GroundingUnavailable('unsupported')),patch.object(storage,'fallback_directories',return_value=[]):
            with self.assertRaisesRegex(GroundingUnavailable,'未找到'):
                storage.resolve_index_directory('unsupported')
