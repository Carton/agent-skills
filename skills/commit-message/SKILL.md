---
name: commit-message
description: Use when creating, reviewing, or suggesting git commit messages, commit subjects, commit bodies, squash commit messages, or Conventional Commits text from staged or unstaged diffs.
---

# Commit Message

## Overview

Create clear, accurate Conventional Commit messages from the actual git diff. The message must describe the change being committed, not the task request in isolation.

## Workflow

1. Inspect the relevant diff before writing the message.
   - Prefer `git diff --cached` for staged changes.
   - Use `git diff` only when the user asks for unstaged changes or no changes are staged.
   - Check `git status --short` to understand whether the working tree contains unrelated edits.
2. Identify the primary user-visible or maintainer-visible change.
3. Choose the Conventional Commit type and optional scope.
4. Write the subject line.
5. Decide whether a body is mandatory before writing the message. Run
   `git diff --numstat`, add additions and deletions, then apply the mandatory
   body gate below.

Do not create or suggest a commit message without reading the diff unless the user explicitly provides the complete diff or exact message content to review.

## Format

Use:

```text
<type>(<scope>): <summary>

<body>
```

Scope is optional. Omit it when there is no clear, short module or area name.

## Types

| Type | Use for |
|------|---------|
| `feat` | New user-facing or API-facing capability |
| `fix` | Bug fix or corrected behavior |
| `perf` | Performance improvement without behavior change |
| `refactor` | Internal restructuring without behavior change |
| `docs` | Documentation-only changes |
| `test` | Test-only changes |
| `build` | Build system, packaging, or dependency changes |
| `ci` | CI workflow or automation changes |
| `chore` | Maintenance that does not fit another type |
| `style` | Formatting-only changes |
| `revert` | Reverting a previous commit |

## Subject Rules

- Write in English.
- Use imperative mood: "add", "fix", "remove", "update".
- Keep the subject at 72 characters or fewer when practical.
- Do not end the subject with a period.
- Be specific about the changed behavior or artifact.
- Do not mention implementation trivia unless that is the committed change.

## Mandatory Body Gate

**A body is required unless every condition below is true:**

- Added lines plus deleted lines is at most 10.
- The diff is one narrow, non-behavioral artifact change.
- The subject alone states both the reason and the impact.

Any behavior, compatibility, configuration, data-shape, API, or workflow
change requires a body regardless of line count. If a body is required, do not
emit or create a one-line commit: write a blank line followed by one or two
sentences explaining why and what changed. Wrap body lines at roughly 72
characters and avoid repeating the file list.

For breaking changes, include a footer:

```text
BREAKING CHANGE: <impact and migration path>
```

## Shell Commit Construction

When creating a commit from a shell, preserve real line breaks in the body.
An ordinary quoted argument such as `-m "first line\\nsecond line"` passes a
literal backslash and `n` to Git in common POSIX shells; it does not create a
new line. For Bash or Zsh, prefer ANSI-C quoting for a multi-line body:

```bash
git commit -m "fix(scope): summary" -m $'First body line\nSecond body line'
```

Alternatively, write the message to a file and pass it with `git commit -F`.
After every commit with a body, verify it with `git show -s --format=%B HEAD`.
If its output contains a literal `\\n`, amend the message before proceeding.

## Examples

```text
feat(api): add workload trend endpoint
fix(sched): avoid stale wakeup state
perf(render): reduce redundant buffer copies
docs(readme): document skill installation flow
test(commit): cover invalid subject types
```

## Common Mistakes

- Writing from the user request instead of the diff.
- Using `chore` when a more precise type applies.
- Adding a broad scope such as `repo` or `misc`.
- Writing a subject that says "update files" or "apply changes".
- Using one-line messages for diffs over 10 lines or for behavior changes that need context.
