---
name: make-bilibili-notes
description: Turn a Bilibili video or BV URL into a timestamped, evidence-checked Obsidian Markdown note, with official/AI subtitle retrieval, hard-subtitle OCR, and local or Google Colab GPU speech transcription. Use when a user asks to summarize, transcribe, take notes from, fact-check, or archive a Bilibili video. Always prefer official subtitles, then cropped hard-subtitle Chinese OCR with deduplication, then audio ASR; add a mandatory claim/evidence/risk-omission table for health, legal, or investment topics.
---

# Make Bilibili Notes

Convert a Bilibili video into a traceable note without making the agent perform
downloads, frame sampling, OCR repetition removal, or speech recognition by hand.

## Non-negotiable source order

Use exactly this order:

1. Official Bilibili subtitles.
2. Hard subtitles cropped from the video and batch-recognized by Chinese OCR.
3. Audio transcription only when the probe shows no hard subtitles.

Never skip an available higher-priority source because a lower-priority source is
more convenient. Never infer video content from its title or description.

## Locate the script

Set `SKILL_DIR` to the directory containing this `SKILL.md`. Run:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" doctor
```

The core requires `ffmpeg`, `ffprobe`, and Pillow. Optional OCR and ASR engines
are installed in a reusable cache only when their path is selected.

If the user has supplied a Bilibili login cookie, expose it only for this
process as `BILIBILI_COOKIE`. This can reveal login-only AI subtitle tracks.
Never print, persist, or place the cookie in the note. The manifest records only
whether a cookie was configured.

An empty anonymous subtitle response does not prove that a video has no official
or AI subtitle track. Before choosing OCR or ASR, retry with `BILIBILI_COOKIE`
when the user has chosen to provide one; otherwise record the authentication
limitation in the note.

## Workflow

### 1. Prepare once

Create a work directory outside the skill:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" prepare \
  "BILIBILI_URL" --output "WORKDIR"
```

Read `WORKDIR/next-action.json`. Do not improvise around it.

- `use_transcript`: official subtitles are already normalized in
  `WORKDIR/transcript.md`.
- `inspect_probe_for_hard_subtitles`: visually inspect only
  `WORKDIR/probe-contact.jpg`.

The probe decision is binary: do the sampled frames repeatedly show sentence-like
captions synchronized with speech? Ignore slide headings, logos, watermarks, and
occasional on-screen labels.

### 2A. Hard subtitles

If the probe repeatedly contains hard subtitles, run:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" hardsub "WORKDIR" \
  --bootstrap-ocr
```

The default crop is the center-bottom subtitle band. If it misses the captions,
estimate normalized `left,top,right,bottom` coordinates from the probe and rerun:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" hardsub "WORKDIR" \
  --crop "0.10,0.72,0.90,0.92" --bootstrap-ocr
```

The script samples frames, crops the band, enhances it, removes near-identical
consecutive frames, and calibrates the existing Tesseract binary with a cached
Chinese fast model. If the font fails calibration it automatically switches to
RapidOCR. It then filters low-confidence noise and deduplicates repeated text.

For a stylized font that Tesseract consistently misses, rerun the same command
with `--ocr rapidocr --bootstrap-ocr`. RapidOCR is slower and is therefore a
targeted fallback, not the default.

If OCR is unavailable or the font defeats it, `next-action.json` points to
`hardsub/contact-sheets/`. Read the sheets in filename order and write:

```json
{
  "source_type": "hard_subtitle_vision",
  "segments": [
    {"start": 0.0, "end": 2.4, "text": "识别出的字幕"}
  ]
}
```

Then normalize it:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" finalize "WORKDIR" \
  --segments "WORKDIR/hardsub/vision-captions.json"
```

Do not transcribe audio merely because OCR contains a few errors. Correct names,
numbers, and obvious glyph confusions from nearby frames first. Use audio only as
a narrowly scoped cross-check when a hard-subtitle phrase remains ambiguous.

### 2B. No hard subtitles

If the probe has no recurring hard subtitles, read
[references/asr-backends.md](references/asr-backends.md). On a machine without a
fast local GPU, prefer the official Google Colab CLI backend:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" transcribe "WORKDIR" \
  --backend colab --model large-v3 --colab-gpu T4 \
  --glossary "TERM1,TERM2"
```

The command reuses a named active session, installs Faster Whisper remotely,
uploads only the audio and a non-secret job manifest, downloads timestamped
JSON, and stops a session it created. Add `--keep-colab-session` only when more
videos will be processed immediately.

Use local CPU/CUDA only when Colab is unavailable or the user asks to keep audio
local:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" transcribe "WORKDIR" \
  --backend local --model small --bootstrap-asr --glossary "TERM1,TERM2"
```

The script reuses a cached Faster Whisper environment and model, uses CPU `int8`,
VAD, timestamps, and the video title plus glossary as an initial prompt. `small`
is the default speed/quality choice for cloud VMs. Use `medium` only when the
content is terminology-heavy or the first pass fails a sample QA check.

Build the glossary from the title, description, slide text, speaker names, and
domain terms before transcription. This materially reduces Chinese homophone
errors.

### 3. Transcript QA

Before summarizing:

1. Inspect `manifest.json` and `transcript.md`.
2. Cross-check at least the opening, one middle section, and the ending.
3. Correct proper nouns, quantities, units, negations, and conclusion wording.
4. Keep uncertainty explicit. Do not silently turn OCR/ASR guesses into facts.
5. Only then structure and compress the transcript.

For a transcript too large to review in one pass, process chronological chunks
with overlapping boundary context. Preserve each chunk's timestamps, then merge
and deduplicate the chunk notes. Do not write a whole-video conclusion until all
chunks have been reviewed.

### 4. Write the Obsidian note

Read [references/note-spec.md](references/note-spec.md) and follow its YAML,
timeline, distinction between video claims and external additions, English tags,
and method-log requirements.

For slide/PPT-style videos, preserve a few stable, information-dense frames when
they explain a relationship better than prose. Do not save decorative duplicates.

### 5. High-risk topics

Classify the topic before drafting. If it contains health/medical, legal,
investment/financial, tax, or similarly consequential advice, read
[references/high-risk-evidence.md](references/high-risk-evidence.md).

The note must include a source-backed table containing at least:

`原视频主张 | 证据等级 | 风险遗漏`

Browse current primary or authoritative sources. Separate what the video says from
what outside evidence supports. A product demonstration, testimonial, mechanism,
or the video's own citation is not independent validation.

## Rules for low-reasoning models

- Run the script before reasoning about content.
- Obey `next-action.json`; make only the hard-subtitle yes/no visual decision.
- Inspect one bounded artifact at a time, not hundreds of raw frames.
- Never manually recreate operations already provided by the script.
- Never claim complete coverage when download, OCR, or ASR is partial.
- Preserve timestamps and source type in the final note.
- Report method failures and fallbacks in the note's method log.
- If a high-risk claim cannot be verified, label it `未核实`; do not fill gaps
  with plausible-sounding explanations.

## Common failures

- Expired or interrupted CDN URLs: `prepare` automatically retries, resumes, and
  refreshes playback information.
- Stylized Chinese hard subtitles: adjust the crop, then use generated contact
  sheets if OCR remains poor.
- Chinese ASR homophones: add a glossary and rerun; upgrade from `small` to
  `medium` only after a failed sample check.
- Missing Chinese Tesseract data: `--bootstrap-ocr` downloads only the Chinese
  fast model into the skill cache; it does not overwrite system packages.
- Highly stylized subtitles: use `--ocr rapidocr --bootstrap-ocr`, then fall
  back to bounded contact sheets if recognition remains poor.
- Missing Faster Whisper or proxy SOCKS support: `--bootstrap-asr` installs both
  into the skill cache.
- Colab is unauthenticated or unavailable: run `colab --auth=oauth2 new`, verify
  `colab status`, stop the test session, then retry. Do not silently fall back to
  a multi-hour local CPU job.
