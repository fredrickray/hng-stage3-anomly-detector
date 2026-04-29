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
      body { font-family: Arial, sans-serif; margin: 20px; }
      .card { border: 1px solid #ddd; padding: 12px; margin-bottom: 12px; border-radius: 8px; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    </style>
  </head>
  <body>
    <h2>HNG Anomaly Detector</h2>
    <div class="card">
      <p><b>Uptime:</b> {{ snap["uptime_seconds"] }}s</p>
      <p><b>Global Req/s:</b> {{ "%.2f"|format(snap["global_rps"]) }}</p>
      <p><b>CPU:</b> {{ "%.1f"|format(cpu) }}%</p>
      <p><b>Memory:</b> {{ "%.1f"|format(mem) }}%</p>
      <p><b>Baseline Mean:</b> {{ "%.2f"|format(snap["baseline_mean"]) }}</p>
      <p><b>Baseline Stddev:</b> {{ "%.2f"|format(snap["baseline_stddev"]) }}</p>
      <p><b>Baseline Error Rate:</b> {{ "%.4f"|format(snap["baseline_error_rate"]) }}</p>
      <p><b>Baseline Source:</b> {{ snap["baseline_source"] }}</p>
    </div>
    <div class="card">
      <h3>Banned IPs</h3>
      <pre>{{ snap["banned_ips"] }}</pre>
    </div>
    <div class="card">
      <h3>Top 10 Source IPs</h3>
      <table>
        <tr><th>IP</th><th>Requests Seen</th></tr>
        {% for ip, c in snap["top_ips"] %}
        <tr><td>{{ ip }}</td><td>{{ c }}</td></tr>
        {% endfor %}
      </table>
    </div>
  </body>
</html>
"""

    @app.get("/")
    def index():
        snap = engine.snapshot()
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory().percent
        return render_template_string(page, snap=snap, cpu=cpu, mem=mem, refresh_seconds=refresh_seconds)

    @app.get("/metrics.json")
    def metrics():
        payload = engine.snapshot()
        payload["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        payload["memory_percent"] = psutil.virtual_memory().percent
        return jsonify(payload)

    return app
