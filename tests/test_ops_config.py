import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('ops_manage', Path(__file__).resolve().parents[1] / 'ops/manage.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class OpsConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = {source: ('content:' + source).encode() for source in manage.FILES}
        for source, (target, mode) in manage.FILES.items():
            manage.atomic_write(self.root / target, self.sources[source], mode)

    def test_installed_files_match(self):
        manage.compare_files(self.sources, self.root)

    def test_manual_edit_is_detected(self):
        target = self.root / manage.FILES['ops/meowbillion-backup'][0]
        target.write_text('local edit')
        with self.assertRaisesRegex(RuntimeError, 'content differs'):
            manage.compare_files(self.sources, self.root)

    def test_missing_file_is_detected(self):
        (self.root / manage.FILES['ops/manage.py'][0]).unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing'):
            manage.compare_files(self.sources, self.root)

    def test_permissions_are_checked(self):
        (self.root / manage.FILES['ops/meowbillion-backup'][0]).chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'permissions differ'):
            manage.compare_files(self.sources, self.root)

    def test_symlink_is_not_an_installed_copy(self):
        target = self.root / manage.FILES['ops/meowbillion-backup'][0]
        other = self.root / 'other'
        target.rename(other)
        target.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, 'content differs'):
            manage.compare_files(self.sources, self.root)

    def test_private_config_cannot_override_other_environment(self):
        self.assertEqual(manage.folder_id('# comment\nGDRIVE_ROOT_FOLDER_ID=example-id_1\n'), 'example-id_1')
        for value in ('GDRIVE_ROOT_FOLDER_ID=\n', 'GDRIVE_ROOT_FOLDER_ID=example\nPATH=/tmp', 'GDRIVE_ROOT_FOLDER_ID=$(command)'):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                manage.folder_id(value)

    def test_uncommitted_ops_are_rejected(self):
        with patch.object(manage, 'git', return_value=' M ops/manage.py'):
            with self.assertRaisesRegex(RuntimeError, 'Commit all ops changes'):
                manage.committed_sources()

    def test_systemd_override_is_rejected(self):
        with patch.object(manage, 'run', side_effect=['/etc/systemd/system/meowbillion.service', '/etc/systemd/system/meowbillion.service.d/local.conf']):
            with self.assertRaisesRegex(RuntimeError, 'override'):
                manage.check_loaded_units()

    def test_stale_loaded_config_is_rejected(self):
        with patch.object(manage, 'run', side_effect=['/etc/systemd/system/meowbillion.service', '', 'yes']):
            with self.assertRaisesRegex(RuntimeError, 'daemon-reload'):
                manage.check_loaded_units()
