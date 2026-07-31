# Audio transcription backends

Read this reference only after official and hard subtitles have been ruled out.

## Selection

| Situation | Backend | Suggested model |
|---|---|---|
| WSL or laptop without a fast NVIDIA GPU | Google Colab CLI | `large-v3` |
| Local NVIDIA GPU with working CUDA | Local | `large-v3` |
| CPU-only and short/non-technical audio | Local | `small` |
| Audio must not leave the machine | Local | `small` or `medium` |

Colab is an ephemeral batch executor, not a permanent API service. GPU
availability depends on the user's Colab plan, quota, and current capacity.

## One-time Colab setup

Install the official Linux CLI in WSL:

```bash
uv tool install google-colab-cli
colab --auth=oauth2 new -s bili-asr-setup --gpu T4
colab --auth=oauth2 status -s bili-asr-setup
colab --auth=oauth2 stop -s bili-asr-setup
```

The first OAuth2 command may open a browser. Never copy authentication tokens,
session metadata, or Bilibili cookies into a work directory or note.

## Session lifecycle

The `transcribe --backend colab` command uses this lifecycle:

1. Reuse `--colab-session` when it already exists.
2. Otherwise create the requested GPU session.
3. Upload the normalized WAV and a non-secret JSON job manifest.
4. Install the pinned Faster Whisper package in the remote runtime.
5. Execute the bundled worker and download its timestamped JSON.
6. Remove remote job files.
7. Stop only the session created by this invocation, unless
   `--keep-colab-session` was passed.

Use `--keep-colab-session` for an immediate batch so package and model caches are
reused. Stop it explicitly after the batch:

```bash
colab --auth=oauth2 stop -s bili-asr
```

## Quality controls

- Build a glossary before ASR; include people, products, acronyms, and domain
  terms from verified metadata or visible slides.
- Start with `large-v3` on remote GPU for terminology-heavy Chinese content.
- Cross-check the opening, a middle section, and the ending against audio/video.
- Review proper nouns, numbers, units, negations, and conclusion wording.
- Record backend, model, GPU request, and unresolved errors in the method log.

If remote execution fails, report the Colab failure. Do not automatically start
a potentially multi-hour CPU transcription without the user's knowledge.
