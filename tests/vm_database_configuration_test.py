import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

spec = importlib.util.spec_from_file_location(
    "vm_database_configuration", Path(__file__).parents[1] / "scripts/configure-vm-database.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CURRENT = "postgresql://postgres.fdnwhzrojorrspvulsgk:old-fixture@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
PASSWORD = "fixture$secret@value'with%characters"


class DatabaseConfigurationTests(unittest.TestCase):
    def setup_files(self, directory):
        base, local = Path(directory) / "base.env", Path(directory) / "local.env"
        base.write_text("DATABASE_URL='" + CURRENT + "'\nOTHER=base\n")
        local.write_text("# retained\nVOX_CREDENTIAL_KEY=fixture-key\nVOX_MCP_OAUTH_CLIENTS='{}'\n")
        for path in (base, local):
            os.chmod(path, 0o600)
        return base, local

    def test_wrong_password_or_tls_failure_never_changes_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base, local = self.setup_files(directory)
            original = (base.read_bytes(), local.read_bytes(), local.stat().st_ino)
            with patch.object(module.database, "probe", side_effect=RuntimeError("probe rejected")):
                with self.assertRaisesRegex(RuntimeError, "probe rejected"):
                    module.configure(base, local, PASSWORD)
            self.assertEqual((base.read_bytes(), local.read_bytes(), local.stat().st_ino), original)

    def test_preserves_other_secrets_and_encodes_password_with_atomic_idempotent_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base, local = self.setup_files(directory)
            original_base, original_local = base.read_bytes(), local.read_text()
            with patch.object(module.database, "probe") as probe:
                module.configure(base, local, PASSWORD)
                probe.assert_called_once()
                self.assertEqual(probe.call_args.args[0]["PGPASSWORD"], PASSWORD)
                self.assertEqual(probe.call_args.args[0]["PGSSLMODE"], "verify-full")
                candidate = module.vm.env_value(local.read_text(), "DATABASE_URL")
                self.assertEqual(unquote(urlsplit(candidate).password), PASSWORD)
                self.assertNotIn("'", candidate)
                self.assertNotIn("$", candidate)
                self.assertEqual(base.read_bytes(), original_base)
                self.assertTrue(local.read_text().startswith(original_local))
                self.assertEqual(stat.S_IMODE(local.stat().st_mode), 0o600)
                inode = local.stat().st_ino
                module.configure(base, local, PASSWORD)
                self.assertEqual(local.stat().st_ino, inode)
                self.assertEqual(probe.call_count, 2)
            self.assertEqual(list(Path(directory).glob(".vox-local-env-*")), [])

    def test_concurrent_base_edit_is_detected_without_overwriting_local(self):
        with tempfile.TemporaryDirectory() as directory:
            base, local = self.setup_files(directory)
            original = local.read_bytes()
            def change_base(_):
                base.write_text(base.read_text() + "CONCURRENT=1\n")
            with patch.object(module.database, "probe", side_effect=change_base):
                with self.assertRaisesRegex(RuntimeError, "concurrently"):
                    module.configure(base, local, PASSWORD)
            self.assertEqual(local.read_bytes(), original)
            self.assertEqual(list(Path(directory).glob(".vox-local-env-*")), [])

    def test_wrong_target_is_rejected_before_probe(self):
        for current in (CURRENT.replace("fdnwhzrojorrspvulsgk", "another-project"),
                        CURRENT.replace(":5432", ":6543"), CURRENT + "#fragment",
                        CURRENT + "&unsafe='quoted"):
            with self.assertRaises(RuntimeError):
                module.candidate_url(current, PASSWORD)

    def test_empty_duplicate_or_insecure_local_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base, local = self.setup_files(directory)
            for content in ("DATABASE_URL=\n", "DATABASE_URL=x\n export DATABASE_URL = y\n"):
                local.write_text(content)
                with patch.object(module.database, "probe") as probe:
                    with self.assertRaises(RuntimeError):
                        module.configure(base, local, PASSWORD)
                    probe.assert_not_called()
            os.chmod(local, 0o644)
            with self.assertRaises(RuntimeError):
                module.configure(base, local, PASSWORD)

    def test_empty_oversized_or_control_character_passwords_are_rejected(self):
        for password in ("", "x" * 257, "value\nline", "value\r", "value\x00", " value"):
            with self.assertRaises(RuntimeError):
                module.candidate_url(CURRENT, password)


if __name__ == "__main__":
    unittest.main()
