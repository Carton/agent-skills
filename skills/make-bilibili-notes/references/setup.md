# One-time setup and credential preflight

Read this reference when `doctor` reports a missing tool, when authenticated
Bilibili subtitles are desired, or before selecting the Colab backend. Keep
configuration separate from a video work directory.

## Safety contract

- `doctor` inspects local tools and caches. It does not validate accounts.
- `auth-check` validates only the selected account path and emits redacted JSON.
- `auth-save --service bilibili` is the supported persistent-cookie path for a
  trusted personal machine. It writes outside the repository with private
  permissions.
- Account login, OAuth consent, and external audio upload require the user's
  explicit participation.
- Never paste a cookie or token into `SKILL.md`, a note, a work directory, a
  repository file, a command-line argument, or an agent message.

## Per-task Colab choice

Account setup is reusable, but upload authorization belongs to the current
video. During task preflight, ask once in the user's language:

> If subtitles are unavailable, may I use your Google Colab runtime for ASR?
> This sends the normalized WAV, a non-secret job manifest, and the bundled
> transcription worker to Colab, then removes the remote job files. Choose
> **Colab for this video** or **keep audio local**.

When the user chooses Colab, validate the account immediately and retain that
choice in the current task context. The eventual command must include
`--confirm-external-upload`; the flag makes the non-interactive CLI path explicit
and prevents a second conversational prompt. If the user runs the command
directly, adding the flag is their confirmation for that invocation.

Do not persist this per-video decision in `AGENTS.md`, global configuration, or
the skill. If the user declines, select local ASR or stop before a potentially
long CPU job.

## Optional Bilibili login

Anonymous access remains supported, but Bilibili may hide official or AI
subtitle tracks unless the request carries a logged-in browser cookie. On a
trusted personal machine, the skill can persist that cookie locally so later
runs do not require another copy-and-paste until the cookie expires.

1. Sign in to Bilibili in a browser and obtain the `Cookie` request-header value
   from that authenticated session. Browser UI details vary; do not install an
   untrusted cookie-export extension.
2. Save it interactively. The prompt does not echo the pasted value:

   ```bash
   python3 "$SKILL_DIR/scripts/bili_video.py" auth-save --service bilibili
   unset BILIBILI_COOKIE
   python3 "$SKILL_DIR/scripts/bili_video.py" auth-check --service bilibili
   ```

   If `BILIBILI_COOKIE` is already exported in that shell, `auth-save` stores it
   without prompting. Otherwise paste it only at the hidden prompt.

3. The file is stored at
   `~/.config/make-bilibili-notes/bilibili-cookie`. The script sets its parent
   directory to mode `700` and the file to mode `600`, rejects symlinks or
   broader permissions, and prefers a temporary `BILIBILI_COOKIE` environment
   override when one is present.

4. A `ready` result means the cookie currently represents a logged-in session.
   `invalid` means it should be refreshed by running `auth-save` again.
   `unreachable` means authentication could not be distinguished from a network
   failure.

5. Remove the saved credential when it is no longer wanted:

   ```bash
   python3 "$SKILL_DIR/scripts/bili_video.py" auth-clear --service bilibili
   unset BILIBILI_COOKIE
   ```

Cookies can grant account access. Use this file mode only on a trusted personal
machine; it is plaintext protected by filesystem permissions. Do not copy it to
cloud-synced folders, shell startup files, or a project `.env`. Revoke browser
sessions from Bilibili account security settings if the value may have leaked.

## Google Colab OAuth2

The skill uses the official
[Google Colab CLI](https://github.com/googlecolab/google-colab-cli) with the
`oauth2` provider. Install or update it first:

```bash
uv tool install google-colab-cli
colab update --install
```

Complete the browser/copy-paste consent flow without allocating a GPU, then run
the redacted skill check:

```bash
colab --auth=oauth2 whoami
python3 "$SKILL_DIR/scripts/bili_video.py" auth-check --service colab
```

For an existing Application Default Credentials setup, validate the same path
with `auth-check --service colab --colab-auth adc`.

The CLI caches the OAuth2 refresh token at
`~/.config/colab-cli/token.json`. The skill never copies that file into its cache
or a work directory. Current Colab CLI authentication design and required scopes
are documented in Google's
[authentication provider notes](https://github.com/googlecolab/google-colab-cli/blob/main/docs/04_automation_and_utility.md#authentication-strategies-cli-backend).

### Refresh consent or change accounts

Use a recoverable move instead of deleting the existing token, then repeat the
consent flow:

```bash
mv ~/.config/colab-cli/token.json \
  ~/.config/colab-cli/token.json.backup
colab --auth=oauth2 whoami
python3 "$SKILL_DIR/scripts/bili_video.py" auth-check --service colab
```

After validation, remove the backup only when it is no longer needed. To revoke
the grant server-side, remove the Colab CLI connection from
[Google Account connections](https://myaccount.google.com/connections), move the
local token aside, and authenticate again.

An optional end-to-end smoke test allocates and immediately releases a Colab
runtime, so run it only with the user's approval:

```bash
colab --auth=oauth2 new -s bili-asr-setup --gpu T4
colab --auth=oauth2 status -s bili-asr-setup
colab --auth=oauth2 stop -s bili-asr-setup
```

## OAuth consent and per-task confirmation

OAuth authorizes the CLI to manage Colab sessions. It does not authorize an
agent to send a specific video's audio to Google. Obtain the informed choice once
during task preflight, then pass `--confirm-external-upload` when the Colab path
is actually needed. Do not ask again for the same task. If approval is declined,
keep the audio local or stop; do not silently switch to a multi-hour CPU
transcription.
