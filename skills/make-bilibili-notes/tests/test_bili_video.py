from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "bili_video.py"
SPEC = importlib.util.spec_from_file_location("bili_video", SCRIPT)
assert SPEC and SPEC.loader
bili_video = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bili_video)


class BilibiliAuthStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        cookie_path = Path(self.temporary_directory.name) / "missing-cookie"
        patcher = mock.patch.object(
            bili_video,
            "bilibili_cookie_path",
            return_value=cookie_path,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_cookie_allows_anonymous_continuation(self) -> None:
        with mock.patch.dict(os.environ, {"BILIBILI_COOKIE": ""}):
            status = bili_video.bilibili_auth_status()

        self.assertEqual(status["status"], "not_configured")

        output = io.StringIO()
        args = argparse.Namespace(service="bilibili", colab_auth="oauth2")
        with (
            mock.patch.object(
                bili_video,
                "bilibili_auth_status",
                return_value=status,
            ),
            contextlib.redirect_stdout(output),
        ):
            exit_code = bili_video.command_auth_check(args)

        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(output.getvalue())["can_continue"])

    def test_all_allows_anonymous_bilibili_when_colab_is_ready(self) -> None:
        output = io.StringIO()
        args = argparse.Namespace(service="all", colab_auth="oauth2")
        with (
            mock.patch.object(
                bili_video,
                "bilibili_auth_status",
                return_value={"status": "not_configured"},
            ),
            mock.patch.object(
                bili_video,
                "colab_auth_status",
                return_value={"status": "ready"},
            ),
            contextlib.redirect_stdout(output),
        ):
            exit_code = bili_video.command_auth_check(args)

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["ready"])
        self.assertTrue(payload["can_continue"])

    def test_invalid_cookie_is_not_reported_as_network_failure(self) -> None:
        response = io.BytesIO(
            b'{"code":-101,"message":"not logged in","data":{"isLogin":false}}'
        )
        with (
            mock.patch.dict(os.environ, {"BILIBILI_COOKIE": "secret-sentinel"}),
            mock.patch.object(bili_video, "request", return_value=response),
        ):
            status = bili_video.bilibili_auth_status()

        self.assertEqual(status["status"], "invalid")
        self.assertNotIn("secret-sentinel", json.dumps(status))

    def test_network_failure_is_unreachable(self) -> None:
        with (
            mock.patch.dict(os.environ, {"BILIBILI_COOKIE": "configured"}),
            mock.patch.object(
                bili_video,
                "request",
                side_effect=urllib.error.URLError("offline"),
            ),
        ):
            status = bili_video.bilibili_auth_status()

        self.assertEqual(status["status"], "unreachable")


class BilibiliCookieStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.cookie_path = (
            Path(self.temporary_directory.name)
            / "make-bilibili-notes"
            / "bilibili-cookie"
        )
        patcher = mock.patch.object(
            bili_video,
            "bilibili_cookie_path",
            return_value=self.cookie_path,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_and_load_cookie_with_private_permissions(self) -> None:
        saved_path = bili_video.save_bilibili_cookie("secret-sentinel")

        with mock.patch.dict(os.environ, {"BILIBILI_COOKIE": ""}):
            cookie, source = bili_video.load_bilibili_cookie()

        self.assertEqual(saved_path, self.cookie_path)
        self.assertEqual(cookie, "secret-sentinel")
        self.assertEqual(source, "file")
        self.assertEqual(self.cookie_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.cookie_path.parent.stat().st_mode & 0o777, 0o700)

    def test_environment_cookie_has_priority_over_saved_file(self) -> None:
        bili_video.save_bilibili_cookie("saved-secret")

        with mock.patch.dict(
            os.environ,
            {"BILIBILI_COOKIE": "environment-secret"},
        ):
            cookie, source = bili_video.load_bilibili_cookie()

        self.assertEqual(cookie, "environment-secret")
        self.assertEqual(source, "environment")

    def test_rejects_cookie_file_with_group_or_other_access(self) -> None:
        bili_video.save_bilibili_cookie("secret-sentinel")
        self.cookie_path.chmod(0o644)

        with (
            mock.patch.dict(os.environ, {"BILIBILI_COOKIE": ""}),
            self.assertRaisesRegex(bili_video.PipelineError, "chmod 600"),
        ):
            bili_video.load_bilibili_cookie()

    def test_auth_save_uses_environment_without_printing_cookie(self) -> None:
        output = io.StringIO()
        args = argparse.Namespace(service="bilibili")
        with (
            mock.patch.dict(
                os.environ,
                {"BILIBILI_COOKIE": "secret-sentinel"},
            ),
            contextlib.redirect_stdout(output),
        ):
            exit_code = bili_video.command_auth_save(args)

        self.assertEqual(exit_code, 0)
        self.assertNotIn("secret-sentinel", output.getvalue())
        self.assertEqual(
            self.cookie_path.read_text(encoding="utf-8"),
            "secret-sentinel",
        )


class ColabAuthStatusTest(unittest.TestCase):
    def test_adc_does_not_require_oauth_token_file(self) -> None:
        result = subprocess.CompletedProcess([], 0, "Email: private@example.com", "")
        with (
            mock.patch.object(bili_video.shutil, "which", return_value="/bin/colab"),
            mock.patch.object(bili_video.subprocess, "run", return_value=result) as run,
            mock.patch.dict(os.environ, {"BILIBILI_COOKIE": "secret-sentinel"}),
        ):
            status = bili_video.colab_auth_status("adc")

        self.assertEqual(status["status"], "ready")
        command = run.call_args.args[0]
        child_env = run.call_args.kwargs["env"]
        self.assertEqual(command, ["/bin/colab", "--auth=adc", "whoami"])
        self.assertNotIn("BILIBILI_COOKIE", child_env)
        self.assertNotIn("private@example.com", json.dumps(status))

    def test_missing_oauth_token_is_not_configured(self) -> None:
        with (
            mock.patch.object(bili_video.shutil, "which", return_value="/bin/colab"),
            mock.patch.object(Path, "exists", return_value=False),
        ):
            status = bili_video.colab_auth_status("oauth2")

        self.assertEqual(status["status"], "not_configured")


class ExternalUploadConsentTest(unittest.TestCase):
    def test_colab_requires_explicit_upload_confirmation(self) -> None:
        args = argparse.Namespace(
            backend="colab",
            confirm_external_upload=False,
            workdir="unused",
        )

        with self.assertRaisesRegex(
            bili_video.PipelineError,
            "--confirm-external-upload",
        ):
            bili_video.command_transcribe(args)

    def test_confirmation_passes_gate_before_audio_validation(self) -> None:
        args = argparse.Namespace(
            backend="colab",
            confirm_external_upload=True,
            workdir="/tmp/nonexistent-bilibili-test-workdir",
            audio=None,
        )

        with self.assertRaisesRegex(bili_video.PipelineError, "找不到音频"):
            bili_video.command_transcribe(args)

    def test_auth_check_requires_explicit_service(self) -> None:
        parser = bili_video.build_parser()
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["auth-check"])


if __name__ == "__main__":
    unittest.main()
