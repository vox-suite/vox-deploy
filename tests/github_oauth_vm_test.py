import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "github_oauth_vm", Path(__file__).parents[1] / "scripts/configure-github-oauth-vm.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SECRET = "test-secret-12345678901234567890"


class VmConfigurationTests(unittest.TestCase):
    def test_preserves_encryption_key_and_other_provider_values(self):
        providers = {"other.example": {"client_secret": "value'with$dollar\\slash"}}
        base = "VOX_MCP_OAUTH_CLIENTS='" + json.dumps(providers).replace("'", "\\u0027") + "'\n"
        local = "# retained comment\nVOX_CREDENTIAL_KEY=fixture-key\nOTHER=preserve\n"
        result = module.merge_text(base, local, SECRET)
        self.assertTrue(result.startswith(local))
        actual = json.loads(module.env_value(result, "VOX_MCP_OAUTH_CLIENTS"))
        self.assertEqual(actual["other.example"], providers["other.example"])
        self.assertEqual(actual["api.githubcopilot.com"]["client_secret"], SECRET)
        self.assertEqual(actual["api.githubcopilot.com"]["scopes"], [])
        self.assertIn("VOX_MCP_OAUTH_CLIENTS='", result)

    def test_missing_key_never_updates(self):
        with self.assertRaisesRegex(RuntimeError, "encryption key"):
            module.merge_text("", "", SECRET)

    def test_empty_local_key_cannot_fall_back_to_shadowed_base_key(self):
        with self.assertRaisesRegex(RuntimeError, "encryption key"):
            module.merge_text("VOX_CREDENTIAL_KEY=base-key\n", "VOX_CREDENTIAL_KEY=\n", SECRET)

    def test_malformed_oauth_never_updates(self):
        with self.assertRaisesRegex(RuntimeError, "OAuth JSON"):
            module.merge_text("VOX_MCP_OAUTH_CLIENTS=invalid\n", "VOX_CREDENTIAL_KEY=fixture-key\n", SECRET)

    def test_duplicate_assignments_are_rejected_including_export(self):
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            module.merge_text("", "VOX_CREDENTIAL_KEY=first\n export VOX_CREDENTIAL_KEY = second\n", SECRET)

    def test_local_providers_override_base_as_compose_does(self):
        base = "VOX_MCP_OAUTH_CLIENTS='{}'\nVOX_CREDENTIAL_KEY=fixture-key\n"
        local = " export VOX_MCP_OAUTH_CLIENTS = '{\"other.example\":{\"client_id\":\"preserve\"}}'\n"
        result = module.merge_text(base, local, SECRET)
        actual = json.loads(module.env_value(result, "VOX_MCP_OAUTH_CLIENTS"))
        self.assertIn("other.example", actual)
        self.assertEqual(result.count("VOX_MCP_OAUTH_CLIENTS"), 1)

    def test_atomic_write_permissions_and_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            base, local = Path(directory) / "base.env", Path(directory) / "local.env"
            base.write_text("OTHER=base\n")
            local.write_text("VOX_CREDENTIAL_KEY=fixture-key\n")
            os.chmod(base, 0o600)
            os.chmod(local, 0o600)
            module.configure(base, local, SECRET)
            self.assertEqual(stat.S_IMODE(local.stat().st_mode), 0o600)
            before, inode = local.read_bytes(), local.stat().st_ino
            module.configure(base, local, SECRET)
            self.assertEqual(local.read_bytes(), before)
            self.assertEqual(local.stat().st_ino, inode)
            self.assertEqual(list(Path(directory).glob(".vox-local-env-*")), [])

    def test_symlink_is_rejected_without_changing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target, link = Path(directory) / "target", Path(directory) / "link"
            target.write_text("VOX_CREDENTIAL_KEY=fixture-key\n")
            os.chmod(target, 0o600)
            link.symlink_to(target)
            with self.assertRaises(RuntimeError):
                module.protected_text(link)
            self.assertEqual(target.read_text(), "VOX_CREDENTIAL_KEY=fixture-key\n")

    def test_insecure_file_permissions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config"
            path.write_text("VOX_CREDENTIAL_KEY=fixture-key\n")
            os.chmod(path, 0o644)
            with self.assertRaises(RuntimeError):
                module.protected_text(path)


if __name__ == "__main__":
    unittest.main()
