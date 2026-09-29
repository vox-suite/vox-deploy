import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "vm_database_probe", Path(__file__).parents[1] / "scripts/check-vm-database.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CURRENT = "postgresql://postgres.project:fixture-old@db.example:5432/postgres"


class DatabaseProbeTests(unittest.TestCase):
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
