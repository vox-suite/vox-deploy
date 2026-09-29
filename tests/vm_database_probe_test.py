import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    "vm_database_probe", Path(__file__).parents[1] / "scripts/check-vm-database.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CURRENT = "postgresql://postgres.project:fixture-old@db.example:5432/postgres"


class DatabaseProbeTests(unittest.TestCase):
    def test_vendor_ca_is_scoped_cleaned_up_and_password_stays_out_of_arguments(self):
        env = module.connection_environment(CURRENT, CURRENT)
        env["PGHOST"] = "aws-0-region.pooler.supabase.com"
        response, context = MagicMock(), MagicMock()
        response.__enter__.return_value.read.return_value = b"fixture vendor CA"
        certificates = []

        def run(command, **kwargs):
            mount = command[command.index("--mount") + 1]
            certificate = Path(mount.split("src=", 1)[1].split(",", 1)[0])
            certificates.append(certificate)
            self.assertEqual(certificate.read_bytes(), b"fixture vendor CA")
            self.assertEqual(certificate.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(env["PGPASSWORD"], " ".join(command))
            self.assertEqual(kwargs["env"]["PGSSLMODE"], "verify-full")
            self.assertEqual(kwargs["env"]["PGSSLROOTCERT"], "/run/vox-supabase-root.crt")
            return SimpleNamespace(returncode=2, stdout=b"", stderr=b"password authentication failed fixture-sensitive-value")

        with patch.object(module, "urlopen", return_value=response), patch.object(module.ssl, "create_default_context", return_value=context), patch.object(module.subprocess, "run", side_effect=run):
            with self.assertRaises(RuntimeError) as error:
                module.probe(env)
        self.assertNotIn("fixture-sensitive-value", str(error.exception))
        context.load_verify_locations.assert_called_once_with(cadata="fixture vendor CA")
        self.assertFalse(certificates[0].exists())

    def test_decodes_password_without_putting_it_in_command_arguments(self):
        candidate = "postgresql://postgres.project:fixture%24new%40password@db.example:5432/postgres"
        env = module.connection_environment(candidate, CURRENT)
        self.assertEqual(env["PGPASSWORD"], "fixture$new@password")
        self.assertEqual(env["PGSSLMODE"], "verify-full")
        self.assertEqual(env["PGSSLROOTCERT"], "system")

    def test_different_host_or_user_is_rejected(self):
        for candidate in [CURRENT.replace("db.example", "other.example"), CURRENT.replace("postgres.project", "other.project")]:
            with self.assertRaisesRegex(RuntimeError, "existing target"):
                module.connection_environment(candidate, CURRENT)

    def test_missing_password_is_rejected(self):
        with self.assertRaises(RuntimeError):
            module.connection_environment(CURRENT.replace(":fixture-old", ""), CURRENT)

    def test_fragment_or_wrong_protocol_is_rejected(self):
        for candidate in [CURRENT + "#fragment", CURRENT.replace("postgresql:", "https:")]:
            with self.assertRaises(RuntimeError):
                module.connection_environment(candidate, CURRENT)


if __name__ == "__main__":
    unittest.main()
