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

Read [setup.md](setup.md) first. Authentication and external audio upload are
separate approvals: validate OAuth before the task, then obtain explicit user
approval before uploading that task's audio.

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

## Why Faster Whisper is the current baseline

Faster Whisper is used here for engineering maturity rather than a claim that it
has the best Chinese character error rate. It provides one lightweight local and
Colab implementation, stable segment timestamps, VAD, glossary prompting, and a
well-understood T4 memory profile. Use `large-v3` for Chinese Colab work; `small`
is a speed probe and can corrupt idioms or domain terms.

Chinese-focused alternatives are worth benchmarking on representative clips:

- FunASR `paraformer-zh` provides Chinese/English recognition, timestamps, and
  hotwords with a much smaller model, but its PyTorch/ModelScope dependency set
  can restart a live Colab CLI kernel during installation.
- Qwen3-ASR supports Chinese dialects and strong long-audio recognition. Its ASR
  model does not by itself provide the timestamped segments required by this
  skill; the official timestamp path also loads Qwen3-ForcedAligner.

Do not add or select either backend solely from published benchmark tables.
First verify install stability, timestamp normalization, cleanup, and transcript
quality on the same audio sample. Until then, label it as an unvalidated
alternative rather than silently changing the source pipeline.
