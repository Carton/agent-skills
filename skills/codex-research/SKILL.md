---
name: codex-research
description: Delegate web search and research to the local Codex CLI (gpt-5.6-luna, server-side web search). Use when the built-in WebSearch tool is unavailable or fails with 429 / "Limit Exhausted" quota errors, and for deep research tasks needing current online information — technology comparisons, finding community recommendations, surveys, fact-checking with sources. Not for reading a known URL (use WebFetch or defuddle instead).
---

# Codex Research (gpt-5.6-luna)

Runs the local Codex CLI non-interactively with the `gpt-5.6-luna` model at medium reasoning and server-side web search enabled (`-c tools.web_search=true`). Luna runs its own multi-query searches, reads pages, and returns a synthesized answer with sources — a full research pass, not a raw link list.

Each invocation costs ~10–20k tokens on the ChatGPT/Codex plan (negligible at luna/medium) and takes 30–120 s. For a quick single-fact lookup, built-in WebSearch is fine **when it works**; use this skill whenever WebSearch returns 429 "Limit Exhausted", and for any research-grade question.

The question passed to codex must be **fully self-contained** — codex has no access to this conversation. Always ask for source URLs in the answer.

## Command

Works the same on the Windows host (npm-global codex; Git Bash converts the `/tmp` path automatically) and inside WSL sessions (the PATH line covers nvm-only installs where codex is not on the default PATH):

```bash
command -v codex >/dev/null || export PATH="$(dirname "$(find "$HOME/.nvm" -name codex -type f 2>/dev/null | head -1)"):$PATH"
codex exec -m gpt-5.6-luna -c model_reasoning_effort=medium -c tools.web_search=true \
  --skip-git-repo-check -o /tmp/codex_research.md "self-contained research question here, in the user's language, ask for source URLs" 2>/dev/null
cat /tmp/codex_research.md
```

## Notes

- Set the Bash tool timeout to **300000 ms or more** — a research pass regularly exceeds 120 s.
- `-o` writes only the final answer to the file; if the file is missing or empty, rerun with stderr visible (drop `2>/dev/null`) to see the error.
- Relaying: `/tmp/codex_research.md` is the research result (markdown with sources). Summarize or quote it for the user; for high-stakes claims, verify the cited URLs yourself with WebFetch.
- Use `-c model_reasoning_effort=high` only for genuinely hard surveys; medium is enough for almost everything.

## Troubleshooting

- `'luna' model is not supported` — the model id must be exactly `gpt-5.6-luna` (bare `luna` is rejected on ChatGPT accounts).
- Auth/401 errors — run `codex login` interactively, then retry.
- `codex: command not found` — the find-based PATH export above handles nvm layouts; otherwise install with `npm i -g @openai/codex`.
