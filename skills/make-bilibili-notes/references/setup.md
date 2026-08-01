# One-time setup and credential preflight

Read this reference when `doctor` reports a missing tool, when authenticated
Bilibili subtitles are desired, or before selecting the Colab backend. Keep
configuration separate from a video work directory.

## Safety contract

- `doctor` inspects local tools and caches. It does not validate accounts.
- `auth-check` validates only the selected account path and emits redacted JSON.
- Account login, OAuth consent, and external audio upload require the user's
  explicit participation.
- Never paste a cookie or token into `SKILL.md`, a note, a work directory, a
  repository file, a command-line argument, or an agent message.

## Optional Bilibili login

Anonymous access remains supported, but Bilibili may hide official or AI
subtitle tracks unless the request carries a logged-in browser cookie. The skill
does not persist this cookie by design.

1. Sign in to Bilibili in a browser and obtain the `Cookie` request-header value
   from that authenticated session. Browser UI details vary; do not install an
   untrusted cookie-export extension.
2. Prefer a password manager or credential helper. For a temporary interactive
   shell session, read the value without echoing it, export it, and clear it when
   finished:

   ```bash
   read -r -s BILIBILI_COOKIE
   export BILIBILI_COOKIE
   python3 "$SKILL_DIR/scripts/bili_video.py" auth-check --service bilibili
   # Run prepare in the same shell, then:
   unset BILIBILI_COOKIE
   ```

3. A `ready` result means the cookie currently represents a logged-in session.
   `invalid` means it should be refreshed. `unreachable` means authentication
   could not be distinguished from a network failure.

Cookies can grant account access. Do not place one in shell startup files or a
project `.env`. Revoke browser sessions from Bilibili account security settings
if the value may have leaked.

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

## OAuth consent is not upload consent

OAuth authorizes the CLI to manage Colab sessions. It does not authorize an
agent to send a user's audio to Google. Before `transcribe --backend colab`, tell
the user that the normalized audio and a non-secret job manifest will be
uploaded, and obtain explicit approval. If approval is declined, keep the audio
local or stop; do not silently switch to a multi-hour CPU transcription.
