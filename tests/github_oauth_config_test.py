import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location(
    "configure_github", Path(__file__).parents[1] / "scripts/configure-github-oauth.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FIXTURE_SECRET = "test-secret-12345678901234567890"


class ConfigurationTests(unittest.TestCase):
    def test_preserves_other_providers_and_applies_least_scope(self):
        original = {"other.example": {"client_id": "other", "client_secret": "fixture"}}
        merged = module.merged_configuration(original, FIXTURE_SECRET)
        self.assertEqual(merged["other.example"], original["other.example"])
        self.assertNotIn("api.githubcopilot.com", original)
        self.assertEqual(merged["api.githubcopilot.com"]["scopes"], [])
        self.assertEqual(merged["api.githubcopilot.com"]["token_endpoint_auth_method"], "client_secret_post")

    def run_case(self, responses):
        calls = []
        def fake(command, **kwargs):
            calls.append((command, kwargs))
            code, output, error = responses.pop(0)
            return SimpleNamespace(returncode=code, stdout=output, stderr=error)
        return calls, fake

    def test_permission_failure_never_creates_or_overwrites(self):
        calls, fake = self.run_case([(1, b"", b"PERMISSION_DENIED")])
        with self.assertRaises(RuntimeError):
            module.configure("vox-agent-507800", FIXTURE_SECRET, fake)
        self.assertEqual(len(calls), 1)

    def test_existing_payload_read_failure_never_overwrites(self):
        calls, fake = self.run_case([(0, b"", b""), (1, b"", b"denied")])
        with self.assertRaises(RuntimeError):
            module.configure("vox-agent-507800", FIXTURE_SECRET, fake)
        self.assertEqual(len(calls), 2)

    def test_malformed_payload_never_overwrites(self):
        calls, fake = self.run_case([(0, b"", b""), (0, b"invalid-json", b"")])
        with self.assertRaises(RuntimeError):
            module.configure("vox-agent-507800", FIXTURE_SECRET, fake)
        self.assertEqual(len(calls), 2)

    def test_secret_only_flows_through_stdin(self):
        calls, fake = self.run_case([(1, b"", b"NOT_FOUND"), (0, b"", b"")])
        module.configure("vox-agent-507800", FIXTURE_SECRET, fake)
        self.assertNotIn(FIXTURE_SECRET, " ".join(calls[-1][0]))
        self.assertEqual(json.loads(calls[-1][1]["input"])["api.githubcopilot.com"]["client_secret"], FIXTURE_SECRET)

    def test_matching_configuration_is_idempotent(self):
        payload = json.dumps(module.merged_configuration({}, FIXTURE_SECRET)).encode()
        calls, fake = self.run_case([(0, b"", b""), (0, payload, b"")])
        module.configure("vox-agent-507800", FIXTURE_SECRET, fake)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
