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
5. Decide whether a one-line message is allowed. Use a one-line subject only for changes of 10 lines or fewer whose intent and impact are fully obvious; otherwise add a body.

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

## Body Rules

Default to adding a body. A one-line subject is allowed only when all of these are true:

- The diff changes 10 lines or fewer.
- The change is confined to one narrow behavior or artifact.
- The motivation, impact, and validation are obvious from the subject.
- The change does not alter behavior, compatibility, configuration, data shape, or workflow.

Add a body whenever any of these are true:

- The reason for the change is not obvious.
- The change alters behavior, compatibility, configuration, data shape, or workflow.
- There are important validation notes.
- Multiple related changes need a short explanation.

Wrap body lines at roughly 72 characters. Explain why and what changed; avoid restating every file touched.

For breaking changes, include a footer:

```text
BREAKING CHANGE: <impact and migration path>
```

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
