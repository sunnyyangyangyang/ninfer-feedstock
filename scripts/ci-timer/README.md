# On-time CI trigger (systemd user timer)

## Why this exists

GitHub's free-tier `schedule` cron is unreliable: on 2026-09-01 the
`0 */12 * * *` slots actually started at **02:27 UTC** (for the 00:00 slot)
and **15:42 UTC** (for the 12:00 slot) — 2.5–3.7 h of scheduler lag, with
no way to fix it on the free tier. `workflow_dispatch` runs, by contrast,
start within ~1 minute.

So the on-time trigger lives **here, on the maintainer's machine**: a
systemd user timer fires `gh workflow run continuous-build.yml` at
00:00:00 and 12:00:00 UTC sharp. The workflow itself deliberately has no
`schedule:` block — keeping both would double-build ~3 h after every
on-time dispatch.

## Install (one line, run in a normal host terminal)

```bash
cd <this feedstock checkout>
install -Dm644 scripts/ci-timer/ninfer-ci-dispatch.service scripts/ci-timer/ninfer-ci-dispatch.timer ~/.config/systemd/user/ \
  && systemctl --user daemon-reload \
  && systemctl --user enable --now ninfer-ci-dispatch.timer \
  && systemctl --user list-timers --all | grep ninfer
```

Requires: `gh` installed and authenticated (`gh auth status`), and the
machine running at the trigger times (it stays on 24/7, so: fine).

## Semantics

- **On time to ~1 minute**: timer fires at :00:00 UTC (AccuracySec=1s),
  `gh workflow run` takes seconds, the Actions run starts ~1 min later.
- **Machine asleep/off at a slot**: `Persistent=true` fires one catch-up
  dispatch on next boot instead of silently skipping (the built timestamp
  reflects the actual build time, so versions stay truthful).
- **Disable temporarily**: `systemctl --user disable --now ninfer-ci-dispatch.timer`
  (manual `gh workflow run continuous-build.yml` still works anytime).

## Notes

- The dispatch uses this machine's `gh` token (repo scope) — the same one
  used for all `gh` commands. No secrets are involved beyond that.
- The build itself still runs on `ubuntu-latest` hosted runners (free
  tier): only the *trigger* is local. A self-hosted runner would remove
  the last ~1 minute of dispatch latency, at the cost of needing CUDA +
  24/7 uptime on this box — not worth it for this cadence.
