import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_release


def service(module, image, resource_type="google_cloud_run_v2_service"):
    return {"module": module, "type": resource_type, "instances": [{"attributes": {
        "template": [{"containers": [{"image": image}]}],
    }}]}


class ReleaseTests(unittest.TestCase):
    def test_preserves_current_service_images_and_ignores_migration_image(self):
        state = {"resources": [service("module.api[0]", "api@sha256:current"),
                              service("module.dashboard[0]", "dashboard@sha256:current"),
                              service("module.ai[0]", "ai@sha256:current"),
                              service("module.api[0]", "job@sha256:old", "google_cloud_run_v2_job")]}
        release = ci_release.deployed_images(state)
        self.assertEqual(release, {"deploy_api": True, "image": "api@sha256:current",
                                  "dashboard_image": "dashboard@sha256:current", "ai_image": "ai@sha256:current"})

    def test_missing_live_images_cannot_remove_existing_services(self):
        with self.assertRaisesRegex(RuntimeError, "missing"):
            ci_release.deployed_images({"resources": []})

    @patch("ci_release.owner_finished", return_value=True)
    @patch("ci_release.google_request")
    def test_recovers_only_finished_owner_and_deletes_exact_lock_generations(self, request, finished):
        busy = urllib.error.HTTPError("https://storage.googleapis.com", 412, "busy", None, None)
        owner = {"repository": "RodrigoVanzelotti/landing-optimizer-api", "run_id": "1", "attempt": "1"}
        request.side_effect = [busy, {"generation": "old"}, owner, {}, {"generation": "new"}, {}]
        with ci_release.deployment_lock(owner):
            pass
        finished.assert_called_once_with(owner)
        deletes = [call.args for call in request.call_args_list if len(call.args) > 1 and call.args[1] == "DELETE"]
        self.assertEqual(deletes, [(ci_release.LOCK_URL + "?ifGenerationMatch=old", "DELETE"),
                                  (ci_release.LOCK_URL + "?ifGenerationMatch=new", "DELETE")])

    @patch("ci_release.github_request")
    def test_refuses_unknown_lock_owner(self, request):
        with self.assertRaisesRegex(RuntimeError, "unknown owner"):
            ci_release.owner_finished({"repository": "someone/other", "run_id": "1", "attempt": "1"})
        request.assert_not_called()

    @patch("ci_release.github_request")
    def test_active_workflow_keeps_lock_but_finished_attempt_does_not(self, request):
        owner = {"repository": "RodrigoVanzelotti/landing-optimizer-ai", "run_id": "1", "attempt": "1"}
        request.return_value = {"status": "in_progress", "run_attempt": 1}
        self.assertFalse(ci_release.owner_finished(owner))
        request.return_value = {"status": "in_progress", "run_attempt": 2}
        self.assertTrue(ci_release.owner_finished(owner))


if __name__ == "__main__":
    unittest.main()
