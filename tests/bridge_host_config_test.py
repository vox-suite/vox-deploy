import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "bridge_host", Path(__file__).parents[1] / "scripts/configure-bridge-host.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CREDENTIAL = {"credential_id": "12345678-1234-4234-9234-123456789abc",
              "audience": module.AUDIENCE, "secret": "a" * 64}


class BridgeHostTests(unittest.TestCase):
    def files(self, directory):
        base, bridge = Path(directory) / "base", Path(directory) / "bridge"
        base.write_text("VOX_AUTH_TOKEN=fixture-bootstrap\nVOX_CREDENTIAL_KEY=fixture-key\n")
        os.chmod(base, 0o600)
        return base, bridge

    def test_issues_once_stores_owner_only_and_preserves_base(self):
        with tempfile.TemporaryDirectory() as directory:
            base, bridge = self.files(directory)
            original = base.read_bytes()
            with patch.object(module, "request", return_value={"credential": CREDENTIAL}) as request:
                module.configure(base, bridge)
                request.assert_called_once_with("/v1/host-apps", "fixture-bootstrap", {
                    "deployment_external_key": "vox.standalone.deployment", "host_app_external_key": "vox.standalone.bridge", "allowed_origins": [],
                })
                self.assertEqual(module.AUDIENCE, "vox-host:vox.standalone.deployment:vox.standalone.bridge")
                self.assertEqual(bridge.stat().st_mode & 0o777, 0o600)
                self.assertEqual(base.read_bytes(), original)
                inode = bridge.stat().st_ino
                module.configure(base, bridge)
                self.assertEqual(request.call_count, 1)
                self.assertEqual(bridge.stat().st_ino, inode)

    def test_partial_or_wrong_host_configuration_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            base, bridge = self.files(directory)
            for content in ("VOX_HOST_SECRET='" + "a" * 64 + "'\n",
                            "VOX_HOST_CREDENTIAL_ID='" + CREDENTIAL["credential_id"] + "'\nVOX_HOST_SECRET='" + "a" * 64 + "'\nVOX_HOST_AUDIENCE='vox-host:production:vox-web'\n"):
                bridge.write_text(content)
                os.chmod(bridge, 0o600)
                with patch.object(module, "request") as request:
                    with self.assertRaises(RuntimeError):
                        module.configure(base, bridge)
                    request.assert_not_called()
                self.assertEqual(bridge.read_text(), content)

    def test_registration_failure_does_not_create_config(self):
        with tempfile.TemporaryDirectory() as directory:
            base, bridge = self.files(directory)
            with patch.object(module, "request", side_effect=RuntimeError("rejected")):
                with self.assertRaises(RuntimeError):
                    module.configure(base, bridge)
            self.assertFalse(bridge.exists())

    def test_write_failure_revokes_undisclosed_new_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            base, bridge = self.files(directory)
            with patch.object(module, "request", side_effect=[{"credential": CREDENTIAL}, None]) as request, patch.object(module.vm.os, "replace", side_effect=OSError("fixture disk failure")):
                with self.assertRaises(OSError):
                    module.configure(base, bridge)
                self.assertEqual(request.call_args.args, ("/v1/host-app-credentials/" + CREDENTIAL["credential_id"] + "/revoke", "fixture-bootstrap"))
            self.assertFalse(bridge.exists())


if __name__ == "__main__":
    unittest.main()
