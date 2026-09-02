# On-time CI trigger (external cron service)

## Why an external cron site

- GitHub's free-tier `schedule` cron is unreliable: on 2026-09-01 the
  `0 */12 * * *` slots actually started at **02:27 UTC** (00:00 slot) and
  **15:42 UTC** (12:00 slot) — 2.5–3.7 h of scheduler lag, unfixable on
  the free tier.
- A local timer (systemd/crontab on the maintainer's machine) was
  evaluated and rejected: **the box is not 24/7**, so 00:00/12:00 slots
  would be silently missed whenever the machine is off.

So the trigger lives on a third-party cron service that runs independently
of both GitHub's lazy scheduler and any personal machine. `workflow_dispatch`
runs start within ~1 minute of the API call, so builds land on the minute.
The workflow itself has **no `schedule:` block** — keeping both would
double-build ~3 h after every on-time dispatch.

## The call the cron site makes

```http
POST https://api.github.com/repos/sunnyyangyangyang/ninfer-feedstock/actions/workflows/continuous-build.yml/dispatches
Authorization: Bearer <PAT>
Accept: application/vnd.github+json
Content-Type: application/json

{"ref": "main"}
```

Response `204 No Content` = the Actions run was accepted (and starts
within ~1 minute on the free tier).

## Setup: cron-job.org (free plan: 3 jobs, 1-minute resolution)

1. **Create a minimal token.** github.com → Settings → Developer settings
   → Personal access tokens → **Tokens (classic)** → Generate new token.
   Check **only `workflow`** (it can trigger workflow dispatches and
   nothing else — no code, no secrets, no repo reads).
2. **Create the job** on cron-job.org (New Job → cURL / REST):
   - URL: `https://api.github.com/repos/sunnyyangyangyang/ninfer-feedstock/actions/workflows/continuous-build.yml/dispatches`
   - Method: `POST`
   - Body (raw): `{"ref":"main"}`
   - Headers:
     - `Authorization: Bearer <paste the PAT from step 1>`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - Schedule: `0 */12 * * *`
   - Timezone: **UTC** (do not let it default to your local TZ)
3. The free plan emails you after every run (success/failure) — that email
   is your build notification; a failed run means the dispatch itself
   failed (bad token / API outage), not the build.

### If the token ever needs rotating
Replace the header in the cron job; GitHub classic tokens can be revoked
from Settings → Developer settings → Tokens (classic).

## Alternative (no third-party site): Cloudflare Workers cron trigger

A ~10-line Worker with a `cron` export (e.g. `"0 0,12 * * *"` UTC) doing
`fetch` of the same endpoint, with the PAT stored as a Worker secret.
Costs a Cloudflare account + worker deploy; otherwise identical semantics
and no request ever touches a cron-site operator.

## Failure semantics

- **Cron site down / machine off is irrelevant** — the service is
  independent of both.
- **Dispatch accepted but runner pool slow**: the run may still queue a
  few minutes on the free tier (observed ~1 min; that is the residual
  latency this design cannot eliminate without a self-hosted runner).
- **Manual run** anytime: `gh workflow run continuous-build.yml`
  (same endpoint the cron site hits).
