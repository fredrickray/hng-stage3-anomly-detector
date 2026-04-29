# HNG Stage 3 - Anomaly / DDoS Detection Engine

This project deploys Nextcloud behind Nginx and runs a custom Python anomaly detection daemon that:
- tails JSON Nginx logs in real time,
- learns baseline traffic behavior from recent data,
- blocks abusive IPs with `iptables`,
- auto-unbans using progressive backoff,
- sends Slack alerts,
- and serves a live metrics dashboard.

## Live Submission Details
- **Server IP:** `<ADD_YOUR_SERVER_IP>`
- **Metrics dashboard URL (domain/subdomain):** `http://<YOUR_METRICS_DOMAIN_OR_SUBDOMAIN>`
- **GitHub repo (public):** `<ADD_REPO_URL>`
- **Blog post URL:** `<ADD_BLOG_POST_URL>`

## Why Python
Python was chosen for fast iteration and readability under time constraints. The standard library plus lightweight packages made it easy to implement:
- streaming log monitoring,
- deque-based time windows,
- threaded workers for baseline and unban loops,
- and a minimal live dashboard.

## Architecture
- `nginx` reverse proxy writes JSON logs to `/var/log/nginx/hng-access.log`
- logs are persisted in Docker named volume `HNG-nginx-logs`
- `detector` container mounts logs read-only and tails continuously
- per-IP anomalies trigger `iptables` DROP and Slack alert
- global anomalies trigger Slack alert only
- dashboard runs on detector service (`:8080`)

Replace `docs/architecture.png` with your real architecture diagram before submission.

## Repository Layout
```text
detector/
  main.py
  monitor.py
  baseline.py
  detector.py
  blocker.py
  unbanner.py
  notifier.py
  dashboard.py
  config.yaml
  requirements.txt
nginx/
  nginx.conf
docs/
  architecture.png
screenshots/
README.md
docker-compose.yml
```

## Sliding Window Logic (Deque)
- Two 60-second deque windows are maintained:
  - **Global window:** one timestamp per request
  - **Per-IP window:** timestamp deque keyed by source IP
- On each request:
  1. append current timestamp,
  2. evict entries older than `now - 60s`,
  3. compute request rate as `len(deque) / 60`.
- This gives true rolling rates, not coarse per-minute counters.

## Rolling Baseline Logic
- Baseline source data is a rolling 30-minute per-second series (`1800` points max).
- Recalculation runs every 60 seconds.
- For each point, detector stores:
  - request count for that second,
  - error ratio for that second.
- Per-hour slots are tracked separately.
- If current hour has enough points (`min_points_for_hourly_slot`), current-hour baseline is preferred; else full rolling 30-minute baseline is used.
- Floor values are applied:
  - `floor_mean`
  - `floor_stddev`
- Effective baseline values are then used by anomaly checks.

## Detection Rules
- **Anomaly condition:** trigger when either:
  - z-score > `3.0`, or
  - current rate > `5x` baseline mean.
- **Error surge tightening:** if an IP error pressure exceeds `3x` baseline error rate, thresholds are tightened automatically (configurable).
- **Per-IP anomaly:** ban + Slack in <=10 seconds (near-immediate in current loop).
- **Global anomaly:** Slack alert only.

## Blocking and Auto-Unban
- Blocking uses `iptables -I INPUT -s <ip> -j DROP`.
- Backoff schedule:
  1. 10 minutes
  2. 30 minutes
  3. 2 hours
  4. permanent
- Every unban emits a Slack notification.

## Audit Log Format
Audit entries are written to `detector/audit.log`:
```text
[timestamp] ACTION ip | condition | rate | baseline | duration
```

Includes:
- `BAN`
- `UNBAN`
- `BASELINE`
- `ALERT` (global anomaly)

## Fresh VPS Setup (Ubuntu Example)
1. Install Docker and Compose plugin:
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

2. Clone repo:
```bash
git clone <YOUR_REPO_URL>
cd hng-stage3-anomly-detector
```

3. Configure detector:
```bash
cp detector/config.yaml detector/config.local.yaml
```
Update Slack webhook and any thresholds in `detector/config.yaml`.

4. Start stack:
```bash
docker compose up -d --build
```

5. Verify:
```bash
docker compose ps
docker compose logs -f detector
curl http://<SERVER_IP>/
curl http://<SERVER_IP>:8080/metrics.json
```

## Required Screenshot Checklist
Put these in `screenshots/`:
1. `Tool-running.png`
2. `Ban-slack.png`
3. `Unban-slack.png`
4. `Global-alert-slack.png`
5. `Iptables-banned.png`
6. `Audit-log.png`
7. `Baseline-graph.png` (show at least two hourly slots with different means)

## Notes for Grading
- Keep server online for full 12-hour grading window.
- Keep Nextcloud accessible by server IP.
- Keep dashboard accessible by your submitted domain/subdomain.
- Ensure `HNG-nginx-logs` named volume exists and is mounted correctly.
