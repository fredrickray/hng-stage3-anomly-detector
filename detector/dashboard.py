from flask import Flask, jsonify, render_template_string
import psutil


def create_dashboard_app(engine, refresh_seconds: int):
    app = Flask(__name__)

    page = """
<!doctype html>
<html>
  <head>
    <title>HNG Anomaly Detector Dashboard</title>
    <meta http-equiv="refresh" content="{{ refresh_seconds }}">
    <style>
      :root {
        --bg: #07090f;
        --surface: #0d111a;
        --surface-2: #121826;
        --line: #242d3d;
        --text: #e8eefb;
        --muted: #8f9bb7;
        --cyan: #2ec5ff;
        --pink: #ff5f99;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: Inter, Segoe UI, Arial, sans-serif;
        background: radial-gradient(circle at top right, #0d1324 0, var(--bg) 40%);
        color: var(--text);
      }
      .wrap { max-width: 1180px; margin: 24px auto; padding: 0 16px; }
      h1 { margin: 0 0 6px; font-size: 28px; }
      .sub { margin: 0 0 18px; color: var(--muted); font-size: 14px; }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 12px;
      }
      .card {
        background: linear-gradient(180deg, var(--surface-2), var(--surface));
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 14px;
      }
      .metric-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
      .metric-value { font-size: 28px; margin-top: 8px; font-weight: 700; }
      .section { margin-top: 14px; }
      .section h2 { margin: 0 0 10px; font-size: 20px; }
      .table-wrap {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid var(--line);
      }
      table { border-collapse: collapse; width: 100%; background: var(--surface); }
      th, td { padding: 11px 10px; text-align: left; border-bottom: 1px solid var(--line); font-size: 14px; }
      th { color: var(--muted); font-weight: 600; background: #0f1422; }
      tr:last-child td { border-bottom: none; }
      .good { color: var(--cyan); }
      .warn { color: var(--pink); font-weight: 700; }
      .kv { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; font-size: 14px; }
      .kv span { color: var(--muted); }
      @media (max-width: 760px) {
        .kv { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>HNG Stage 3 Anomaly Detection Dashboard</h1>
      <p class="sub">Live metrics refresh every {{ refresh_seconds }} seconds | Detector + Nginx + Nextcloud</p>

      <div class="grid">
        <div class="card"><div class="metric-label">Global Requests/Sec</div><div class="metric-value good">{{ "%.2f"|format(snap["global_rps"]) }}</div></div>
        <div class="card"><div class="metric-label">Logs Processed</div><div class="metric-value">{{ total_logs }}</div></div>
        <div class="card"><div class="metric-label">Banned IPs</div><div class="metric-value warn">{{ banned_count }}</div></div>
        <div class="card"><div class="metric-label">Uptime</div><div class="metric-value">{{ uptime_human }}</div></div>
        <div class="card"><div class="metric-label">CPU Usage</div><div class="metric-value">{{ "%.1f"|format(cpu) }}%</div></div>
        <div class="card"><div class="metric-label">Memory Usage</div><div class="metric-value">{{ "%.1f"|format(mem) }}%</div></div>
      </div>

      <div class="card section">
        <h2>Effective Baseline</h2>
        <div class="kv">
          <div><span>Mean:</span> {{ "%.4f"|format(snap["baseline_mean"]) }}</div>
          <div><span>Stddev:</span> {{ "%.4f"|format(snap["baseline_stddev"]) }}</div>
          <div><span>Error Rate:</span> {{ "%.4f"|format(snap["baseline_error_rate"]) }}</div>
          <div><span>Source:</span> {{ snap["baseline_source"] }}</div>
        </div>
      </div>

      <div class="section">
        <h2>Top 10 Source IPs</h2>
        <div class="table-wrap">
          <table>
            <tr><th>IP</th><th>Total Requests Seen</th></tr>
            {% for ip, c in snap["top_ips"] %}
            <tr><td>{{ ip }}</td><td>{{ c }}</td></tr>
            {% endfor %}
          </table>
        </div>
      </div>

      <div class="section">
        <h2>Banned IPs</h2>
        <div class="table-wrap">
          <table>
            <tr><th>IP</th><th>Condition</th><th>Banned At</th><th>Duration</th><th>Expires At</th></tr>
            {% if snap["banned_ips"] %}
              {% for ip, details in snap["banned_ips"].items() %}
              <tr>
                <td>{{ ip }}</td>
                <td>{{ details["condition"] }}</td>
                <td>{{ details["banned_at"] }}</td>
                <td>{{ details["duration"] }}</td>
                <td>{{ details["expires_at"] if details["expires_at"] else "permanent" }}</td>
              </tr>
              {% endfor %}
            {% else %}
              <tr><td colspan="5">No banned IPs right now.</td></tr>
            {% endif %}
          </table>
        </div>
      </div>
    </div>
  </body>
</html>
"""

    def _uptime_human(seconds: int) -> str:
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours}h {minutes}m {secs}s"

    @app.get("/")
    def index():
        snap = engine.snapshot()
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory().percent
        total_logs = sum(count for _, count in snap["top_ips"])
        return render_template_string(
            page,
            snap=snap,
            cpu=cpu,
            mem=mem,
            refresh_seconds=refresh_seconds,
            uptime_human=_uptime_human(snap["uptime_seconds"]),
            total_logs=total_logs,
            banned_count=len(snap["banned_ips"]),
        )

    @app.get("/metrics.json")
    def metrics():
        payload = engine.snapshot()
        payload["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        payload["memory_percent"] = psutil.virtual_memory().percent
        return jsonify(payload)

    return app
