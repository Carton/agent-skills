#!/usr/bin/env python3
"""Route English audio to Faster Whisper and Chinese audio to Qwen3-ASR."""

from __future__ import annotations

import argparse
import gc
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_INPUT_PATH = Path("/content/make-bilibili-notes-input.json")
QWEN_ASR_MODEL = "Qwen/Qwen3-ASR-1.7B"
QWEN_VAD_MODEL = "funasr/fsmn-vad"
MAX_QWEN_SEGMENT_MS = 60_000
MIN_LANGUAGE_CONFIDENCE = 0.65
CHINESE_LANGUAGE_CODES = {
    "zh",
    "yue",
    "wuu",
    "nan",
    "hak",
    "gan",
    "hsn",
    "cjy",
}


def normalize_text(value: str) -> str:
    value = value.replace("\u3000", " ").replace("\ufeff", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalized_language(value: str) -> str:
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


def is_chinese_language(value: str) -> bool:
    language = normalized_language(value)
    return language in CHINESE_LANGUAGE_CODES or language.startswith("zh-")


def split_long_segments(
    segments: list[list[int]], max_segment_ms: int = MAX_QWEN_SEGMENT_MS
) -> list[list[int]]:
    result: list[list[int]] = []
    for start_ms, end_ms in segments:
        cursor = start_ms
        while end_ms - cursor > max_segment_ms:
            result.append([cursor, cursor + max_segment_ms])
            cursor += max_segment_ms
        if end_ms > cursor:
            result.append([cursor, end_ms])
    return result


def pack_vad_segments(
    segments: list[list[int]], max_span_ms: int = MAX_QWEN_SEGMENT_MS
) -> list[list[int]]:
    split_segments = split_long_segments(segments, max_span_ms)
    if not split_segments:
        return []
    packed: list[list[int]] = []
    current_start, current_end = split_segments[0]
    for start_ms, end_ms in split_segments[1:]:
        if end_ms - current_start <= max_span_ms:
            current_end = end_ms
        else:
            packed.append([current_start, current_end])
            current_start, current_end = start_ms, end_ms
    packed.append([current_start, current_end])
    return packed


def cleanup_cuda() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def detect_language(payload: dict[str, Any]) -> tuple[str, float]:
    from faster_whisper import WhisperModel

    detector = WhisperModel(
        payload.get("language_detection_model", "tiny"),
        device=payload["device"],
        compute_type=payload["compute_type"],
        download_root=payload["model_cache"],
    )
    unused_segments, info = detector.transcribe(
        payload["audio"],
        language=None,
        beam_size=1,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
    )
    language = normalized_language(str(info.language))
    probability = float(info.language_probability)
    del unused_segments, detector
    cleanup_cuda()
    return language, probability


def resolve_language(payload: dict[str, Any]) -> tuple[str, float | None, str]:
    requested = normalized_language(str(payload.get("language") or "auto"))
    if requested != "auto":
        return requested, None, "explicit"
    language, probability = detect_language(payload)
    if probability < MIN_LANGUAGE_CONFIDENCE:
        raise RuntimeError(
            f"语言检测置信度过低：{language} ({probability:.3f})。"
            "请试听开头后显式传入 --language zh 或 --language en。"
        )
    return language, probability, "faster-whisper-tiny"


def transcribe_faster_whisper(
    payload: dict[str, Any],
    language: str,
) -> tuple[list[dict[str, Any]], str, float | None]:
    from faster_whisper import WhisperModel

    model = WhisperModel(
        payload["model"],
        device=payload["device"],
        compute_type=payload["compute_type"],
        download_root=payload["model_cache"],
    )
    segments, info = model.transcribe(
        payload["audio"],
        language=language,
        beam_size=payload["beam_size"],
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        initial_prompt=payload.get("initial_prompt") or None,
        condition_on_previous_text=True,
    )
    rows: list[dict[str, Any]] = []
    for segment in segments:
        text = normalize_text(segment.text)
        if text:
            rows.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": text,
                    "confidence": None,
                    "source": "audio_asr",
                }
            )
    return (
        rows,
        normalized_language(str(getattr(info, "language", language))),
        getattr(info, "language_probability", None),
    )


def detect_vad_segments(audio_path: str) -> list[list[int]]:
    from funasr import AutoModel

    vad_model = AutoModel(
        model=QWEN_VAD_MODEL,
        hub="hf",
        device="cuda",
        disable_update=True,
    )
    result = vad_model.generate(input=audio_path)
    segments = result[0].get("value") or result[0].get("timestamp") or []
    del vad_model
    cleanup_cuda()
    normalized = [[int(start), int(end)] for start, end in segments]
    return pack_vad_segments(normalized)


def transcribe_qwen(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    import torch

    if payload["device"] != "cuda" or not torch.cuda.is_available():
        raise RuntimeError(
            "中文默认 Qwen3-ASR-1.7B 需要 CUDA；请使用 Colab 后端或本地 CUDA。"
        )

    import soundfile as sf
    from qwen_asr import Qwen3ASRModel

    vad_segments = detect_vad_segments(payload["audio"])
    if not vad_segments:
        return [], 0
    audio, sample_rate = sf.read(payload["audio"], dtype="float32", always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    if sample_rate != 16_000:
        raise RuntimeError(f"Qwen ASR 需要 16 kHz 音频，实际为 {sample_rate} Hz")
    chunks = [
        (
            audio[
                round(start_ms / 1000 * sample_rate) : round(
                    end_ms / 1000 * sample_rate
                )
            ],
            sample_rate,
        )
        for start_ms, end_ms in vad_segments
    ]

    model = Qwen3ASRModel.from_pretrained(
        QWEN_ASR_MODEL,
        dtype=torch.float16,
        device_map="cuda:0",
        max_inference_batch_size=2,
        max_new_tokens=512,
    )
    context = str(payload.get("initial_prompt") or "")
    rows: list[dict[str, Any]] = []
    for offset in range(0, len(chunks), 2):
        batch = chunks[offset : offset + 2]
        results = model.transcribe(
            audio=batch,
            context=[context] * len(batch),
            language=["Chinese"] * len(batch),
        )
        for (start_ms, end_ms), result in zip(
            vad_segments[offset : offset + len(batch)], results
        ):
            text = normalize_text(result.text)
            if text:
                rows.append(
                    {
                        "start": start_ms / 1000,
                        "end": end_ms / 1000,
                        "text": text,
                        "confidence": None,
                        "source": "audio_asr",
                    }
                )
    return rows, len(vad_segments)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, default=DEFAULT_INPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload: dict[str, Any] = json.loads(args.payload.read_text(encoding="utf-8"))
    output_path = Path(payload["output"])
    language, detected_probability, detection_method = resolve_language(payload)

    if is_chinese_language(language):
        rows, vad_segment_count = transcribe_qwen(payload)
        result = {
            "engine": "qwen3-asr",
            "model": QWEN_ASR_MODEL,
            "language": language,
            "language_probability": detected_probability,
            "language_detection": detection_method,
            "vad_model": QWEN_VAD_MODEL,
            "max_segment_seconds": MAX_QWEN_SEGMENT_MS / 1000,
            "vad_segment_count": vad_segment_count,
            "segments": rows,
        }
    else:
        rows, output_language, model_probability = transcribe_faster_whisper(
            payload, language
        )
        result = {
            "engine": "faster-whisper",
            "model": payload["model"],
            "language": output_language,
            "language_probability": (
                detected_probability
                if detected_probability is not None
                else model_probability
            ),
            "language_detection": detection_method,
            "segments": rows,
        }
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(result['segments'])} {result['engine']} segments to {output_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
