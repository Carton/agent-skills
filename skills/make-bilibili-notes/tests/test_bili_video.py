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

ASR_SCRIPT = Path(__file__).parents[1] / "scripts" / "asr_worker.py"
ASR_SPEC = importlib.util.spec_from_file_location("asr_worker", ASR_SCRIPT)
assert ASR_SPEC and ASR_SPEC.loader
asr_worker = importlib.util.module_from_spec(ASR_SPEC)
ASR_SPEC.loader.exec_module(asr_worker)


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


class AsrRoutingTest(unittest.TestCase):
    def test_transcribe_defaults_to_automatic_language_detection(self) -> None:
        parser = bili_video.build_parser()

        args = parser.parse_args(["transcribe", "/tmp/workdir"])

        self.assertEqual(args.language, "auto")

    def test_explicit_chinese_and_english_select_different_engines(self) -> None:
        self.assertEqual(bili_video.asr_engine_for_language("zh-CN"), "qwen3-asr")
        self.assertEqual(bili_video.asr_engine_for_language("yue"), "qwen3-asr")
        self.assertEqual(
            bili_video.asr_engine_for_language("English"),
            "faster-whisper",
        )

    def test_colab_installs_only_the_explicit_language_package_set(self) -> None:
        chinese = bili_video.asr_packages_for_language("zh", colab=True)
        english = bili_video.asr_packages_for_language("en", colab=True)
        automatic = bili_video.asr_packages_for_language("auto", colab=True)

        self.assertIn("qwen-asr==0.0.6", chinese)
        self.assertNotIn("faster-whisper==1.2.1", chinese)
        self.assertEqual(english, ["faster-whisper==1.2.1"])
        self.assertIn("qwen-asr==0.0.6", automatic)
        self.assertIn("faster-whisper==1.2.1", automatic)

    def test_auto_language_detection_routes_chinese(self) -> None:
        with mock.patch.object(
            asr_worker,
            "detect_language",
            return_value=("zh", 0.93),
        ):
            language, probability, method = asr_worker.resolve_language(
                {"language": "auto"}
            )

        self.assertEqual(language, "zh")
        self.assertEqual(probability, 0.93)
        self.assertEqual(method, "faster-whisper-tiny")

    def test_low_confidence_auto_detection_requires_explicit_language(self) -> None:
        with (
            mock.patch.object(
                asr_worker,
                "detect_language",
                return_value=("en", 0.51),
            ),
            self.assertRaisesRegex(RuntimeError, "--language zh.*--language en"),
        ):
            asr_worker.resolve_language({"language": "auto"})

    def test_qwen_vad_chunks_never_exceed_sixty_seconds(self) -> None:
        packed = asr_worker.pack_vad_segments(
            [[0, 10_000], [11_000, 30_000], [70_000, 140_000]]
        )

        self.assertEqual(
            packed,
            [[0, 30_000], [70_000, 130_000], [130_000, 140_000]],
        )
        self.assertTrue(all(end - start <= 60_000 for start, end in packed))

    def test_explicit_language_skips_detection(self) -> None:
        with mock.patch.object(asr_worker, "detect_language") as detect:
            language, probability, method = asr_worker.resolve_language(
                {"language": "zh"}
            )

        detect.assert_not_called()
        self.assertEqual((language, probability, method), ("zh", None, "explicit"))

    def test_local_chinese_requires_cuda_before_loading_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio_path = root / "audio.wav"
            audio_path.write_bytes(b"")
            args = argparse.Namespace(
                backend="local",
                confirm_external_upload=False,
                workdir=str(root),
                audio=str(audio_path),
                language="zh",
                device="cpu",
            )

            with self.assertRaisesRegex(bili_video.PipelineError, "需要 CUDA"):
                bili_video.command_transcribe(args)

    def test_worker_writes_qwen_metadata_for_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / "output.json"
            payload_path = root / "payload.json"
            payload_path.write_text(
                json.dumps({"language": "zh", "output": str(output_path)}),
                encoding="utf-8",
            )
            rows = [
                {
                    "start": 1.0,
                    "end": 20.0,
                    "text": "中文",
                    "source": "audio_asr",
                }
            ]
            with (
                mock.patch.object(
                    asr_worker,
                    "parse_args",
                    return_value=argparse.Namespace(payload=payload_path),
                ),
                mock.patch.object(
                    asr_worker,
                    "transcribe_qwen",
                    return_value=(rows, 1),
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                asr_worker.main()

            result = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result["engine"], "qwen3-asr")
        self.assertEqual(result["model"], "Qwen/Qwen3-ASR-1.7B")
        self.assertEqual(result["vad_model"], "funasr/fsmn-vad")
        self.assertEqual(result["max_segment_seconds"], 60)

    def test_worker_keeps_faster_whisper_for_english(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / "output.json"
            payload_path = root / "payload.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "language": "en",
                        "output": str(output_path),
                        "model": "large-v3",
                    }
                ),
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    asr_worker,
                    "parse_args",
                    return_value=argparse.Namespace(payload=payload_path),
                ),
                mock.patch.object(
                    asr_worker,
                    "transcribe_faster_whisper",
                    return_value=([], "en", 0.99),
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                asr_worker.main()

            result = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(result["engine"], "faster-whisper")
        self.assertEqual(result["model"], "large-v3")
        self.assertEqual(result["language"], "en")

    def test_transcribe_manifest_records_selected_engine_and_language(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio_path = root / "audio.wav"
            audio_path.write_bytes(b"")
            args = argparse.Namespace(
                backend="local",
                confirm_external_upload=False,
                workdir=str(root),
                audio=str(audio_path),
                language="en",
                device="cpu",
                compute_type="int8",
                model="small",
                beam_size=3,
                glossary="Codex",
                bootstrap_asr=False,
            )

            def fake_run(
                command: list[str], **_: object
            ) -> subprocess.CompletedProcess[str]:
                payload = bili_video.read_json(Path(command[-1]))
                bili_video.write_json(
                    Path(payload["output"]),
                    {
                        "engine": "faster-whisper",
                        "model": "small",
                        "language": "en",
                        "language_probability": 0.99,
                        "language_detection": "explicit",
                        "segments": [
                            {
                                "start": 0.0,
                                "end": 1.0,
                                "text": "Codex",
                            }
                        ],
                    },
                )
                return subprocess.CompletedProcess(command, 0)

            with (
                mock.patch.object(bili_video, "module_available", return_value=True),
                mock.patch.object(bili_video, "run", side_effect=fake_run),
                mock.patch.dict(
                    os.environ,
                    {"MAKE_BILIBILI_NOTES_CACHE": str(root / "cache")},
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                bili_video.command_transcribe(args)

            manifest = bili_video.read_json(root / "manifest.json")

        self.assertEqual(manifest["asr"]["engine"], "faster-whisper")
        self.assertEqual(manifest["asr"]["requested_language"], "en")
        self.assertEqual(manifest["asr"]["language_detection"], "explicit")


if __name__ == "__main__":
    unittest.main()
