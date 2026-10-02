---
name: capture-cli-bearer-token
description: Use when you need to extract an API key / bearer token from a third-party CLI tool (muse code, internal Meta tools, corporate CLIs, "agent"-style TUI products) that does not surface the key in its UI but does send it as an Authorization Bearer header on its API calls. Triggers on "get api key from muse", "extract token from CLI", "no UI for API key", "capture bearer token", "internal tool API key", "redirect CLI to local listener", "use --base-url to capture auth", "muse code api key", "Meta API key from muse". Sets up a local plaintext-HTTP listener, redirects the CLI base URL to it via the CLI own --base-url flag, captures the Authorization header in plaintext, then cleans up. Works when HTTPS-proxy interception is blocked (rustls/openssl cert pinning, sudo required for system-CA install) but the CLI accepts an http:// base-url override. Does NOT work if the CLI pins its base URL to https://, refuses http://, or strips the auth header before sending.
---

# Capture CLI Bearer Token via Base-URL Override

Single-shot trick for getting an API key out of a third-party CLI that hides it
from its UI but sends it on the wire.

## When to use

The CLI:
- Holds an API key / OAuth token internally (often in macOS Keychain or
  `~/.config/<cli>/auth.json` with `storage: "keychain"`).
- Refuses to print the key. `muse auth` is write-only — the entire interface is
  `muse auth set --provider <PROVIDER> --api-key-stdin`, with no `get`/`show`,
  so there is no supported way to read it back.
- Sends it as `Authorization: Bearer <token>` to a known API host.
- Exposes a `--base-url <URL>` flag (or equivalent) to override the API host.
- Accepts an `http://` URL (not all binaries do — see pitfalls).

Typical trigger: Meta's `muse code` (and similar `tbh`-style internal CLIs).
Its real API base is `https://api.meta.ai/v1`, so the default capture target is
`http://127.0.0.1:<port>` overriding that base — nothing else needs changing.
Also useful when an HTTPS-mitmproxy approach fails because the binary uses
rustls with a hardcoded webpki-roots bundle (ignores `SSL_CERT_FILE`).

## Why this works (one sentence)

TLS interception needs the target to trust the proxy CA, but pointing the CLI
at `http://127.0.0.1:<port>` via `--base-url` switches it to plaintext HTTP —
no TLS, no cert, the `Authorization` header arrives in the clear.

## Workflow

Commands below assume your working directory is the skill's own directory
(the one holding this `SKILL.md`), so `scripts/capture_listener.py` resolves
wherever you cloned it. If you invoke it from elsewhere, use the absolute path.

1. **Pick a free port.** Avoid anything already in use (`lsof -nP -iTCP:9999`).

2. **Start the capture listener in the background.**
   ```sh
   python3 scripts/capture_listener.py \
       --port 9999 \
       --log /tmp/captured.txt &
   ```
   The script truncates the log on start and logs every request's headers,
   then returns a stub response so the CLI can continue.

3. **Run the CLI with `--base-url` pointing at the listener.**
   ```sh
   muse exec --provider meta --reasoning-effort minimal \
       --base-url http://127.0.0.1:9999 "ping"
   ```
   **You do not need to wait for the run to finish.** With `muse` the token is
   captured on the *first* request, a model-catalog `GET /muse-code/models`,
   which fires before any prompt is sent. Read the log and kill the CLI as
   soon as the `authorization` line appears.
   Common variations:
   - `--reasoning-effort minimal` — keep token spend low; you're capturing,
     not training a model.
   - If the CLI takes a config-file base URL instead of a flag, edit a copy
     of its config (skill protocol: copy → edit → restore).
   - If it has no `--base-url` flag, check env vars (`*_BASE_URL`,
     `*_API_BASE_URL`) — many CLIs honor those.

4. **Read the captured Authorization — then kill the CLI.**
   ```sh
   grep -i "^  authorization:" /tmp/captured.txt | head -1
   ```
   The log records the request line (`=== GET /muse-code/models ===`) and
   two-space-indented headers, so match the leading whitespace.
   Token shapes seen in the wild:
   - `Bearer LLM|<numeric id>|<opaque secret>` — Meta `muse` / `tbh` family
   - `Bearer sk-...` — OpenAI-style
   - `Bearer EAAB...` — short-lived OAuth bearer (likely to expire in ~1h)
   - `Bearer <jwt>` — JWT (decode the middle segment for claims/exp)

   ⚠️ The captured token also appears on the subsequent `POST /responses`, so
   a `head -1` is enough — don't dump the whole log.

5. **Stop muse early.** Do not wait for it to exit:
   `muse` sends `accept: text/event-stream` and the listener's stub is not a
   valid event stream for it, so it retries with exponential backoff
   (`retrying meta model stream in 1000ms (attempt 2/10)`) and will keep
   going. That is expected and harmless — the token is already captured.
   ```sh
   pkill -f "muse exec"; pkill -f capture_listener.py
   ```

6. **Smoke-test the token against the real API** before trusting it.
   ```sh
   TOKEN='...paste here...'
   curl -sS -H "Authorization: Bearer $TOKEN" https://api.meta.ai/v1/models | head
   ```
   A 401 means the captured header was malformed or the token is already dead;
   a 200 with a model list means it works. Any other status (403/404) usually
   means the path is wrong, not the token — try `/v1/responses` with a
   one-token `max_tokens` before concluding the token is bad.
   For `muse` the model catalog actually lives at `/muse-code/models` (and its
   chat endpoint is `POST /responses`, model `muse-spark-1.3`), so a 404 from
   the smoke test above is not proof the token is bad — test against
   `/muse-code/models` too.

7. **Scrub the capture file.**
   ```sh
   chmod 600 /tmp/captured.txt && rm /tmp/captured.txt
   ```
   The capture file contains the raw token — treat it like a password.

## Pitfalls (in order of likelihood)

- **CLI rejects `http://` base URL** with "base URL must use TLS" / similar.
  → Some binaries refuse non-TLS even when the override flag accepts it.
  Test once; if it refuses, fall back to HTTPS-mitmproxy with `sudo` CA
  install (which this skill avoids because most users can't sudo non-interactively).
- **CLI accepts the override but the request body or headers leak nothing.**
  → Check: the request may be signed/HMAC'd and the signature won't validate
  on your listener. Look for a `--dry-run` or `--no-stream` mode; some CLIs
  have a separate "verify credentials" subcommand.
- **Token is short-lived OAuth bearer, not an API key.** Decoded JWT exp
  claim in the middle segment will tell you. If it's < 1 day, you probably
  want the OAuth refresh token instead (different endpoint, different flow).
- **Token rotates per request** (signature-based auth). You'll capture a
  one-shot signature, not a reusable key. Look for static keys in the
  process memory via `lldb -p <pid>` instead — see `lldb` for that pattern.
- **The log stores request bodies.** Older versions wrote `body[0:500]`, which
  for an agent CLI means a slice of the system prompt — full of workspace
  paths, secrets, and source. The listener now writes only `body-bytes`, but
  if you have an old copy of this script, patch it or scrub aggressively.

## Cleanup checklist

- [ ] `pkill -f capture_listener.py`
- [ ] `pkill -f "muse exec"` — muse retries against the stub and will not exit
      on its own
- [ ] `chmod 600 /tmp/captured.txt` (or wherever you wrote it)
- [ ] `rm /tmp/captured.txt`
- [ ] If you installed a proxy CA anywhere: `security delete-certificate -c "<name>"` (macOS keychain)
- [ ] Restore any config file you temporarily edited for the base URL

## Why the HTTPS-proxy approach is *not* preferred

For completeness — mitmproxy/Charles/Proxyman-style HTTPS interception was
tried first and is more general but blocked here:
- `rustls` with hardcoded `webpki-roots` ignores `SSL_CERT_FILE`.
- Installing the proxy CA to the System keychain needs `sudo`
  (`/Library/Keychains/System.keychain`), which a non-interactive shell
  can't obtain.
- The login keychain doesn't satisfy apps using `rustls-native-certs`.
- Result: connection fails with "transport error", no headers captured.

The base-url override sidesteps all of that by removing TLS from the path.

## End-to-end verification (run this before handing the skill over)

The listener alone is easy to smoke-test, but it does not prove the CLI accepts
an `http://` override. Do the real thing, with the token masked in the output:

```sh
# Run from this skill's directory, or set SKILL_ROOT to where you cloned it.
SKILL_ROOT="${SKILL_ROOT:-$PWD}"
rm -f /tmp/verify.txt
python3 "$SKILL_ROOT/scripts/capture_listener.py" \
    --port 9977 --log /tmp/verify.txt >/dev/null 2>&1 &
LPID=$!; sleep 1

muse exec --provider meta --reasoning-effort minimal \
    --base-url http://127.0.0.1:9977 "say ok" >/dev/null 2>&1 &
MPID=$!

# muse captures on its FIRST request; it then retries the stub stream, so
# stop as soon as the log has an authorization header.
for i in $(seq 1 15); do
    grep -qi "^  authorization:" /tmp/verify.txt 2>/dev/null && break
    sleep 1
done
kill -9 $MPID 2>/dev/null; kill -9 $LPID 2>/dev/null
pkill -f capture_listener.py 2>/dev/null

sed -E 's/(Bearer LLM\|[0-9]+\|)[A-Za-z0-9_-]+/\1<REDACTED>/' /tmp/verify.txt
chmod 600 /tmp/verify.txt && rm -f /tmp/verify.txt
```

Expected output — a `GET /muse-code/models` request line, then the auth header:

```
=== GET /muse-code/models ===
  authorization: Bearer LLM|1234567890|<REDACTED>
  x-client-id: tbh:exec
  user-agent: muse-build/<version> (non-interactive; macos-aarch64; build <sha>)
  body-bytes: 0
```

If you see that header, the technique works and the captured value is a real
`muse` token. `muse` will then keep retrying the stub SSE stream
(`retrying meta model stream in 1000ms …`) — that is expected and harmless,
and is why the loop above breaks on the capture instead of waiting for exit.


## Files in this skill

- `SKILL.md` — this file
- `scripts/capture_listener.py` — the local HTTP listener that captures headers