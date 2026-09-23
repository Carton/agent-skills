---
name: codex-delegate
description: Delegate hard engineering — architecture design and difficult code modifications — to the local Codex CLI running a strong model (pinned at the top of this skill; currently gpt-6-astra at low reasoning effort), while the calling agent keeps doing the light work (codebase research, log analysis, orchestration, verification) and feeds codex only pre-distilled context to save strong-model tokens. Supports resuming previous codex sessions for follow-ups. OPT-IN ONLY. Enable when the user explicitly invokes this skill or asks for this split (e.g. "/codex-delegate", "delegate to codex", "交给 codex 做", "难的部分用 codex"). Never trigger automatically; once the user opts in, keep it active for the rest of the task until they say otherwise.
---

# Codex Delegate (strong model, low effort)

**Model pin — lives in [`model.conf`](model.conf) next to this file: the ONLY place to touch when a newer model generation ships.** Every command template below starts by sourcing it:

```bash
# ~/.zcode/skills/codex-delegate/model.conf
MODEL="gpt-6-astra"   # e.g. later: MODEL="gpt-7-whatever"
EFFORT="low"          # reasoning effort: low | medium | high
```

Once the user has opted in, split the work:

- **You (the calling agent) do the light work**: investigating the codebase, grepping/reading files, analyzing logs and tool output, reproducing issues, running commands/tests, git operations, and distilling the brief for each codex call. Also verify codex's output after every call.
- **Codex (the strong model) does the heavy work**: every important architecture design and every difficult code modification — new module/system design, cross-file refactors, concurrency/async correctness, performance-critical paths, tricky algorithms, subtle bug fixes.

Simple mechanical edits (typos, renames, small localized fixes, config tweaks) do NOT go to codex — just do them. When genuinely unsure whether a change is "hard", delegate.

## Token economy: keep codex's context clean

Every token the strong model reads is the expensive kind — don't make it do the orchestrator's job.

- **Distill, never dump.** Run the greps, read the files, and analyze the logs/tool output locally; the brief contains only conclusions plus the load-bearing evidence: exact file paths, code excerpts limited to the change sites (not whole files), and the few log lines that matter (not raw dumps).
- **Make the brief self-sufficient** and say so: "All context you need is in this brief; do not explore the repo unless something essential is missing." Codex answering from the brief spends hundreds of tokens; codex exploring spends tens of thousands.
- **Repo exploration by codex is the exception**, not the default — only for genuinely repo-wide design questions, and then bound it: "explore only <dirs/files> and nothing else".
- **Trim between calls.** Don't re-paste context codex already has (see session reuse below) — send only the delta.

## Session ledger & reuse

Codex sessions persist in `~/.codex/sessions/` and can be continued:

| Mode | Command | Context | Thread id |
|---|---|---|---|
| Fresh | `codex exec ...` | none | new |
| Resume | `codex exec resume <id> ...` | full history inherited | unchanged |
| Fork | `codex exec fork <id> ...` | full history copied | new (original untouched) |

Capture the thread id of every fresh/forked call from the first `--json` event: `grep -o '"thread_id":"[^"]*"' <events> | head -1`. Append one row per call to the ledger:

```bash
printf '%s\t%s\t%s\t%s\n' "$TID" "$(date '+%F %T')" "$PWD" "one-line scope: what this thread covers" >> /tmp/codex_delegate_ledger.tsv
```

Per call, you decide (check the ledger first — it can make this judgment):

- **Resume** when the new ask continues an existing thread's work: iterating on the same design, follow-up fixes to codex's own change, the next step of the same refactor. The prompt contains only the delta requirements plus any NEW findings — no re-stated context.
- **Fork** when you want the old thread's context but must keep it pristine — e.g. "try a different approach" — then record the new thread id.
- **Fresh** for unrelated tasks, or when a thread's accumulated history is no longer relevant dead weight.

Resuming is also cheap: the re-fed history mostly hits codex's prompt cache (`cached_input_tokens` in the usage event). If the ledger is lost, `codex exec resume --last` picks the most recent session in the cwd.

## Commands

Run from the project root (Bash cwd persists; `cd` there first if needed). Works on the Windows host (npm-global codex; Git Bash converts the `/tmp` path automatically). Use `-c sandbox_mode=` everywhere (resume/fork reject `-s`). Set `MODEL` from the pin at the top of this skill in every shell.

Design consult (fresh) — codex answers from the distilled brief:

```bash
source "$HOME/.zcode/skills/codex-delegate/model.conf"
codex exec -m "$MODEL" -c model_reasoning_effort="$EFFORT" -c sandbox_mode="read-only" \
  --skip-git-repo-check --json -o /tmp/codex_delegate.md \
  "self-contained brief in the user's language: design X; relevant context distilled below (paths + excerpts + constraints); all context you need is in this brief — do not explore the repo; return: architecture, file-by-file plan, key interfaces, trade-offs, risks" \
  >/tmp/codex_delegate_events.jsonl 2>/dev/null
TID=$(grep -o '"thread_id":"[^"]*"' /tmp/codex_delegate_events.jsonl | head -1 | cut -d'"' -f4)
cat /tmp/codex_delegate.md   # then append $TID to the ledger
```

Code modification (fresh) — codex edits the files in the workspace itself:

```bash
source "$HOME/.zcode/skills/codex-delegate/model.conf"
codex exec -m "$MODEL" -c model_reasoning_effort="$EFFORT" -c sandbox_mode="workspace-write" \
  --skip-git-repo-check --json -o /tmp/codex_delegate.md \
  "self-contained brief in the user's language: implement change X; numbered requirements; context excerpts at the change sites below; constraints; do not run destructive commands; when done, summarize what changed and why" \
  >/tmp/codex_delegate_events.jsonl 2>/dev/null
cat /tmp/codex_delegate.md && git diff --stat
```

Resume for follow-ups — same flags, delta-only prompt:

```bash
source "$HOME/.zcode/skills/codex-delegate/model.conf"
codex exec resume "$TID" -m "$MODEL" -c model_reasoning_effort="$EFFORT" -c sandbox_mode="workspace-write" \
  --skip-git-repo-check -o /tmp/codex_delegate.md \
  "delta requirements + new findings only, in the user's language; codex already has the prior context" 2>/dev/null
```

(`fork "$TID"` has identical syntax to `resume`.)

## Rules

1. **Codex cannot see this conversation.** Fresh calls get a fully self-contained brief; resumed calls get the delta plus anything new.
2. **One call per well-scoped unit of work.** Batch related sub-questions into one brief; don't drip-feed.
3. **Always verify a code-modifying call**: read the diff (`git diff`, `git status`), run the project's tests/build/lints. Fix trivial fallout yourself; re-delegate to codex (resume the thread) only if the approach itself is wrong.
4. Set the Bash tool timeout to **600000 ms** — codex routinely takes several minutes.
5. Before a code-modifying call on a dirty tree, commit or stash unrelated changes so codex's diff stays isolated and revertible.
6. Keep the ledger current — every fresh/forked call appends a row; the reuse decision is only as good as the ledger.

## Troubleshooting

- `model ... is not supported` — check `model.conf`; the id must be the full model id (e.g. `gpt-6-astra`, not a nickname). Update `model.conf` when a new generation ships — nothing else needs editing.
- `unexpected argument '-s' found` on resume/fork — use `-c sandbox_mode="read-only"` / `"workspace-write"` instead of `-s`.
- `-o` file missing/empty — rerun with stderr visible (drop `2>/dev/null`; unrelated rmcp/MCP transport ERRORs in stderr are noise).
- Auth/401 errors — run `codex login` interactively, then retry.
- `codex: command not found` — install with `npm i -g @openai/codex`.

## Notes

- Low reasoning effort is intentional: the strong model at low is still the strong model, and low keeps iteration fast. Raise to `-c model_reasoning_effort=medium` only if the user asks.
- You stay the orchestrator and own final quality: you decide what to delegate and whether to resume, write the briefs, and gate every merge of codex's work.
