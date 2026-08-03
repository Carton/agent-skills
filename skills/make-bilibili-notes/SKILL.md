---
name: make-bilibili-notes
description: Turn a Bilibili video or BV URL into a timestamped, evidence-checked Obsidian Markdown note with a complete, polished prose rendering of the transcript, using official/AI subtitle retrieval, hard-subtitle OCR, and language-routed local or Google Colab speech transcription. Use when a user asks to summarize, transcribe, take notes from, fact-check, or archive a Bilibili video. Always prefer official subtitles, then cropped hard-subtitle Chinese OCR with deduplication, then audio ASR; route Chinese audio to Qwen3-ASR with FSMN-VAD and English audio to Faster Whisper; add a mandatory claim/evidence/risk-omission table for health, legal, or investment topics.
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

## One-time setup and preflight

Keep account setup separate from video processing. Read
[references/setup.md](references/setup.md) when `doctor` reports a missing tool,
when the user wants login-visible Bilibili subtitles, or before selecting Colab.

Run only the credential check needed by the chosen path:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" auth-check --service bilibili
python3 "$SKILL_DIR/scripts/bili_video.py" auth-check --service colab
```

On a trusted personal machine, persist a Bilibili browser cookie once with
`auth-save --service bilibili`. The script stores it outside the repository at
`~/.config/make-bilibili-notes/bilibili-cookie` with private permissions and
automatically reuses it. Read [references/setup.md](references/setup.md) for the
interactive login, refresh, and removal commands.

At task preflight, ask once whether Colab may be used if audio ASR becomes
necessary. Explain that this uploads the normalized WAV, a non-secret job
manifest, and the bundled transcription worker to the user's Google Colab
runtime; remote job files are removed afterward. Offer two choices: authorize
Colab for this video, or keep the audio local. Translate this disclosure into the
user's language.

If the user authorizes Colab, validate its account now and remember the choice
for this task. Later pass `--confirm-external-upload` without asking again. If the
user declines, never call the Colab backend. A direct, informed request to use
Colab for the current video also counts as this confirmation.

The checks emit redacted JSON and never print cookies, tokens, or account
identities. A missing optional Bilibili cookie returns `can_continue: true` so
the anonymous path remains usable. Colab authentication is required only when
Colab is selected. Account login and OAuth consent are human setup steps; do not
search for credentials or perform them silently.

Resolve a Bilibili login cookie from `BILIBILI_COOKIE` first and the private
local file second. The environment variable is the temporary override. Never
print the cookie or place it in a note, work directory, repository file, command
argument, or agent message. The manifest records only whether a cookie was
configured.

An empty anonymous subtitle response does not prove that a video has no official
or AI subtitle track. Before choosing OCR or ASR, retry after `auth-check` reports
the saved or temporary Bilibili cookie as ready; otherwise record the
authentication limitation in the separate processing log.

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

Before accepting an official or AI subtitle, compare its opening lines with the
opening audio/frames and the verified video title. If the content is clearly
unrelated rather than merely imperfect, reject that corrupted upstream track and
prepare the media explicitly:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" prepare \
  "BILIBILI_URL" --output "WORKDIR" --ignore-official-subtitle
```

The URL's `?p=N` selects that part automatically; an explicit `--page N`
overrides it. Use `--ignore-official-subtitle` only after this bounded QA proves a
content mismatch. Record the rejected track and fallback in the separate
processing log; it is not permission to prefer ASR over a usable higher-priority
subtitle.

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
  --confirm-external-upload \
  --language auto --glossary "TERM1,TERM2"
```

`--language auto` first uses Faster Whisper `tiny` only for spoken-language
detection. It routes detected Chinese to Qwen3-ASR-1.7B with FSMN-VAD chunks of
at most 60 seconds, and routes English or another detected language to Faster
Whisper `large-v3`. Detection below 0.65 confidence stops and asks for an explicit
language instead of silently choosing the wrong model.

After automatic detection, inspect `manifest.json` and listen to the opening
audio. Slide text is only a clue because slides and narration may use different
languages. If the language is already known, pass `--language zh` or
`--language en` to skip detection. For code-switched audio, choose the dominant
spoken language and record the limitation in the separate processing log. Build
the glossary after this check; Qwen receives it as context and Faster Whisper as
its initial prompt.

The command reuses a named active session, installs only the packages required by
an explicit language (or both sets for `auto`), uploads only the audio and a
non-secret job manifest, downloads timestamped JSON, and stops a session it
created. Qwen timestamps are the enclosing FSMN-VAD chunk boundaries, not word
alignment. Add `--keep-colab-session` only when more videos will be processed
immediately.

Pass `--confirm-external-upload` only after the task preflight choice above. That
choice is sufficient for the current video, so do not interrupt the workflow to
ask again immediately before upload. Colab OAuth setup does not itself count as
this per-video confirmation.

Use local CPU/CUDA only when Colab is unavailable or the user asks to keep audio
local. English keeps the existing Faster Whisper path:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" transcribe "WORKDIR" \
  --backend local --model small --bootstrap-asr --language en \
  --glossary "TERM1,TERM2"
```

Chinese Qwen transcription requires either Colab or a working local CUDA GPU:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" transcribe "WORKDIR" \
  --backend local --device cuda --bootstrap-asr --language zh \
  --glossary "TERM1,TERM2"
```

The English path reuses a cached Faster Whisper environment and model, uses CPU
`int8`, VAD, timestamps, and the video title plus glossary as an initial prompt.
`small` is the local speed/quality default; use `medium` only when the content is
terminology-heavy or the first pass fails a sample QA check. Do not silently
fall back to CPU Faster Whisper for Chinese when Qwen cannot run; report the
missing CUDA/Colab capability.

Build the glossary from the title, description, slide text, speaker names, and
domain terms before transcription. This materially reduces Chinese homophone
errors.

### 3. Transcript QA

Before summarizing:

1. Inspect `manifest.json` and `transcript.md`.
2. Cross-check at least the opening, one middle section, and the ending.
3. Correct proper nouns, quantities, units, negations, and conclusion wording.
4. Keep uncertainty explicit. Do not silently turn OCR/ASR guesses into facts.
5. Only then derive the summary and timeline, and turn the whole transcript into
   the complete polished note.

For a transcript too large to review in one pass, process chronological chunks
with overlapping boundary context. Preserve each chunk's timestamps, then merge
and deduplicate the chunk notes. Do not write a whole-video conclusion until all
chunks have been reviewed.

### 4. Write the Obsidian note

Read [references/note-spec.md](references/note-spec.md) and follow its YAML,
timeline, complete-note section, distinction between video claims and external
additions, English tags, and separate processing-log requirements.

The `完整笔记` section comes immediately after `时间线`. It is not another
summary: rewrite the entire transcript in chronological, readable prose while
preserving every substantive claim, example, condition, transition, caveat, and
conclusion. Remove only semantically empty fillers, stutters, false starts, and
exact repetitions. Repair punctuation, paragraph boundaries, and obvious
references, but do not shorten the argument or add claims that were not spoken.
For non-Chinese audio, produce a faithful Chinese rendering and retain important
technical terms in the source language on first use. If the transcript is
partial, say so explicitly instead of presenting the section as complete.

Do not put processing history in the final note. Maintain one
`processing.log` beside the notes in the output directory and append one
dated entry per video or part. Record the source path, engine/model, QA samples,
authentication limitations, external upload, failures, fallbacks, and unresolved
transcription uncertainty there. Keep reader-facing content limitations in
`局限与待核实项`; keep implementation and extraction details only in the log.

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
- Report method failures and fallbacks in the separate `processing.log`.
- If a high-risk claim cannot be verified, label it `未核实`; do not fill gaps
  with plausible-sounding explanations.

## Common failures

- Expired or interrupted CDN URLs: `prepare` automatically retries, resumes, and
  refreshes playback information.
- Stylized Chinese hard subtitles: adjust the crop, then use generated contact
  sheets if OCR remains poor.
- Chinese ASR names or homophones: add a glossary and rerun Qwen so the title and
  terms are supplied as context; verify the term-review report afterward.
- Missing Chinese Tesseract data: `--bootstrap-ocr` downloads only the Chinese
  fast model into the skill cache; it does not overwrite system packages.
- Highly stylized subtitles: use `--ocr rapidocr --bootstrap-ocr`, then fall
  back to bounded contact sheets if recognition remains poor.
- Missing Faster Whisper/Qwen dependencies or proxy SOCKS support:
  `--bootstrap-asr` installs the language-specific set into the skill cache.
- Colab is unauthenticated or unavailable: run `colab --auth=oauth2 whoami`, then
  `auth-check --service colab`; read [references/setup.md](references/setup.md)
  when consent must be refreshed. Do not silently fall back to a multi-hour local
  CPU job. If OAuth reports that Google returned a narrower scope, retry once with
  `OAUTHLIB_RELAX_TOKEN_SCOPE=1`; the skill applies this compatibility setting to
  its own Colab subprocesses.
