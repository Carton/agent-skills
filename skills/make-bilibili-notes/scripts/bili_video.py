#!/usr/bin/env python3
"""Deterministic preparation pipeline for Bilibili video notes.

The script does the mechanical work so the calling agent only has to:
1. inspect one probe sheet,
2. choose hard-subtitle OCR or speech transcription,
3. write and verify the final note.

Core preparation uses only the Python standard library, ffmpeg/ffprobe and
Pillow. Optional OCR and ASR engines are isolated in reusable virtualenvs.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import difflib
import getpass
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com/"
FASTER_WHISPER_PACKAGES = ["faster-whisper==1.2.1", "socksio"]
QWEN_ASR_PACKAGES = [
    "qwen-asr==0.0.6",
    "funasr==1.4.0",
    "soundfile==0.14.0",
    "transformers==4.57.6",
    "socksio",
]
OCR_PACKAGES = ["rapidocr-onnxruntime==1.4.4"]
COLAB_FASTER_WHISPER_PACKAGES = ["faster-whisper==1.2.1"]
ASR_LANGUAGE_DETECTION_MODEL = "tiny"
CHINESE_ASR_LANGUAGE_CODES = {
    "zh",
    "yue",
    "wuu",
    "nan",
    "hak",
    "gan",
    "hsn",
    "cjy",
}
COLAB_REMOTE_AUDIO = "/content/make-bilibili-notes-audio.wav"
COLAB_REMOTE_INPUT = "/content/make-bilibili-notes-input.json"
COLAB_REMOTE_OUTPUT = "/content/make-bilibili-notes-output.json"
TESSDATA_FAST_CHI_SIM = (
    "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/"
    "chi_sim.traineddata"
)


class PipelineError(RuntimeError):
    pass


def bilibili_cookie_path() -> Path:
    return Path.home() / ".config" / "make-bilibili-notes" / "bilibili-cookie"


def load_bilibili_cookie() -> tuple[str, str]:
    cookie = os.environ.get("BILIBILI_COOKIE", "").strip()
    if cookie:
        return cookie, "environment"

    path = bilibili_cookie_path()
    if path.is_symlink():
        raise PipelineError(f"Bilibili Cookie 路径不能是符号链接：{path}")
    if not path.exists():
        return "", "none"
    if not path.is_file():
        raise PipelineError(f"Bilibili Cookie 路径必须是普通文件：{path}")
    if path.parent.is_symlink():
        raise PipelineError(f"Bilibili Cookie 目录不能是符号链接：{path.parent}")
    if (path.parent.stat().st_mode & 0o777) != 0o700:
        raise PipelineError(
            f"Bilibili Cookie 目录权限过宽；请运行：chmod 700 {path.parent}"
        )
    if (path.stat().st_mode & 0o777) != 0o600:
        raise PipelineError(
            f"Bilibili Cookie 文件权限过宽；请运行：chmod 600 {path}"
        )
    cookie = path.read_text(encoding="utf-8").strip()
    if not cookie:
        raise PipelineError(f"Bilibili Cookie 文件为空：{path}")
    return cookie, "file"


def save_bilibili_cookie(cookie: str) -> Path:
    cookie = cookie.strip()
    if not cookie or "\n" in cookie or "\r" in cookie:
        raise PipelineError("Bilibili Cookie 不能为空或包含换行符。")

    path = bilibili_cookie_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise PipelineError(f"Bilibili Cookie 目录不能是符号链接：{path.parent}")
    path.parent.chmod(0o700)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".bilibili-cookie-",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary_path.chmod(0o600)
            temporary.write(cookie)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        path.chmod(0o600)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return path


def say(message: str) -> None:
    print(message, flush=True)


def run(
    command: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        env=env,
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(value: str, limit: int = 80) -> str:
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value or "bilibili-video")[:limit]


def extract_bvid(value: str) -> str:
    match = re.search(r"(BV[0-9A-Za-z]{10})", value)
    if not match:
        raise PipelineError(f"未在输入中找到 BVID：{value}")
    return match.group(1)


def resolve_video_page(value: str, explicit_page: int | None) -> int:
    if explicit_page is not None:
        return explicit_page
    page_values = urllib.parse.parse_qs(urllib.parse.urlparse(value).query).get("p")
    if not page_values:
        return 1
    try:
        page = int(page_values[0])
    except ValueError as exc:
        raise PipelineError(f"无效的分 P 参数：p={page_values[0]}") from exc
    if page < 1:
        raise PipelineError(f"分 P 必须大于等于 1：p={page}")
    return page


def request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> urllib.response.addinfourl:
    merged = {"User-Agent": USER_AGENT, "Referer": REFERER}
    hostname = (urllib.parse.urlparse(url).hostname or "").lower()
    cookie, _ = load_bilibili_cookie()
    if cookie and (hostname == "bilibili.com" or hostname.endswith(".bilibili.com")):
        merged["Cookie"] = cookie
    if headers:
        merged.update(headers)
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=merged),
        timeout=timeout,
    )


def get_json(url: str, retries: int = 3) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with request(url) as response:
                payload = json.load(response)
            if isinstance(payload, dict) and payload.get("code") not in (None, 0):
                raise PipelineError(
                    f"Bilibili API 返回错误 {payload.get('code')}: "
                    f"{payload.get('message')}"
                )
            return payload
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise PipelineError(f"请求失败：{url}\n{last_error}")


def api_url(path: str, **params: Any) -> str:
    return "https://api.bilibili.com" + path + "?" + urllib.parse.urlencode(params)


def page_info(view_data: dict[str, Any], page: int) -> dict[str, Any]:
    pages = view_data.get("pages") or []
    if page < 1 or page > len(pages):
        raise PipelineError(f"分 P {page} 不存在；该视频共有 {len(pages)} P")
    return pages[page - 1]


def subtitle_is_ai(item: dict[str, Any]) -> bool:
    language = str(item.get("lan") or "")
    return bool(item.get("ai_type")) or language.startswith("ai-")


def choose_subtitle(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    priorities = ("zh-CN", "zh-Hans", "zh-Hant", "ai-zh", "zh")

    def score(item: dict[str, Any]) -> tuple[int, int, int]:
        language = str(item.get("lan") or "")
        is_ai = subtitle_is_ai(item)
        try:
            rank = priorities.index(language)
        except ValueError:
            rank = len(priorities)
        if rank < len(priorities):
            source_rank = 1 if is_ai else 0
        else:
            source_rank = 3 if is_ai else 2
        return source_rank, rank, 1 if item.get("is_lock") else 0

    return sorted(items, key=score)[0]


def subtitle_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for row in payload.get("body") or []:
        text = str(row.get("content") or "").strip()
        if text:
            segments.append(
                {
                    "start": float(row.get("from") or 0),
                    "end": float(row.get("to") or row.get("from") or 0),
                    "text": text,
                    "confidence": None,
                    "source": "official_subtitle",
                }
            )
    return segments


def seconds_label(value: float, srt: bool = False) -> str:
    value = max(0.0, float(value))
    milliseconds = round((value - math.floor(value)) * 1000)
    whole = int(math.floor(value))
    if milliseconds == 1000:
        whole += 1
        milliseconds = 0
    hours, remain = divmod(whole, 3600)
    minutes, seconds = divmod(remain, 60)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{milliseconds:03d}"


def short_time(value: float) -> str:
    whole = max(0, round(float(value)))
    hours, remain = divmod(whole, 3600)
    minutes, seconds = divmod(remain, 60)
    return (
        f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        if hours
        else f"{minutes:02d}:{seconds:02d}"
    )


def normalize_text(value: str) -> str:
    value = value.replace("\u3000", " ").replace("\ufeff", "")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", value)
    value = re.sub(r"^[|丨·•\-—_]+|[|丨·•\-—_]+$", "", value)
    return value.strip()


def comparison_text(value: str) -> str:
    value = normalize_text(value).lower()
    return re.sub(r"[\s，。！？、；：“”‘’（）《》〈〉,.!?;:'\"()\[\]{}<>…—-]", "", value)


def dedupe_segments(
    segments: Iterable[dict[str, Any]],
    similarity: float = 0.91,
) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for original in sorted(segments, key=lambda row: float(row.get("start") or 0)):
        row = dict(original)
        row["start"] = float(row.get("start") or 0)
        row["end"] = max(row["start"], float(row.get("end") or row["start"]))
        row["text"] = normalize_text(str(row.get("text") or ""))
        if not row["text"]:
            continue
        if cleaned:
            previous = cleaned[-1]
            left = comparison_text(previous["text"])
            right = comparison_text(row["text"])
            ratio = difflib.SequenceMatcher(None, left, right).ratio() if left and right else 0
            if left == right or (min(len(left), len(right)) >= 5 and ratio >= similarity):
                previous["end"] = max(previous["end"], row["end"])
                if len(right) > len(left):
                    previous["text"] = row["text"]
                scores = [
                    x
                    for x in (previous.get("confidence"), row.get("confidence"))
                    if isinstance(x, (float, int))
                ]
                previous["confidence"] = max(scores) if scores else None
                continue
        cleaned.append(row)
    return cleaned


def write_transcript(
    output_dir: Path,
    segments: list[dict[str, Any]],
    source_type: str,
) -> None:
    segments = dedupe_segments(segments)
    write_json(
        output_dir / "transcript.json",
        {"source_type": source_type, "segments": segments},
    )
    srt_lines: list[str] = []
    md_lines = [f"# Transcript ({source_type})", ""]
    for index, row in enumerate(segments, start=1):
        srt_lines.extend(
            [
                str(index),
                f"{seconds_label(row['start'], True)} --> {seconds_label(row['end'], True)}",
                row["text"],
                "",
            ]
        )
        md_lines.append(f"- `{short_time(row['start'])}` {row['text']}")
    (output_dir / "transcript.srt").write_text(
        "\n".join(srt_lines),
        encoding="utf-8",
    )
    (output_dir / "transcript.md").write_text(
        "\n".join(md_lines) + "\n",
        encoding="utf-8",
    )


def video_metadata(bvid: str, page: int) -> tuple[dict[str, Any], dict[str, Any]]:
    view = get_json(api_url("/x/web-interface/view", bvid=bvid))["data"]
    selected = page_info(view, page)
    published = dt.datetime.fromtimestamp(
        int(view.get("pubdate") or 0),
        tz=dt.timezone.utc,
    ).date().isoformat()
    metadata = {
        "bvid": bvid,
        "aid": int(view["aid"]),
        "cid": int(selected["cid"]),
        "page": page,
        "title": str(view.get("title") or ""),
        "part_title": str(selected.get("part") or ""),
        "owner": str((view.get("owner") or {}).get("name") or ""),
        "published": published,
        "duration": int(selected.get("duration") or view.get("duration") or 0),
        "width": int((selected.get("dimension") or {}).get("width") or 0),
        "height": int((selected.get("dimension") or {}).get("height") or 0),
        "url": f"https://www.bilibili.com/video/{bvid}/?p={page}",
    }
    return view, metadata


def player_data(metadata: dict[str, Any]) -> dict[str, Any]:
    return get_json(
        api_url(
            "/x/player/v2",
            aid=metadata["aid"],
            cid=metadata["cid"],
        )
    )["data"]


def fresh_playurl(metadata: dict[str, Any]) -> dict[str, Any]:
    return get_json(
        api_url(
            "/x/player/playurl",
            avid=metadata["aid"],
            cid=metadata["cid"],
            qn=64,
            fnver=0,
            fnval=16,
            fourk=0,
        )
    )["data"]


def candidate_urls(stream: dict[str, Any]) -> list[str]:
    values = [stream.get("baseUrl") or stream.get("base_url")]
    values.extend(stream.get("backupUrl") or stream.get("backup_url") or [])
    return [str(value) for value in values if value]


def choose_video_stream(dash: dict[str, Any]) -> dict[str, Any]:
    videos = list(dash.get("video") or [])
    if not videos:
        raise PipelineError("播放信息中没有 DASH 视频流")
    avc = [row for row in videos if str(row.get("codecs") or "").startswith("avc")]
    pool = avc or videos
    suitable = [
        row
        for row in pool
        if int(row.get("height") or 0) <= 720 and int(row.get("height") or 0) >= 480
    ]
    if suitable:
        return min(
            suitable,
            key=lambda row: (
                abs(int(row.get("height") or 0) - 480),
                int(row.get("bandwidth") or 0),
            ),
        )
    return min(pool, key=lambda row: int(row.get("bandwidth") or 0))


def choose_audio_stream(dash: dict[str, Any]) -> dict[str, Any]:
    audio = list(dash.get("audio") or [])
    if not audio:
        raise PipelineError("播放信息中没有 DASH 音频流")
    return min(audio, key=lambda row: int(row.get("bandwidth") or 0))


def download_one(url: str, destination: Path, retries: int = 6) -> None:
    part = destination.with_suffix(destination.suffix + ".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("curl"):
        # Probe a one-byte Range response. Fixed, verified byte ranges avoid a
        # class of Bilibili CDN failures where automatic resume appends shifted
        # data while still producing a plausible file size and duration.
        total: int | None = None
        range_supported = False
        try:
            with request(url, headers={"Range": "bytes=0-0"}, timeout=20) as response:
                content_range = response.headers.get("Content-Range") or ""
                match = re.search(r"bytes\s+0-0/(\d+)", content_range)
                if match:
                    total = int(match.group(1))
                    range_supported = getattr(response, "status", 0) == 206
                    response.read(1)
                elif response.headers.get("Content-Length"):
                    total = int(response.headers["Content-Length"])
        except Exception:
            pass

        if total and range_supported:
            chunk_size = 2 * 1024 * 1024
            meta_path = destination.with_suffix(destination.suffix + ".part.json")
            chunk_path = destination.with_suffix(destination.suffix + ".chunk")
            identity = {
                "total": total,
                "path": urllib.parse.urlsplit(url).path,
                "chunk_size": chunk_size,
            }
            previous_meta: dict[str, Any] = {}
            if meta_path.exists():
                with contextlib.suppress(Exception):
                    previous_meta = read_json(meta_path)
            if previous_meta != identity:
                part.unlink(missing_ok=True)
                chunk_path.unlink(missing_ok=True)
            write_json(meta_path, identity)
            offset = part.stat().st_size if part.exists() else 0
            if offset > total:
                part.unlink()
                offset = 0
            if offset < total and offset % chunk_size:
                safe_offset = offset - (offset % chunk_size)
                with part.open("r+b") as handle:
                    handle.truncate(safe_offset)
                offset = safe_offset
            last_report = -1
            while offset < total:
                end = min(total - 1, offset + chunk_size - 1)
                expected = end - offset + 1
                complete = False
                for attempt in range(retries):
                    chunk_path.unlink(missing_ok=True)
                    result = run(
                        [
                            "curl",
                            "--http1.1",
                            "--location",
                            "--fail",
                            "--silent",
                            "--show-error",
                            "--connect-timeout",
                            "20",
                            "--max-time",
                            "90",
                            "--range",
                            f"{offset}-{end}",
                            "--user-agent",
                            USER_AGENT,
                            "--referer",
                            REFERER,
                            "--output",
                            str(chunk_path),
                            "--write-out",
                            "%{http_code}",
                            url,
                        ],
                        check=False,
                        capture=True,
                    )
                    received = chunk_path.stat().st_size if chunk_path.exists() else 0
                    status = (result.stdout or "").strip()[-3:]
                    if result.returncode == 0 and status == "206" and received == expected:
                        with part.open("ab") as target, chunk_path.open("rb") as source:
                            shutil.copyfileobj(source, target)
                        chunk_path.unlink(missing_ok=True)
                        offset += received
                        complete = True
                        break
                    say(
                        f"{destination.name} 字节 {offset}-{end} 重试 "
                        f"{attempt + 1}/{retries}（HTTP {status or '?'}，{received} bytes）"
                    )
                    time.sleep(min(2 ** attempt, 8))
                if not complete:
                    raise PipelineError(
                        f"固定字节分块下载失败：{destination.name} @ {offset}-{end}"
                    )
                percent = int(offset * 100 / total)
                if percent // 10 != last_report // 10 or offset == total:
                    say(
                        f"{destination.name}：{percent}% "
                        f"({offset / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MiB)"
                    )
                    last_report = percent
            meta_path.unlink(missing_ok=True)
            part.replace(destination)
            say(f"已下载 {destination.name}（{total / 1024 / 1024:.1f} MiB）")
            return

        # Range is unavailable. A one-shot retry overwrites rather than appends,
        # so retries cannot corrupt the file.
        result = run(
            [
                "curl",
                "--http1.1",
                "--location",
                "--fail",
                "--silent",
                "--show-error",
                "--retry",
                str(retries),
                "--retry-all-errors",
                "--connect-timeout",
                "20",
                "--max-time",
                "600",
                "--user-agent",
                USER_AGENT,
                "--referer",
                REFERER,
                "--output",
                str(part),
                url,
            ],
            check=False,
        )
        if result.returncode == 0 and part.exists() and part.stat().st_size:
            current = part.stat().st_size
            part.replace(destination)
            say(f"已下载 {destination.name}（{current / 1024 / 1024:.1f} MiB）")
            return
        raise PipelineError(f"curl 下载失败（exit {result.returncode}）：{destination.name}")

    # Standard-library fallback for minimal environments without curl.
    total: int | None = None
    for attempt in range(retries):
        offset = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with request(url, headers=headers, timeout=45) as response:
                status = getattr(response, "status", response.getcode())
                if offset and status == 200:
                    part.unlink(missing_ok=True)
                    offset = 0
                content_range = response.headers.get("Content-Range") or ""
                match = re.search(r"/(\d+)$", content_range)
                if match:
                    total = int(match.group(1))
                elif response.headers.get("Content-Length"):
                    length = int(response.headers["Content-Length"])
                    total = offset + length if status == 206 else length
                mode = "ab" if offset and status == 206 else "wb"
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
            current = part.stat().st_size
            if total is None or current >= total:
                part.replace(destination)
                say(f"已下载 {destination.name}（{current / 1024 / 1024:.1f} MiB）")
                return
            say(
                f"{destination.name} 下载中断，续传 "
                f"{current / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MiB"
            )
        except Exception as exc:
            say(f"{destination.name} 第 {attempt + 1} 次下载失败：{exc}")
        time.sleep(min(2 ** attempt, 12))
    raise PipelineError(f"下载未完成：{destination}")


def download_candidates(urls: list[str], destination: Path) -> None:
    errors: list[str] = []
    for index, url in enumerate(urls, start=1):
        say(f"尝试下载源 {index}/{len(urls)}：{destination.name}")
        try:
            download_one(url, destination)
            return
        except Exception as exc:
            errors.append(str(exc))
    raise PipelineError("\n".join(errors))


def ffprobe_value(path: Path, field: str) -> str:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            f"format={field}",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture=True,
    )
    return result.stdout.strip()


def media_duration(path: Path) -> float:
    return float(ffprobe_value(path, "duration"))


def media_is_decodable(path: Path) -> bool:
    try:
        media_duration(path)
    except Exception:
        return False
    # A resumed CDN response can have a valid container index but duplicated or
    # missing byte ranges in the middle. Decode the compact selected stream once;
    # spot checks cannot reliably detect that class of corruption.
    result = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture=True,
    )
    diagnostics = (result.stderr or "").lower()
    return result.returncode == 0 and not any(
        marker in diagnostics
        for marker in (
            "invalid nal",
            "corrupt",
            "missing picture",
            "error while",
            "partial file",
        )
    )


def convert_audio(source: Path, destination: Path) -> None:
    say("转换为 16 kHz 单声道 WAV…")
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
    )


def require_pillow() -> tuple[Any, Any, Any, Any, Any]:
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
    except ImportError as exc:
        raise PipelineError(
            "缺少 Pillow。请先运行：python3 -m pip install --user Pillow"
        ) from exc
    return Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


def extract_frame(video: Path, at: float, destination: Path) -> None:
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{at:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(destination),
        ]
    )


def font_for(draw_module: Any, size: int) -> Any:
    from PIL import ImageFont

    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def make_contact_sheet(
    images: list[tuple[Path, float]],
    destination: Path,
    *,
    columns: int = 2,
    rows: int = 4,
    tile_width: int = 960,
    tile_height: int = 270,
) -> None:
    Image, ImageDraw, _, _, _ = require_pillow()
    background = Image.new("RGB", (columns * tile_width, rows * tile_height), "black")
    draw = ImageDraw.Draw(background)
    font = font_for(draw, 28)
    for index, (path, timestamp) in enumerate(images[: columns * rows]):
        image = Image.open(path).convert("RGB")
        scale = min(tile_width / image.width, (tile_height - 40) / image.height)
        resized = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        )
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        background.paste(resized, (x + (tile_width - resized.width) // 2, y + 40))
        draw.rectangle((x, y, x + tile_width, y + 40), fill=(18, 18, 18))
        draw.text((x + 12, y + 5), short_time(timestamp), fill="white", font=font)
    destination.parent.mkdir(parents=True, exist_ok=True)
    background.save(destination, quality=91)


def make_probe(video: Path, duration: float, output_dir: Path) -> Path:
    frame_dir = output_dir / "probe-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    fractions = (0.04, 0.16, 0.30, 0.46, 0.64, 0.84, 0.95)
    times = [min(max(2.0, duration * value), max(2.0, duration - 1)) for value in fractions]
    images: list[tuple[Path, float]] = []
    for index, timestamp in enumerate(times):
        target = frame_dir / f"{index:02d}-{timestamp:09.3f}.jpg"
        extract_frame(video, timestamp, target)
        images.append((target, timestamp))
    destination = output_dir / "probe-contact.jpg"
    make_contact_sheet(images, destination)
    return destination


def command_probe(args: argparse.Namespace) -> None:
    bvid = extract_bvid(args.url)
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    page = resolve_video_page(args.url, args.page)
    _, metadata = video_metadata(bvid, page)
    player = player_data(metadata)
    subtitle_items = ((player.get("subtitle") or {}).get("subtitles") or [])
    selected = choose_subtitle(subtitle_items)
    cookie_configured = bool(load_bilibili_cookie()[0])
    manifest: dict[str, Any] = {
        "metadata": metadata,
        "official_subtitles": [
            {
                "language": row.get("lan"),
                "label": row.get("lan_doc"),
                "id": row.get("id"),
                "ai_type": row.get("ai_type"),
                "is_ai": subtitle_is_ai(row),
            }
            for row in subtitle_items
        ],
        "bilibili_cookie_configured": cookie_configured,
        "source_type": "official_subtitle" if selected else "undetermined",
        "next_action": "use_transcript" if selected else "prepare_media",
    }
    if selected:
        subtitle_url = str(selected.get("subtitle_url") or "")
        if subtitle_url.startswith("//"):
            subtitle_url = "https:" + subtitle_url
        segments = subtitle_segments(get_json(subtitle_url))
        write_transcript(output_dir, segments, "official_subtitle")
        manifest["selected_subtitle"] = {
            "language": selected.get("lan"),
            "label": selected.get("lan_doc"),
            "ai_type": selected.get("ai_type"),
            "is_ai": subtitle_is_ai(selected),
            "segment_count": len(segments),
        }
        say(f"发现官方字幕：{selected.get('lan_doc') or selected.get('lan')}")
    else:
        say("未发现官方字幕。")
    write_json(output_dir / "manifest.json", manifest)
    write_json(
        output_dir / "next-action.json",
        {
            "action": manifest["next_action"],
            "reason": (
                "official_subtitle_found"
                if selected
                else (
                    "official_subtitle_absent"
                    if cookie_configured
                    else "subtitle_not_visible_anonymously"
                )
            ),
            "inspect": "transcript.md" if selected else None,
            "warning": (
                None
                if selected or cookie_configured
                else (
                    "Bilibili may hide AI or CC subtitle tracks without login. "
                    "Authenticate with a saved or temporary Bilibili cookie before "
                    "concluding that no official subtitle exists."
                )
            ),
        },
    )
    say(f"输出：{output_dir}")


def command_prepare(args: argparse.Namespace) -> None:
    output_dir = Path(args.output).resolve()
    probe_args = argparse.Namespace(url=args.url, page=args.page, output=str(output_dir))
    command_probe(probe_args)
    manifest = read_json(output_dir / "manifest.json")
    if manifest["source_type"] == "official_subtitle":
        if not args.ignore_official_subtitle:
            return
        manifest["rejected_official_subtitle"] = {
            **(manifest.get("selected_subtitle") or {}),
            "reason": "manual_qa_content_mismatch",
        }
        manifest["source_type"] = "undetermined"
        manifest["next_action"] = "prepare_media"
        write_json(output_dir / "manifest.json", manifest)
        say("已按人工 QA 结论拒绝错挂字幕，继续下载媒体。")
    missing_media_tools = [
        name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)
    ]
    if missing_media_tools:
        raise PipelineError(
            "继续下载媒体前需要安装：" + ", ".join(missing_media_tools)
        )
    metadata = manifest["metadata"]
    play = fresh_playurl(metadata)
    dash = play.get("dash") or {}
    video_stream = choose_video_stream(dash)
    audio_stream = choose_audio_stream(dash)
    video_path = output_dir / "video.m4s"
    audio_path = output_dir / "audio.m4s"
    try:
        download_candidates(candidate_urls(video_stream), video_path)
    except PipelineError:
        say("视频下载地址可能已过期，刷新播放信息后重试…")
        refreshed = fresh_playurl(metadata).get("dash") or {}
        download_candidates(candidate_urls(choose_video_stream(refreshed)), video_path)
    if not media_is_decodable(video_path):
        say("视频完整性检查失败；丢弃损坏的测试产物并从备用地址重新下载…")
        video_path.unlink(missing_ok=True)
        video_path.with_suffix(video_path.suffix + ".part").unlink(missing_ok=True)
        refreshed = fresh_playurl(metadata).get("dash") or {}
        urls = candidate_urls(choose_video_stream(refreshed))
        download_candidates(list(reversed(urls)), video_path)
        if not media_is_decodable(video_path):
            raise PipelineError("视频流下载后仍无法解码")
    try:
        download_candidates(candidate_urls(audio_stream), audio_path)
    except PipelineError:
        say("音频下载地址可能已过期，刷新播放信息后重试…")
        refreshed = fresh_playurl(metadata).get("dash") or {}
        download_candidates(candidate_urls(choose_audio_stream(refreshed)), audio_path)
    if not media_is_decodable(audio_path):
        say("音频完整性检查失败；从备用地址重新下载…")
        audio_path.unlink(missing_ok=True)
        audio_path.with_suffix(audio_path.suffix + ".part").unlink(missing_ok=True)
        refreshed = fresh_playurl(metadata).get("dash") or {}
        urls = candidate_urls(choose_audio_stream(refreshed))
        download_candidates(list(reversed(urls)), audio_path)
        if not media_is_decodable(audio_path):
            raise PipelineError("音频流下载后仍无法解码")
    wav_path = output_dir / "audio.wav"
    convert_audio(audio_path, wav_path)
    duration = media_duration(video_path)
    probe_sheet = make_probe(video_path, duration, output_dir)
    manifest["media"] = {
        "video": str(video_path),
        "audio": str(audio_path),
        "wav": str(wav_path),
        "video_height": int(video_stream.get("height") or 0),
        "video_codec": str(video_stream.get("codecs") or ""),
        "audio_codec": str(audio_stream.get("codecs") or ""),
    }
    manifest["next_action"] = "inspect_probe_for_hard_subtitles"
    write_json(output_dir / "manifest.json", manifest)
    write_json(
        output_dir / "next-action.json",
        {
            "action": "inspect_probe_for_hard_subtitles",
            "inspect": str(probe_sheet),
            "if_hard_subtitles": "run hardsub",
            "if_no_hard_subtitles": "run transcribe",
        },
    )
    say(f"请只检查这一张图是否持续出现硬字幕：{probe_sheet}")


def parse_crop(value: str) -> tuple[float, float, float, float]:
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise PipelineError("--crop 必须是 left,top,right,bottom 四个 0–1 比例")
    left, top, right, bottom = parts
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise PipelineError("--crop 的比例必须满足 0<=left<right<=1, 0<=top<bottom<=1")
    return left, top, right, bottom


def image_dhash(path: Path) -> int:
    Image, _, _, ImageFilter, ImageOps = require_pillow()
    image = Image.open(path).convert("L")
    image = ImageOps.autocontrast(image).filter(ImageFilter.FIND_EDGES).resize((9, 8))
    getter = getattr(image, "get_flattened_data", image.getdata)
    pixels = list(getter())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return value


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def enhance_crop(source: Path, destination: Path) -> None:
    Image, _, ImageEnhance, ImageFilter, ImageOps = require_pillow()
    image = Image.open(source).convert("RGB")
    image = image.resize((image.width * 2, image.height * 2))
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.35)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.4, percent=180, threshold=2))
    gray.save(destination, quality=94)


def cache_root() -> Path:
    root = os.environ.get("MAKE_BILIBILI_NOTES_CACHE")
    if root:
        return Path(root).expanduser().resolve()
    candidates = [
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")),
        Path("/workspace/.cache"),
        Path(tempfile.gettempdir()),
    ]
    for base in candidates:
        target = base / "make-bilibili-notes"
        probe = target / f".write-test-{os.getpid()}"
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return target
        except OSError:
            with contextlib.suppress(OSError):
                probe.unlink()
    return Path(tempfile.gettempdir()) / "make-bilibili-notes"


def venv_python(kind: str) -> Path:
    return cache_root() / f"{kind}-venv" / "bin" / "python"


def module_available(module: str, python: Path | None = None) -> bool:
    if python is None:
        return importlib.util.find_spec(module) is not None
    if not python.exists():
        return False
    result = run(
        [str(python), "-c", f"import {module}"],
        check=False,
        capture=True,
    )
    return result.returncode == 0


def bootstrap_venv(kind: str, packages: list[str]) -> Path:
    target = cache_root() / f"{kind}-venv"
    python = target / "bin" / "python"
    if not python.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        say(f"创建可复用的 {kind.upper()} 环境：{target}")
        run([sys.executable, "-m", "venv", str(target)])
    say(f"检查/安装 {kind.upper()} 引擎…")
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *packages,
        ]
    )
    return python


def chinese_tessdata(*, bootstrap: bool) -> Path | None:
    target_dir = cache_root() / "tessdata"
    target = target_dir / "chi_sim.traineddata"
    if target.exists() and target.stat().st_size > 1_000_000:
        return target_dir
    if not bootstrap or not shutil.which("tesseract"):
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".traineddata.part")
    say("下载可复用的 Tesseract 简体中文快速模型…")
    if shutil.which("curl"):
        result = run(
            [
                "curl",
                "--http1.1",
                "--location",
                "--fail",
                "--silent",
                "--show-error",
                "--output",
                str(temporary),
                TESSDATA_FAST_CHI_SIM,
            ],
            check=False,
        )
        if result.returncode != 0:
            temporary.unlink(missing_ok=True)
            return None
    else:
        try:
            with request(TESSDATA_FAST_CHI_SIM) as response, temporary.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        except Exception:
            temporary.unlink(missing_ok=True)
            return None
    if temporary.stat().st_size <= 1_000_000:
        temporary.unlink(missing_ok=True)
        return None
    temporary.replace(target)
    return target_dir


def run_tesseract_ocr(
    frames: list[dict[str, Any]],
    output: Path,
    *,
    bootstrap: bool,
) -> bool:
    tessdata = chinese_tessdata(bootstrap=bootstrap)
    if tessdata is None:
        return False
    rows: list[dict[str, Any]] = []
    total = len(frames)
    for index, frame in enumerate(frames, start=1):
        result = run(
            [
                "tesseract",
                frame["path"],
                "stdout",
                "--tessdata-dir",
                str(tessdata),
                "-l",
                "chi_sim",
                "--psm",
                "6",
                "tsv",
            ],
            check=False,
            capture=True,
        )
        pieces: list[str] = []
        scores: list[float] = []
        for line in result.stdout.splitlines()[1:]:
            columns = line.split("\t", 11)
            if len(columns) != 12:
                continue
            text_value = columns[11].strip()
            try:
                confidence = float(columns[10])
            except ValueError:
                confidence = -1
            if text_value and confidence >= 0:
                pieces.append(text_value)
                scores.append(confidence / 100)
        rows.append(
            {
                "start": frame["start"],
                "end": frame["end"],
                "text": normalize_text(" ".join(pieces)),
                "confidence": sum(scores) / len(scores) if scores else None,
                "source": "hard_subtitle_ocr",
            }
        )
        if index == 1 or index % 20 == 0 or index == total:
            say(f"Tesseract OCR：{index}/{total}")
    write_json(output, rows)
    return True


def rapidocr_worker(payload: dict[str, Any]) -> None:
    from rapidocr_onnxruntime import RapidOCR
    from PIL import Image

    engine = RapidOCR()
    output: list[dict[str, Any]] = []
    total = len(payload["frames"])
    for index, row in enumerate(payload["frames"], start=1):
        result, _ = engine(row["path"])
        with Image.open(row["path"]) as image:
            image_height = image.height
        detected: list[dict[str, Any]] = []
        for item in result or []:
            if len(item) >= 3:
                box = item[0]
                ys = [float(point[1]) for point in box]
                xs = [float(point[0]) for point in box]
                detected.append(
                    {
                        "text": str(item[1]).strip(),
                        "confidence": float(item[2]),
                        "center_y": sum(ys) / len(ys),
                        "center_x": sum(xs) / len(xs),
                        "height": max(ys) - min(ys),
                    }
                )
        # Slides and lower-thirds often contain extra text in the same crop.
        # Spoken hard subtitles are normally the lowest centered line. Retain
        # that line rather than concatenating every detected label.
        lower = [item for item in detected if item["center_y"] >= image_height * 0.42]
        pieces: list[dict[str, Any]] = []
        if lower:
            lowest = max(item["center_y"] for item in lower)
            typical_height = sorted(item["height"] for item in lower)[len(lower) // 2]
            tolerance = max(12.0, typical_height * 0.65)
            pieces = [
                item for item in lower if item["center_y"] >= lowest - tolerance
            ]
            pieces.sort(key=lambda item: item["center_x"])
        text = " ".join(piece["text"] for piece in pieces if piece["text"])
        confidence = (
            sum(piece["confidence"] for piece in pieces) / len(pieces)
            if pieces
            else None
        )
        output.append(
            {
                "start": row["start"],
                "end": row["end"],
                "text": text,
                "confidence": confidence,
                "source": "hard_subtitle_ocr",
            }
        )
        if index == 1 or index % 20 == 0 or index == total:
            say(f"RapidOCR：{index}/{total}")
    write_json(Path(payload["output"]), output)


def run_rapidocr(
    frames: list[dict[str, Any]],
    output: Path,
    *,
    bootstrap: bool,
) -> bool:
    current_has = module_available("rapidocr_onnxruntime")
    cached_python = venv_python("ocr")
    if current_has:
        rapidocr_worker({"frames": frames, "output": str(output)})
        return True
    if not module_available("rapidocr_onnxruntime", cached_python):
        if not bootstrap:
            return False
        cached_python = bootstrap_venv("ocr", OCR_PACKAGES)
    payload_path = output.with_suffix(".worker-input.json")
    write_json(payload_path, {"frames": frames, "output": str(output)})
    result = run(
        [
            str(cached_python),
            str(Path(__file__).resolve()),
            "_rapidocr_worker",
            "--payload",
            str(payload_path),
        ],
        check=False,
    )
    payload_path.unlink(missing_ok=True)
    return result.returncode == 0 and output.exists()


def command_hardsub(args: argparse.Namespace) -> None:
    workdir = Path(args.workdir).resolve()
    manifest_path = workdir / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    video = Path(args.video).resolve() if args.video else workdir / "video.m4s"
    if not video.exists():
        raise PipelineError(f"找不到视频：{video}")
    left, top, right, bottom = parse_crop(args.crop)
    duration = media_duration(video)
    raw_dir = workdir / "hardsub" / "raw"
    enhanced_dir = workdir / "hardsub" / "enhanced"
    raw_dir.mkdir(parents=True, exist_ok=True)
    enhanced_dir.mkdir(parents=True, exist_ok=True)
    for generated in list(raw_dir.glob("*.jpg")) + list(enhanced_dir.glob("*.jpg")):
        generated.unlink()
    width_expr = f"iw*{right - left:.6f}"
    height_expr = f"ih*{bottom - top:.6f}"
    x_expr = f"iw*{left:.6f}"
    y_expr = f"ih*{top:.6f}"
    say(f"按 {args.interval:.2f}s 间隔提取字幕区域…")
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            (
                f"fps=1/{args.interval},"
                f"crop={width_expr}:{height_expr}:{x_expr}:{y_expr}"
            ),
            "-q:v",
            "2",
            str(raw_dir / "%06d.jpg"),
        ]
    )
    kept: list[dict[str, Any]] = []
    previous_hash: int | None = None
    for index, source in enumerate(sorted(raw_dir.glob("*.jpg"))):
        timestamp = index * args.interval
        current_hash = image_dhash(source)
        if previous_hash is not None and hamming(previous_hash, current_hash) <= args.hash_distance:
            continue
        target = enhanced_dir / source.name
        enhance_crop(source, target)
        kept.append(
            {
                "path": str(target),
                "start": timestamp,
                "end": min(duration, timestamp + args.interval),
            }
        )
        previous_hash = current_hash
    if not kept:
        raise PipelineError("裁剪后没有可用帧；请检查视频与 --crop")
    say(f"视觉去重：{len(list(raw_dir.glob('*.jpg')))} → {len(kept)} 帧")
    ocr_output = workdir / "hardsub" / "ocr-raw.json"
    ocr_engine: str | None = None
    used_ocr = False
    if args.ocr == "auto":
        calibration_output = workdir / "hardsub" / "ocr-calibration.json"
        calibration_frames = kept[: min(12, len(kept))]
        tesseract_ready = run_tesseract_ocr(
            calibration_frames,
            calibration_output,
            bootstrap=args.bootstrap_ocr,
        )
        calibration_rows = read_json(calibration_output) if tesseract_ready else []
        hit_ratio = (
            sum(bool(comparison_text(row.get("text") or "")) for row in calibration_rows)
            / len(calibration_rows)
            if calibration_rows
            else 0
        )
        say(f"OCR 校准：Tesseract 有效帧比例 {hit_ratio:.0%}")
        if tesseract_ready and hit_ratio >= 0.35:
            used_ocr = run_tesseract_ocr(
                kept,
                ocr_output,
                bootstrap=False,
            )
            if used_ocr:
                ocr_engine = "tesseract-chi_sim-fast"
        else:
            say("字体不适合 Tesseract，自动切换 RapidOCR…")
            used_ocr = run_rapidocr(
                kept,
                ocr_output,
                bootstrap=args.bootstrap_ocr,
            )
            if used_ocr:
                ocr_engine = "rapidocr_onnxruntime"
    elif args.ocr == "tesseract":
        used_ocr = run_tesseract_ocr(
            kept,
            ocr_output,
            bootstrap=args.bootstrap_ocr,
        )
        if used_ocr:
            ocr_engine = "tesseract-chi_sim-fast"
    if args.ocr == "rapidocr":
        used_ocr = run_rapidocr(
            kept,
            ocr_output,
            bootstrap=args.bootstrap_ocr,
        )
        if used_ocr:
            ocr_engine = "rapidocr_onnxruntime"
    recognized_segments: list[dict[str, Any]] = []
    if used_ocr:
        recognized_segments = dedupe_segments(read_json(ocr_output), args.text_similarity)
        recognized_segments = [
            row
            for row in recognized_segments
            if len(comparison_text(row["text"])) >= args.min_chars
            and (
                row.get("confidence") is None
                or float(row["confidence"]) >= args.min_confidence
            )
        ]
        if not recognized_segments:
            say("OCR 未得到可靠字幕，改为生成限量接触表供视觉识别。")
            used_ocr = False
    if used_ocr:
        write_transcript(workdir, recognized_segments, "hard_subtitle_ocr")
        manifest["source_type"] = "hard_subtitle_ocr"
        manifest["next_action"] = "review_transcript_then_write_note"
        write_json(
            workdir / "next-action.json",
            {
                "action": "review_transcript_then_write_note",
                "inspect": str(workdir / "transcript.md"),
                "warning": "OCR may confuse stylized Chinese glyphs; verify names and numbers.",
            },
        )
        say(f"OCR 与文本去重完成：{len(recognized_segments)} 条字幕。")
    else:
        sheets_dir = workdir / "hardsub" / "contact-sheets"
        sheets_dir.mkdir(parents=True, exist_ok=True)
        sheet_size = 8
        for offset in range(0, len(kept), sheet_size):
            items = [
                (Path(row["path"]), float(row["start"]))
                for row in kept[offset : offset + sheet_size]
            ]
            make_contact_sheet(
                items,
                sheets_dir / f"sheet-{offset // sheet_size + 1:04d}.jpg",
            )
        write_json(
            workdir / "hardsub" / "vision-captions.template.json",
            {
                "source_type": "hard_subtitle_vision",
                "segments": [
                    {"start": row["start"], "end": row["end"], "text": ""}
                    for row in kept
                ],
            },
        )
        manifest["source_type"] = "hard_subtitle_visual_review"
        manifest["next_action"] = "read_contact_sheets"
        write_json(
            workdir / "next-action.json",
            {
                "action": "read_contact_sheets",
                "inspect_directory": str(sheets_dir),
                "write": str(workdir / "hardsub" / "vision-captions.json"),
                "then": "run finalize --segments <vision-captions.json>",
                "reason": "Chinese OCR engine unavailable or disabled",
            },
        )
        say(f"未使用中文 OCR；已生成 {len(list(sheets_dir.glob('*.jpg')))} 张审阅图。")
    manifest["hard_subtitle"] = {
        "crop": [left, top, right, bottom],
        "interval": args.interval,
        "sampled_frames": len(list(raw_dir.glob("*.jpg"))),
        "deduplicated_frames": len(kept),
        "ocr": ocr_engine if used_ocr else "agent_vision",
    }
    write_json(manifest_path, manifest)


def normalized_asr_language(value: str) -> str:
    language = value.strip().lower().replace("_", "-")
    aliases = {
        "chinese": "zh",
        "中文": "zh",
        "mandarin": "zh",
        "cmn": "zh",
        "cantonese": "yue",
        "english": "en",
        "英语": "en",
    }
    return aliases.get(language, language)


def is_chinese_asr_language(value: str) -> bool:
    language = normalized_asr_language(value)
    return language in CHINESE_ASR_LANGUAGE_CODES or language.startswith("zh-")


def asr_engine_for_language(value: str) -> str:
    language = normalized_asr_language(value)
    if language == "auto":
        return "auto"
    if is_chinese_asr_language(language):
        return "qwen3-asr"
    return "faster-whisper"


def asr_packages_for_language(value: str, *, colab: bool) -> list[str]:
    engine = asr_engine_for_language(value)
    faster_packages = (
        COLAB_FASTER_WHISPER_PACKAGES if colab else FASTER_WHISPER_PACKAGES
    )
    if engine == "qwen3-asr":
        return list(QWEN_ASR_PACKAGES)
    if engine == "faster-whisper":
        return list(faster_packages)
    return [*faster_packages, *QWEN_ASR_PACKAGES]


def asr_modules_for_language(value: str) -> list[str]:
    engine = asr_engine_for_language(value)
    if engine == "qwen3-asr":
        return ["qwen_asr", "funasr", "soundfile", "torch"]
    if engine == "faster-whisper":
        return ["faster_whisper"]
    return ["faster_whisper", "qwen_asr", "funasr", "soundfile", "torch"]


def colab_command(auth: str, *parts: str) -> list[str]:
    executable = shutil.which("colab")
    if not executable:
        raise PipelineError(
            "未找到 Google Colab CLI。请先运行 `uv tool install google-colab-cli`，"
            "再用 `colab --auth=oauth2 whoami` 完成首次授权。"
        )
    return [executable, f"--auth={auth}", *parts]


def run_colab_transcription(
    args: argparse.Namespace,
    audio: Path,
    payload: dict[str, Any],
    raw_output: Path,
) -> dict[str, Any]:
    worker = Path(__file__).with_name("asr_worker.py")
    if not worker.exists():
        raise PipelineError(f"缺少 Colab 转录脚本：{worker}")
    colab_env = os.environ.copy()
    colab_env.pop("BILIBILI_COOKIE", None)
    colab_env.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    session = args.colab_session
    status = run(
        colab_command(args.colab_auth, "status", "-s", session),
        check=False,
        capture=True,
        env=colab_env,
    )
    status_text = "\n".join((status.stdout or "", status.stderr or "")).lower()
    created_session = status.returncode != 0 or "not found" in status_text
    if created_session:
        say(f"创建 Colab {args.colab_gpu} 会话：{session}…")
        run(
            colab_command(
                args.colab_auth,
                "new",
                "-s",
                session,
                "--gpu",
                args.colab_gpu,
            ),
            env=colab_env,
        )
    else:
        say(f"复用 Colab 会话：{session}")

    remote_payload = dict(payload)
    remote_payload.update(
        {
            "audio": COLAB_REMOTE_AUDIO,
            "output": COLAB_REMOTE_OUTPUT,
            "device": "cuda",
            "compute_type": args.colab_compute_type,
            "model_cache": "/content/.cache/make-bilibili-notes/models",
        }
    )
    payload_path = raw_output.with_name("colab-asr-input.json")
    write_json(payload_path, remote_payload)

    try:
        run(
            colab_command(
                args.colab_auth,
                "upload",
                "-s",
                session,
                str(audio),
                COLAB_REMOTE_AUDIO,
            ),
            env=colab_env,
        )
        run(
            colab_command(
                args.colab_auth,
                "upload",
                "-s",
                session,
                str(payload_path),
                COLAB_REMOTE_INPUT,
            ),
            env=colab_env,
        )
        run(
            colab_command(
                args.colab_auth,
                "install",
                "-s",
                session,
                *asr_packages_for_language(args.language, colab=True),
            ),
            env=colab_env,
        )
        requested_engine = asr_engine_for_language(args.language)
        if requested_engine == "auto":
            engine_message = (
                f"先用 Faster Whisper {ASR_LANGUAGE_DETECTION_MODEL} 检测语言，"
                f"中文转 Qwen3-ASR-1.7B，其他语言转 Faster Whisper {args.model}"
            )
        elif requested_engine == "qwen3-asr":
            engine_message = "使用 Qwen3-ASR-1.7B + FSMN-VAD ≤60 秒分块"
        else:
            engine_message = f"使用 Faster Whisper {args.model}"
        say(f"Colab {args.colab_gpu}：{engine_message}…")
        run(
            colab_command(
                args.colab_auth,
                "exec",
                "-s",
                session,
                "--timeout",
                str(args.colab_timeout),
                "-f",
                str(worker),
            ),
            env=colab_env,
        )
        run(
            colab_command(
                args.colab_auth,
                "download",
                "-s",
                session,
                COLAB_REMOTE_OUTPUT,
                str(raw_output),
            ),
            env=colab_env,
        )
    finally:
        for remote_path in (
            COLAB_REMOTE_AUDIO,
            COLAB_REMOTE_INPUT,
            COLAB_REMOTE_OUTPUT,
        ):
            run(
                colab_command(
                    args.colab_auth,
                    "rm",
                    "-s",
                    session,
                    remote_path,
                ),
                check=False,
                env=colab_env,
            )
        if created_session and not args.keep_colab_session:
            say(f"释放本次创建的 Colab 会话：{session}")
            run(
                colab_command(args.colab_auth, "stop", "-s", session),
                check=False,
                env=colab_env,
            )

    if not raw_output.exists():
        raise PipelineError("Colab 执行结束，但没有下载到转录结果")
    return {
        "session": session,
        "gpu": args.colab_gpu,
        "created_session": created_session,
        "kept_session": not created_session or args.keep_colab_session,
    }


def command_transcribe(args: argparse.Namespace) -> None:
    if args.backend == "colab" and not args.confirm_external_upload:
        raise PipelineError(
            "Colab 会上传规范化 WAV、非秘密任务清单和转写 worker。"
            "请先在任务 preflight 中取得用户授权，再添加 "
            "`--confirm-external-upload`。"
        )
    workdir = Path(args.workdir).resolve()
    manifest_path = workdir / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    audio = Path(args.audio).resolve() if args.audio else workdir / "audio.wav"
    if not audio.exists():
        raise PipelineError(f"找不到音频：{audio}")
    if (
        args.backend == "local"
        and asr_engine_for_language(args.language) == "qwen3-asr"
        and args.device != "cuda"
    ):
        raise PipelineError(
            "中文默认 Qwen3-ASR-1.7B 需要 CUDA。请改用 --backend colab，"
            "或在本地 NVIDIA GPU 上传入 --device cuda。"
        )
    if audio.suffix.lower() != ".wav":
        converted = workdir / "audio.wav"
        convert_audio(audio, converted)
        audio = converted
    metadata = manifest.get("metadata") or {}
    glossary = [item.strip() for item in (args.glossary or "").split(",") if item.strip()]
    prompt_parts = []
    if metadata.get("title"):
        prompt_parts.append(f"视频标题：{metadata['title']}")
    if glossary:
        prompt_parts.append("专有名词：" + "、".join(glossary))
    initial_prompt = "。".join(prompt_parts)
    model_cache = cache_root() / "models"
    raw_output = workdir / "asr-raw.json"
    payload = {
        "audio": str(audio),
        "output": str(raw_output),
        "model": args.model,
        "device": args.device,
        "compute_type": args.compute_type,
        "language": args.language,
        "language_detection_model": ASR_LANGUAGE_DETECTION_MODEL,
        "beam_size": args.beam_size,
        "initial_prompt": initial_prompt,
        "model_cache": str(model_cache),
    }
    backend_details: dict[str, Any] = {}
    if args.backend == "colab":
        backend_details = run_colab_transcription(args, audio, payload, raw_output)
    else:
        worker = Path(__file__).with_name("asr_worker.py")
        if not worker.exists():
            raise PipelineError(f"缺少 ASR worker：{worker}")
        python = Path(sys.executable)
        modules = asr_modules_for_language(args.language)
        if not all(module_available(module) for module in modules):
            engine = asr_engine_for_language(args.language)
            environment_name = {
                "auto": "asr-auto",
                "qwen3-asr": "asr-qwen",
                "faster-whisper": "asr",
            }[engine]
            python = venv_python(environment_name)
            if not all(module_available(module, python) for module in modules):
                if not args.bootstrap_asr:
                    raise PipelineError(
                        "未找到所需 ASR 依赖。重新运行并添加 --bootstrap-asr，"
                        "脚本会创建可复用的隔离环境。"
                    )
                python = bootstrap_venv(
                    environment_name,
                    asr_packages_for_language(args.language, colab=False),
                )
        model_cache.mkdir(parents=True, exist_ok=True)
        worker_env = os.environ.copy()
        worker_env.update(
            {
                "XDG_CACHE_HOME": str(cache_root()),
                "HF_HOME": str(cache_root() / "huggingface"),
                "HF_HUB_CACHE": str(model_cache),
                "HF_XET_CACHE": str(cache_root() / "xet"),
                # Xet otherwise writes logs below a read-only home in some Codex VMs.
                "HF_HUB_DISABLE_XET": "1",
            }
        )
        say("使用本地 ASR 路由转写；首次运行会下载并缓存所需模型…")
        payload_path = workdir / "asr-worker-input.json"
        write_json(payload_path, payload)
        try:
            run(
                [
                    str(python),
                    str(worker),
                    "--payload",
                    str(payload_path),
                ],
                env=worker_env,
            )
        finally:
            payload_path.unlink(missing_ok=True)
    raw = read_json(raw_output)
    write_transcript(workdir, raw["segments"], "audio_asr")
    transcript_text = "\n".join(
        normalize_text(str(row.get("text") or "")) for row in raw["segments"]
    )
    glossary_review = {
        "terms": [
            {
                "term": term,
                "occurrences": transcript_text.count(term),
                "status": "present" if term in transcript_text else "missing_review_required",
            }
            for term in glossary
        ]
    }
    write_json(workdir / "term-review.json", glossary_review)
    missing_terms = [
        row["term"]
        for row in glossary_review["terms"]
        if row["status"] == "missing_review_required"
    ]
    manifest["source_type"] = "audio_asr"
    manifest["next_action"] = "review_transcript_then_write_note"
    manifest["asr"] = {
        "engine": raw.get("engine"),
        "backend": args.backend,
        "model": raw.get("model"),
        "requested_language": normalized_asr_language(args.language),
        "language": raw.get("language"),
        "language_probability": raw.get("language_probability"),
        "language_detection": raw.get("language_detection"),
        "vad_model": raw.get("vad_model"),
        "max_segment_seconds": raw.get("max_segment_seconds"),
        "vad_segment_count": raw.get("vad_segment_count"),
        "initial_prompt": initial_prompt,
        "external_upload_confirmed": args.backend == "colab",
        **backend_details,
    }
    write_json(manifest_path, manifest)
    write_json(
        workdir / "next-action.json",
        {
            "action": "review_transcript_then_write_note",
            "inspect": str(workdir / "transcript.md"),
            "term_review": str(workdir / "term-review.json"),
            "missing_glossary_terms": missing_terms,
            "warning": "Check proper nouns, numbers and title terminology against the video.",
        },
    )
    say(f"转写完成：{workdir / 'transcript.md'}")


def command_finalize(args: argparse.Namespace) -> None:
    workdir = Path(args.workdir).resolve()
    value = read_json(Path(args.segments).resolve())
    segments = value.get("segments") if isinstance(value, dict) else value
    if not isinstance(segments, list):
        raise PipelineError("输入 JSON 必须是 segment 数组或包含 segments 数组")
    source_type = (
        value.get("source_type", args.source_type)
        if isinstance(value, dict)
        else args.source_type
    )
    write_transcript(workdir, segments, source_type)
    manifest_path = workdir / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    manifest["source_type"] = source_type
    manifest["next_action"] = "review_transcript_then_write_note"
    write_json(manifest_path, manifest)
    write_json(
        workdir / "next-action.json",
        {
            "action": "review_transcript_then_write_note",
            "inspect": str(workdir / "transcript.md"),
        },
    )


def command_doctor(_: argparse.Namespace) -> None:
    tools = {
        name: shutil.which(name)
        for name in ("ffmpeg", "ffprobe", "tesseract", "curl", "jq", "colab")
    }
    tesseract_languages: list[str] = []
    if tools["tesseract"]:
        result = run(["tesseract", "--list-langs"], check=False, capture=True)
        tesseract_languages = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and not line.startswith("List of")
        ]
    try:
        cookie, cookie_source = load_bilibili_cookie()
        cookie_error = None
    except PipelineError as exc:
        cookie = ""
        cookie_source = "invalid_local_file"
        cookie_error = str(exc)
    payload = {
        "python": sys.version.split()[0],
        "tools": tools,
        "pillow": module_available("PIL"),
        "rapidocr_current": module_available("rapidocr_onnxruntime"),
        "rapidocr_cached": module_available("rapidocr_onnxruntime", venv_python("ocr")),
        "faster_whisper_current": module_available("faster_whisper"),
        "faster_whisper_cached": module_available("faster_whisper", venv_python("asr")),
        "qwen_asr_current": module_available("qwen_asr"),
        "qwen_asr_cached": module_available("qwen_asr", venv_python("asr-qwen")),
        "bilibili_cookie_configured": bool(cookie),
        "bilibili_cookie_source": cookie_source,
        "bilibili_cookie_error": cookie_error,
        "colab_cli": tools["colab"],
        "tesseract_languages": tesseract_languages,
        "cache": str(cache_root()),
        "ready_core": bool(tools["ffmpeg"] and tools["ffprobe"] and module_available("PIL")),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def bilibili_auth_status() -> dict[str, Any]:
    try:
        cookie, source = load_bilibili_cookie()
    except PipelineError as exc:
        return {
            "status": "unsafe_configuration",
            "configured": True,
            "authenticated": False,
            "source": "file",
            "next_action": str(exc),
        }
    if not cookie:
        return {
            "status": "not_configured",
            "configured": False,
            "authenticated": False,
            "source": "none",
            "next_action": (
                "Run `auth-save --service bilibili`, then retry."
            ),
        }
    try:
        with request(api_url("/x/web-interface/nav"), timeout=15) as response:
            payload = json.load(response)
    except (OSError, TypeError, ValueError):
        return {
            "status": "unreachable",
            "configured": True,
            "authenticated": False,
            "source": source,
            "next_action": (
                "Check network access, then retry without printing the cookie."
            ),
        }
    if not isinstance(payload, dict):
        return {
            "status": "unreachable",
            "configured": True,
            "authenticated": False,
            "source": source,
            "next_action": "Retry after checking the Bilibili API response.",
        }
    code = payload.get("code")
    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}
    authenticated = bool(data.get("isLogin"))
    if code not in (None, 0, -101):
        return {
            "status": "api_error",
            "configured": True,
            "authenticated": False,
            "source": source,
            "next_action": (
                "Clear the saved cookie and any BILIBILI_COOKIE override to "
                "continue anonymously, or retry later."
            ),
        }
    return {
        "status": "ready" if authenticated else "invalid",
        "configured": True,
        "authenticated": authenticated,
        "source": source,
        "next_action": (
            None
            if authenticated
            else "Refresh the saved Bilibili Cookie with `auth-save`."
        ),
    }


def command_auth_save(args: argparse.Namespace) -> int:
    del args
    cookie = os.environ.get("BILIBILI_COOKIE", "").strip()
    if not cookie:
        if not sys.stdin.isatty():
            raise PipelineError(
                "需要交互式终端输入 Cookie，或先设置 BILIBILI_COOKIE。"
            )
        cookie = getpass.getpass("粘贴 Bilibili Cookie（输入不会显示）：")
    path = save_bilibili_cookie(cookie)
    print(
        json.dumps(
            {
                "service": "bilibili",
                "saved": True,
                "path": str(path),
                "mode": "0600",
                "next_action": (
                    "Unset BILIBILI_COOKIE, then run "
                    "`auth-check --service bilibili` to verify the saved file."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_auth_clear(args: argparse.Namespace) -> int:
    del args
    path = bilibili_cookie_path()
    removed = path.exists() or path.is_symlink()
    path.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "service": "bilibili",
                "removed": removed,
                "path": str(path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def colab_auth_status(auth: str) -> dict[str, Any]:
    executable = shutil.which("colab")
    if not executable:
        return {
            "status": "not_installed",
            "configured": False,
            "authenticated": False,
            "next_action": "Install google-colab-cli, then complete OAuth2 setup.",
        }
    token_path = Path.home() / ".config" / "colab-cli" / "token.json"
    if auth == "oauth2" and not token_path.exists():
        return {
            "status": "not_configured",
            "configured": False,
            "authenticated": False,
            "next_action": "Run `colab --auth=oauth2 whoami` interactively once.",
        }
    colab_env = os.environ.copy()
    colab_env.pop("BILIBILI_COOKIE", None)
    try:
        result = subprocess.run(
            [executable, f"--auth={auth}", "whoami"],
            check=False,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            env=colab_env,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "unreachable",
            "configured": True,
            "authenticated": False,
            "next_action": "Check network access and retry Colab OAuth validation.",
        }
    authenticated = result.returncode == 0
    combined = "\n".join((result.stdout or "", result.stderr or "")).lower()
    old_cli = "no such command" in combined or "unknown command" in combined
    status = (
        "ready" if authenticated else ("update_required" if old_cli else "invalid")
    )
    return {
        "status": status,
        "configured": True,
        "authenticated": authenticated,
        "next_action": (
            None
            if authenticated
            else (
                "Update google-colab-cli before retrying."
                if old_cli
                else "Refresh the cached OAuth2 consent, then retry."
            )
        ),
    }


def command_auth_check(args: argparse.Namespace) -> int:
    checks: dict[str, Any] = {}
    if args.service in ("all", "bilibili"):
        checks["bilibili"] = bilibili_auth_status()
    if args.service in ("all", "colab"):
        checks["colab"] = colab_auth_status(args.colab_auth)
    ready = all(item["status"] == "ready" for item in checks.values())
    can_continue = all(
        item["status"] == "ready"
        or (service == "bilibili" and item["status"] == "not_configured")
        for service, item in checks.items()
    )
    print(
        json.dumps(
            {
                "service": args.service,
                "ready": ready,
                "can_continue": can_continue,
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if can_continue else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare Bilibili videos for evidence-checked Obsidian notes."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Inspect reusable VM tools and cached engines.")

    auth_check = subparsers.add_parser(
        "auth-check",
        help="Validate optional Bilibili and Colab credentials without exposing them.",
    )
    auth_check.add_argument(
        "--service",
        choices=("all", "bilibili", "colab"),
        required=True,
    )
    auth_check.add_argument(
        "--colab-auth",
        choices=("oauth2", "adc"),
        default="oauth2",
    )

    auth_save = subparsers.add_parser(
        "auth-save",
        help="Save a Bilibili cookie in a private local file.",
    )
    auth_save.add_argument("--service", choices=("bilibili",), required=True)

    auth_clear = subparsers.add_parser(
        "auth-clear",
        help="Remove the saved Bilibili cookie file.",
    )
    auth_clear.add_argument("--service", choices=("bilibili",), required=True)

    probe = subparsers.add_parser("probe", help="Fetch metadata and official subtitles.")
    probe.add_argument("url")
    probe.add_argument("--page", type=int)
    probe.add_argument("--output", required=True)

    prepare = subparsers.add_parser(
        "prepare",
        help="Probe, download compact media, make audio WAV and a visual probe sheet.",
    )
    prepare.add_argument("url")
    prepare.add_argument("--page", type=int)
    prepare.add_argument("--output", required=True)
    prepare.add_argument(
        "--ignore-official-subtitle",
        action="store_true",
        help=(
            "Download media only after transcript QA proves that Bilibili attached "
            "an unrelated subtitle track."
        ),
    )

    hardsub = subparsers.add_parser(
        "hardsub",
        help="Crop, visually deduplicate and OCR hard subtitles.",
    )
    hardsub.add_argument("workdir")
    hardsub.add_argument("--video")
    hardsub.add_argument("--crop", default="0.10,0.72,0.90,0.92")
    hardsub.add_argument("--interval", type=float, default=1.2)
    hardsub.add_argument("--hash-distance", type=int, default=3)
    hardsub.add_argument(
        "--ocr",
        choices=("auto", "tesseract", "rapidocr", "none"),
        default="auto",
    )
    hardsub.add_argument("--bootstrap-ocr", action="store_true")
    hardsub.add_argument("--text-similarity", type=float, default=0.91)
    hardsub.add_argument("--min-confidence", type=float, default=0.45)
    hardsub.add_argument("--min-chars", type=int, default=2)

    transcribe = subparsers.add_parser(
        "transcribe",
        help=(
            "Transcribe with language routing: Qwen3-ASR for Chinese and "
            "Faster Whisper for English/other languages."
        ),
    )
    transcribe.add_argument("workdir")
    transcribe.add_argument("--audio")
    transcribe.add_argument(
        "--backend",
        choices=("local", "colab"),
        default="local",
    )
    transcribe.add_argument("--model", default="small")
    transcribe.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    transcribe.add_argument("--compute-type", default="int8")
    transcribe.add_argument(
        "--language",
        default="auto",
        help="auto detects the spoken language; pass zh or en to skip detection.",
    )
    transcribe.add_argument("--beam-size", type=int, default=3)
    transcribe.add_argument("--glossary", default="")
    transcribe.add_argument("--bootstrap-asr", action="store_true")
    transcribe.add_argument("--colab-session", default="bili-asr")
    transcribe.add_argument(
        "--colab-gpu",
        choices=("T4", "L4", "G4", "A100", "H100"),
        default="T4",
    )
    transcribe.add_argument(
        "--colab-auth",
        choices=("oauth2", "adc"),
        default="oauth2",
    )
    transcribe.add_argument("--colab-compute-type", default="int8_float16")
    transcribe.add_argument("--colab-timeout", type=int, default=7200)
    transcribe.add_argument("--keep-colab-session", action="store_true")
    transcribe.add_argument("--confirm-external-upload", action="store_true")

    finalize = subparsers.add_parser(
        "finalize",
        help="Normalize and deduplicate OCR/vision/ASR segment JSON.",
    )
    finalize.add_argument("workdir")
    finalize.add_argument("--segments", required=True)
    finalize.add_argument("--source-type", default="hard_subtitle_vision")

    worker_ocr = subparsers.add_parser("_rapidocr_worker")
    worker_ocr.add_argument("--payload", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            command_doctor(args)
        elif args.command == "auth-check":
            return command_auth_check(args)
        elif args.command == "auth-save":
            return command_auth_save(args)
        elif args.command == "auth-clear":
            return command_auth_clear(args)
        elif args.command == "probe":
            command_probe(args)
        elif args.command == "prepare":
            command_prepare(args)
        elif args.command == "hardsub":
            command_hardsub(args)
        elif args.command == "transcribe":
            command_transcribe(args)
        elif args.command == "finalize":
            command_finalize(args)
        elif args.command == "_rapidocr_worker":
            rapidocr_worker(read_json(Path(args.payload)))
        else:
            parser.error("unknown command")
        return 0
    except (PipelineError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
