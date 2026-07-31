#!/usr/bin/env python3
"""Run Faster Whisper inside a Google Colab CLI session."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


INPUT_PATH = Path("/content/make-bilibili-notes-input.json")


def normalize_text(value: str) -> str:
    value = value.replace("\u3000", " ").replace("\ufeff", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def main() -> None:
    from faster_whisper import WhisperModel

    payload: dict[str, Any] = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    output_path = Path(payload["output"])
    model = WhisperModel(
        payload["model"],
        device="cuda",
        compute_type=payload["compute_type"],
        download_root=payload["model_cache"],
    )
    segments, info = model.transcribe(
        payload["audio"],
        language=payload["language"],
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
    output_path.write_text(
        json.dumps(
            {
                "language": getattr(info, "language", payload["language"]),
                "language_probability": getattr(info, "language_probability", None),
                "segments": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} segments to {output_path}", flush=True)


if __name__ == "__main__":
    main()
