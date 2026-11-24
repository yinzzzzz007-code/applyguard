import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from backend.services import agent_bridge, folder_picker as picker

class FolderPickerTests(unittest.TestCase):
    def setUp(self):
        self.state = patch.object(picker, '_JOB', None)
        self.state.start()
        self.addCleanup(self.state.stop)

    def process(self, output='', running=False):
        process = Mock(pid=456, returncode=0)
        process.poll.return_value = None if running else 0
        process.communicate.return_value = (output, '')
        return process

    def start(self, process):
        with patch.object(picker.subprocess, 'Popen', return_value=process):
            return agent_bridge.ui_call({'action': 'pick_folder'})

    def test_start_is_nonblocking_and_does_not_grant_access(self):
        process = self.process(running=True)
        before = set(agent_bridge.GRANTS)
        started = self.start(process)
        self.assertEqual(started['state'], 'pending')
        self.assertEqual(picker.folder_picker_status(started['picker_id']), {'state': 'pending'})
        process.communicate.assert_not_called()
        self.assertEqual(set(agent_bridge.GRANTS), before)
        with self.assertRaisesRegex(ValueError, '已有'):
            self.start(self.process(running=True))

    def test_selected_folder_is_returned_once_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            process = self.process(json.dumps({'path': directory, 'cancelled': False}))
            started = self.start(process)
            status = agent_bridge.ui_call({'action': 'folder_status', 'picker_id': started['picker_id']})
            self.assertEqual(status, {'state': 'selected', 'path': str(Path(directory).resolve())})
            self.assertEqual(picker.folder_picker_status(started['picker_id']), status)
            process.communicate.assert_called_once()

    def test_cancel_stops_owned_process_and_allows_restart(self):
        process = self.process(running=True)
        started = self.start(process)
        with patch.object(picker, '_stop') as stop:
            self.assertEqual(agent_bridge.ui_call({'action': 'cancel_folder', 'picker_id': started['picker_id']}), {'state': 'cancelled'})
            stop.assert_called_once_with(process)
        self.assertEqual(picker.folder_picker_status(started['picker_id']), {'state': 'cancelled'})
        self.assertNotEqual(self.start(self.process(running=True))['picker_id'], started['picker_id'])

    def test_native_cancel_does_not_add_path(self):
        started = self.start(self.process('{"cancelled":true}'))
        self.assertEqual(picker.folder_picker_status(started['picker_id']), {'state': 'cancelled'})

    def test_disk_root_is_rejected(self):
        started = self.start(self.process(json.dumps({'path': str(Path.cwd().anchor)})))
        result = picker.folder_picker_status(started['picker_id'])
        self.assertEqual(result['state'], 'error')
        self.assertIn('整盘', result['message'])

    def test_timeout_stops_picker_and_restores_retry(self):
        started = self.start(self.process(running=True))
        with patch.object(picker.time, 'monotonic', return_value=picker._JOB['started'] + 151), patch.object(picker, '_stop') as stop:
            self.assertEqual(picker.folder_picker_status(started['picker_id'])['state'], 'error')
            stop.assert_called_once()

    def test_bad_result_and_expired_id_are_explicit(self):
        started = self.start(self.process('invalid-json'))
        self.assertEqual(picker.folder_picker_status(started['picker_id'])['state'], 'error')
        with self.assertRaisesRegex(ValueError, '结束'):
            picker.folder_picker_status('wrong-id')
