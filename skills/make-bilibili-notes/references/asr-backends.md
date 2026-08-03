# Audio transcription backends

Read this reference only after official and hard subtitles have been ruled out.

## Selection

| Situation | Backend | Suggested model |
|---|---|---|
| Chinese, WSL/laptop without a fast NVIDIA GPU | Google Colab CLI | Qwen3-ASR-1.7B + FSMN-VAD |
| English, WSL/laptop without a fast NVIDIA GPU | Google Colab CLI | Faster Whisper `large-v3` |
| Chinese, local NVIDIA GPU with working CUDA | Local | Qwen3-ASR-1.7B + FSMN-VAD |
| English, CPU-only and short/non-technical audio | Local | Faster Whisper `small` |
| Audio must not leave the machine | Local | Chinese requires CUDA; English uses `small` or `medium` |

Colab is an ephemeral batch executor, not a permanent API service. GPU
availability depends on the user's Colab plan, quota, and current capacity.

## One-time Colab setup

Read [setup.md](setup.md) first. Authentication and external audio upload are
separate decisions: validate OAuth during setup, and record the user's informed
Colab choice once during task preflight.

Install the official Linux CLI in WSL:

```bash
uv tool install google-colab-cli
colab update --install
colab --auth=oauth2 whoami
python3 "$SKILL_DIR/scripts/bili_video.py" auth-check --service colab
```

The OAuth2 command prints an authorization URL and asks the user to paste the
returned code. Never copy authentication tokens, session metadata, or Bilibili
cookies into a work directory or note.

If `colab install` or `colab exec` raises `jupyter_kernel_client` missing
`KernelClient`, the PyPI tool resolved the wrong same-named dependency. Replace
it with the source required by the official Colab CLI project, then retry:

```bash
uv pip install \
  --python ~/.local/share/uv/tools/google-colab-cli/bin/python \
  git+https://github.com/googlecolab/jupyter-kernel-client.git
```

## Session lifecycle

After preflight approval, include `--confirm-external-upload`. Without it the
command exits before creating or reusing a session:

```bash
python3 "$SKILL_DIR/scripts/bili_video.py" transcribe "WORKDIR" \
  --backend colab --confirm-external-upload \
  --model large-v3 --language auto
```

The confirmed `transcribe --backend colab` command uses this lifecycle:

1. Reuse `--colab-session` when it already exists.
2. Otherwise create the requested GPU session.
3. Upload the normalized WAV and a non-secret JSON job manifest.
4. Install the pinned package set needed by the requested language. `auto`
   installs the lightweight detector plus both possible ASR engines.
5. Detect spoken language when requested, execute the selected engine, and
   download timestamped JSON.
6. Remove remote job files.
7. Stop only the session created by this invocation, unless
   `--keep-colab-session` was passed.

Use `--keep-colab-session` for an immediate batch so package and model caches are
reused. Stop it explicitly after the batch:

```bash
colab --auth=oauth2 stop -s bili-asr
```

## Quality controls

- Use `--language auto` when the spoken language is genuinely unknown. It runs a
  Faster Whisper `tiny` probe and stops below 0.65 confidence.
- Use `--language zh` or `--language en` when listening or reliable metadata has
  already established the narration language; this avoids a detector download
  and makes routing deterministic.
- Build a glossary before ASR; include people, products, acronyms, and domain
  terms from verified metadata or visible slides.
- Chinese uses Qwen3-ASR-1.7B with `funasr/fsmn-vad`; VAD regions are packed into
  at most 60-second chunks and processed in batches of two on T4.
- English and other non-Chinese languages use Faster Whisper. Start with
  `large-v3` on remote GPU and `small` for a local CPU speed pass.
- Cross-check the opening, a middle section, and the ending against audio/video.
- Review proper nouns, numbers, units, negations, and conclusion wording.
- Record requested/detected language, confidence, engine, model, GPU request,
  VAD chunking, and unresolved errors in the separate `processing.log`, not
  in the reader-facing note.

If remote execution fails, report the Colab failure. Do not automatically start
a potentially multi-hour CPU transcription without the user's knowledge.

## Why the defaults differ by language

The 2026-08-02 Colab T4 test used the same 1205.04-second FLEURS Mandarin WAV
for all Chinese candidates. Qwen3-ASR-1.7B + FSMN-VAD reached 8.16% CER and a
93.1-second warm new-audio estimate. Fun-ASR-Nano reached 8.05% CER but needed
147.2 seconds; the four-character first-pass advantage was too small to justify
the slower, less repeatable single-file path. Paraformer reached 10.15% CER in
13.0 seconds, so it remains a future speed mode rather than the note-quality
default.

Faster Whisper remains the English and general multilingual path because of its
mature timestamps, VAD, initial-prompt support, and well-understood local/Colab
behavior. The prior 10-minute Mandarin test gave Faster Whisper `large-v3`
14.09% CER, so it is no longer the Chinese default.

Current Chinese behavior:

- Download Qwen and FSMN-VAD from Hugging Face; do not use the slower ModelScope
  path by default.
- Store one transcript segment per VAD chunk. These start/end values support
  approximate note links but are not word-level alignment.
- Preserve Qwen's context input using the verified video title and glossary.
- If a precise timeline is later required, add Qwen3-ForcedAligner as a separate
  optional pass rather than charging every note for it.

Do not infer that these Mandarin results cover Bilibili music, overlapping
speakers, code-switching, or dialects. Continue the opening/middle/ending QA and
label detection or transcription uncertainty explicitly.
