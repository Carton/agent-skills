---
name: codex-image
description: Delegate image understanding to the local Codex CLI (model pinned in model.conf next to this skill; currently gpt-6-luna at low reasoning effort). Use when this agent cannot see an image natively — the Read tool returns a CDN URL instead of the picture, the built-in vision MCP fails or is unavailable — and for OCR (transcribing text in screenshots/photos), describing UI screenshots, photos, charts and diagrams, and comparing several images. Attaches 1–5 local image files to a one-shot `codex exec`. Not for generating or editing images.
---

# Codex Image (fast model, low effort)

**Model pin — lives in [`model.conf`](model.conf) next to this file: the ONLY place to touch when a newer model generation ships.** Every command template below starts by sourcing it:

```bash
# ~/.zcode/skills/codex-image/model.conf
MODEL="gpt-6-luna"    # must be a vision-capable model
EFFORT="low"          # reasoning effort: low | medium | high
```

Runs the local Codex CLI non-interactively with the pinned model at the pinned effort, attaching local image files via `-i`. No web access needed — the model reads only the attached images plus the prompt. Handles photos, UI screenshots (including dense Chinese/English text), charts, diagrams, and side-by-side comparison of several images.

Each invocation costs ~5–10k tokens on the ChatGPT/Codex plan and takes 15–60 s. Low effort is enough for describing and OCR; raise `EFFORT` in `model.conf` only when reasoning *over* the image is genuinely hard (dense architecture diagrams, multi-step chart arithmetic).

The prompt must be **fully self-contained** — codex has no access to this conversation. Say what each image is and where it came from when that context matters (e.g. "a screenshot of the app's settings page"), and be explicit about the output you want (description / verbatim transcription / specific question).

## Command

Works the same on the Windows host (npm-global codex) and inside WSL sessions (the PATH line covers nvm-only installs where codex is not on the default PATH):

```bash
source "$HOME/.zcode/skills/codex-image/model.conf"
command -v codex >/dev/null || export PATH="$(dirname "$(find "$HOME/.nvm" -name codex -type f 2>/dev/null | head -1)"):$PATH"
codex exec -m "$MODEL" -c model_reasoning_effort="$EFFORT" \
  --skip-git-repo-check \
  -i "C:/path/to/image1.png" -i "C:/path/to/image2.png" \
  -o /tmp/codex_image.md \
  "self-contained question about the attached image(s), in the user's language; with multiple images refer to them as #1, #2 ... in attachment order" 2>/dev/null
cat /tmp/codex_image.md
```

## Notes

- `-i` is repeatable — attach up to ~5 images per call (more gets slow and blurry in attribution). With several images, number them in the prompt so the answer stays attributable.
- `-i` takes **local file paths only, not URLs**. If all you have is a URL (e.g. the Read tool returned a CDN link instead of the picture), download it first: `curl -sL -o /tmp/img1.png "URL"` and attach `/tmp/img1.png`.
- Prefer absolute Windows-style paths with forward slashes on the Windows host (`C:/Users/.../img.png`); plain POSIX paths (`/c/...`) are auto-converted by Git Bash but the explicit form is less surprising.
- Common raster formats work (tested: PNG, JPEG; WebP generally fine). For huge screenshots (>4 MB) consider downscaling first to save tokens.
- Set the Bash tool timeout to **180000 ms or more** — calls with several images regularly exceed 60 s.
- `-o` writes only the final answer to the file; if the file is missing or empty, rerun with stderr visible (drop `2>/dev/null`) to see the error.
- Relaying: `/tmp/codex_image.md` is the recognition result. Quote it for the user; for high-stakes readings (e.g. transcribing a value you're about to act on), spot-check by asking again or cropping the region.

## Troubleshooting

- `model ... is not supported` — check `model.conf`; the id must be the full model id (e.g. `gpt-6-luna`, not a nickname like `luna`), and it must be vision-capable. Update `model.conf` when a new generation ships — nothing else needs editing.
- Codex answers as if **no image was attached** (generic refusal) — the `-i` path didn't resolve. Use an absolute existing path; on Windows check the file isn't locked by another program.
- `--image` / `-i` flag unknown — the installed codex CLI is too old; update with `npm i -g @openai/codex@latest`.
- Auth/401 errors — run `codex login` interactively, then retry.
- `codex: command not found` — the find-based PATH export above handles nvm layouts; otherwise install with `npm i -g @openai/codex`.
