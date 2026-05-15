import os
import json
import sqlite3
import datetime
from pathlib import Path
from flask import Flask, request, jsonify, Response, session, redirect, url_for
from functools import wraps
import pytz
import werkzeug

SUBSCRIBERS_FILE = Path("subscribers.json")
METRICS_FILE = Path("metrics.json")
CONFIG_FILE = Path("config.json")
IST = pytz.timezone('Asia/Kolkata')

app = Flask(__name__)
app.secret_key = "arms_monitor_secret_key_123" # In production, use a random string

# User Credentials
DASHBOARD_USER = "Knightwinner"
DASHBOARD_PASS = "GreaterShifter"

def get_ist_now():
    return datetime.datetime.now(IST)

def load_db() -> dict:
    default_db = {
        "approved": [], 
        "pending": {},
        "slots": [
            {"id": 4, "label": "A"},
            {"id": 5, "label": "B"},
            {"id": 2, "label": "C"},
            {"id": 7, "label": "D"}
        ]
    }
    if SUBSCRIBERS_FILE.exists():
        try:
            data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
            if "slots" not in data:
                data["slots"] = default_db["slots"]
            return data
        except json.JSONDecodeError:
            pass
    return default_db

def save_db(db: dict) -> None:
    SUBSCRIBERS_FILE.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")

def load_config():
    if not CONFIG_FILE.exists():
        return {"arms_username": "", "arms_password": "", "poll_interval": 20}
    try:
        return json.loads(CONFIG_FILE.read_text())
    except:
        return {"arms_username": "", "arms_password": "", "poll_interval": 20}

def save_config(config):
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, werkzeug.exceptions.HTTPException):
        return jsonify({"error": e.description}), e.code
    return jsonify({"error": str(e), "type": type(e).__name__}), 500

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.form if not request.is_json else request.json
        username = data.get("username")
        password = data.get("password")
        if username == DASHBOARD_USER and password == DASHBOARD_PASS:
            session["logged_in"] = True
            return jsonify({"status": "success"}) if request.is_json else redirect(url_for("index"))
        return jsonify({"error": "Invalid credentials"}), 401 if request.is_json else "Invalid credentials", 401
    
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login | ARMS Monitor</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&display=swap" rel="stylesheet">
        <style>
            :root { --bg: #0d1117; --accent: #58a6ff; --card: #161b22; }
            body { background: var(--bg); color: white; font-family: 'Outfit', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .login-card { background: var(--card); padding: 2.5rem; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); width: 100%; max-width: 380px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }
            h1 { margin-bottom: 1.5rem; font-size: 1.8rem; text-align: center; background: linear-gradient(90deg, #58a6ff, #3fb950); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            input { width: 100%; padding: 12px; margin-bottom: 1rem; border-radius: 8px; border: 1px solid #30363d; background: #010409; color: white; box-sizing: border-box; outline: none; }
            input:focus { border-color: var(--accent); }
            button { width: 100%; padding: 12px; border-radius: 8px; border: none; background: var(--accent); color: #0d1117; font-weight: 600; cursor: pointer; transition: 0.2s; }
            button:hover { opacity: 0.9; transform: translateY(-1px); }
        </style>
    </head>
    <body>
        <div class="login-card">
            <h1>ARMS Portal</h1>
            <form method="POST">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Unlock Dashboard</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/api/config", methods=["GET", "POST"])
@requires_auth
def api_config():
    if request.method == "POST":
        data = request.json
        config = load_config()
        if "arms_username" in data: config["arms_username"] = data["arms_username"]
        if "arms_password" in data: config["arms_password"] = data["arms_password"]
        if "poll_interval" in data: config["poll_interval"] = int(data["poll_interval"])
        save_config(config)
        return jsonify({"status": "success"})
    return jsonify(load_config())

@app.route("/favicon.ico")
def favicon():
    return Response(status=204)

@app.route("/")
@requires_auth
def index():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ARMS Monitor | Premium Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            :root {
                --bg: #030712;
                --surface: rgba(17, 24, 39, 0.7);
                --border: rgba(255, 255, 255, 0.08);
                --accent: #6366f1;
                --accent-glow: rgba(99, 102, 241, 0.3);
                --success: #10b981;
                --danger: #ef4444;
                --text: #f3f4f6;
                --text-dim: #9ca3af;
            }
            
            * { box-sizing: border-box; }
            body {
                margin: 0; font-family: 'Outfit', sans-serif; background: var(--bg); color: var(--text);
                min-height: 100vh; display: flex; overflow-x: hidden;
            }
            
            /* Animated Background */
            .bg-glow {
                position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: -1;
                background: 
                    radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.15) 0%, transparent 40%),
                    radial-gradient(circle at 80% 70%, rgba(16, 185, 129, 0.1) 0%, transparent 40%);
                filter: blur(80px);
            }

            /* Sidebar */
            .sidebar {
                width: 280px; height: 100vh; background: rgba(0,0,0,0.3); border-right: 1px solid var(--border);
                backdrop-filter: blur(20px); padding: 2rem 1.5rem; display: flex; flex-direction: column;
                position: sticky; top: 0;
            }
            .brand { font-size: 1.5rem; font-weight: 600; margin-bottom: 3rem; display: flex; align-items: center; gap: 12px; }
            .nav-link {
                padding: 12px 16px; border-radius: 12px; cursor: pointer; color: var(--text-dim);
                transition: 0.3s; margin-bottom: 8px; display: flex; align-items: center; gap: 12px; font-weight: 500;
            }
            .nav-link:hover { background: rgba(255,255,255,0.05); color: var(--text); }
            .nav-link.active { background: var(--accent); color: white; box-shadow: 0 4px 15px var(--accent-glow); }

            /* Main Content */
            main { flex: 1; padding: 2rem 3rem; max-width: 1200px; margin: 0 auto; width: 100%; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2.5rem; }
            .status-chip { 
                background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2);
                color: var(--success); padding: 6px 14px; border-radius: 100px; font-size: 0.85rem; font-weight: 600;
                display: flex; align-items: center; gap: 8px;
            }
            .status-dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; box-shadow: 0 0 10px var(--success); animation: pulse 2s infinite; }
            @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.4; } 100% { opacity: 1; } }

            /* Grid Layout */
            .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin-bottom: 2rem; }
            .glass-card { 
                background: var(--surface); border: 1px solid var(--border); backdrop-filter: blur(12px);
                border-radius: 20px; padding: 1.5rem; box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .stat-label { font-size: 0.85rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
            .stat-value { font-size: 1.8rem; font-weight: 600; margin-top: 8px; }

            /* Terminal */
            .terminal { 
                background: #000; border: 1px solid var(--border); border-radius: 16px; padding: 1rem;
                height: 450px; overflow-y: auto; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
                scrollbar-width: thin; scrollbar-color: var(--accent) transparent;
            }
            .log-entry { margin-bottom: 6px; line-height: 1.5; border-bottom: 1px solid rgba(255,255,255,0.03); padding-bottom: 4px; }
            .log-time { color: var(--text-dim); margin-right: 12px; }
            .log-msg-success { color: var(--success); }
            .log-msg-error { color: var(--danger); }
            .log-msg-info { color: var(--accent); }

            /* Settings Forms */
            .form-group { margin-bottom: 1.5rem; }
            .form-group label { display: block; margin-bottom: 8px; color: var(--text-dim); font-size: 0.9rem; }
            input {
                width: 100%; background: rgba(0,0,0,0.3); border: 1px solid var(--border); padding: 12px 16px;
                border-radius: 12px; color: white; font-family: inherit; font-size: 1rem; outline: none; transition: 0.2s;
            }
            input:focus { border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-glow); }
            .btn {
                background: var(--accent); color: white; border: none; padding: 12px 24px; border-radius: 12px;
                font-weight: 600; cursor: pointer; transition: 0.2s; display: inline-flex; align-items: center; gap: 8px;
            }
            .btn:hover { transform: translateY(-1px); opacity: 0.9; }
            .btn-secondary { background: rgba(255,255,255,0.1); }

            .slot-config-item { 
                background: rgba(255,255,255,0.03); padding: 1rem; border-radius: 12px; margin-bottom: 12px;
                display: flex; gap: 1rem; align-items: center;
            }
            
            .tab-content { display: none; }
            .tab-content.active { display: block; animation: fadeIn 0.4s ease; }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

            @media (max-width: 1000px) {
                .sidebar { display: none; }
                .stats-row { grid-template-columns: repeat(2, 1fr); }
            }
        </style>
    </head>
    <body>
        <div class="bg-glow"></div>
        
        <aside class="sidebar">
            <div class="brand">🚀 ARMS Monitor</div>
            <nav>
                <div class="nav-link active" onclick="switchTab('dashboard', this)"><span>📊</span> Dashboard</div>
                <div class="nav-link" onclick="switchTab('slots', this)"><span>⚙️</span> Slots Config</div>
                <div class="nav-link" onclick="switchTab('security', this)"><span>🔐</span> Security</div>
                <div class="nav-link" onclick="switchTab('logs', this)"><span>📜</span> Live Logs</div>
            </nav>
            <div style="margin-top: auto;">
                <a href="/logout" style="color: var(--danger); text-decoration: none; font-size: 0.9rem; font-weight: 600;">🚪 Logout System</a>
            </div>
        </aside>

        <main>
            <div class="header">
                <h1 id="page-title">Dashboard Overview</h1>
                <div class="status-chip"><div class="status-dot"></div> Live Monitoring</div>
            </div>

            <!-- Dashboard Tab -->
            <div id="tab-dashboard" class="tab-content active">
                <div class="stats-row">
                    <div class="glass-card">
                        <div class="stat-label">Total Polls</div>
                        <div id="stat-polls" class="stat-value">--</div>
                    </div>
                    <div class="glass-card">
                        <div class="stat-label">System Uptime</div>
                        <div id="stat-uptime" class="stat-value">--</div>
                    </div>
                    <div class="glass-card">
                        <div class="stat-label">Total Courses</div>
                        <div id="stat-courses" class="stat-value">--</div>
                    </div>
                    <div class="glass-card">
                        <div class="stat-label">Latency</div>
                        <div id="stat-latency" class="stat-value">--</div>
                    </div>
                </div>

                <div class="glass-card" style="margin-bottom: 2rem;">
                    <div class="stat-label" style="margin-bottom: 1.5rem;">Slot Activity (24h)</div>
                    <div style="height: 350px;">
                        <canvas id="mainChart"></canvas>
                    </div>
                </div>
            </div>

            <!-- Slots Tab -->
            <div id="tab-slots" class="tab-content">
                <div class="glass-card">
                    <h3 style="margin-top:0;">ARMS Monitor Slots</h3>
                    <p style="color: var(--text-dim); font-size: 0.9rem; margin-bottom: 2rem;">Configure which Slot IDs the background engine should track.</p>
                    <div id="slot-list"></div>
                    <button class="btn btn-secondary" onclick="addSlotRow()" style="margin-top: 1rem;">+ Add New Slot</button>
                    <hr style="border: 0; border-top: 1px solid var(--border); margin: 2rem 0;">
                    <button class="btn" onclick="saveSlots()">💾 Save & Sync Bot</button>
                </div>
            </div>

            <!-- Security Tab -->
            <div id="tab-security" class="tab-content">
                <div class="glass-card">
                    <h3 style="margin-top:0;">ARMS Portal Credentials</h3>
                    <p style="color: var(--text-dim); font-size: 0.9rem; margin-bottom: 2rem;">These credentials are used by the bot to automatically log into the Saveetha ARMS portal.</p>
                    
                    <div class="form-group">
                        <label>ARMS Username / Roll No</label>
                        <input type="text" id="arms-user" placeholder="P1925XXXX">
                    </div>
                    <div class="form-group">
                        <label>ARMS Password</label>
                        <input type="password" id="arms-pass" placeholder="••••••••">
                    </div>
                    <div class="form-group">
                        <label>Poll Interval (Seconds)</label>
                        <input type="number" id="poll-int" value="20">
                    </div>
                    <button class="btn" onclick="saveConfig()">🛡️ Update Portal Access</button>
                </div>
            </div>

            <!-- Logs Tab -->
            <div id="tab-logs" class="tab-content">
                <div class="glass-card">
                    <h3 style="margin-top:0;">System Execution Logs</h3>
                    <div id="terminal" class="terminal">Loading logs...</div>
                </div>
            </div>
        </main>

        <script>
            let mainChart = null;

            function switchTab(tabId, el) {
                document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                document.getElementById('tab-' + tabId).classList.add('active');
                el.classList.add('active');
                document.getElementById('page-title').innerText = el.innerText.trim();
                
                if(tabId === 'slots') loadSlots();
                if(tabId === 'security') loadConfig();
            }

            async function updateStats() {
                try {
                    const r = await fetch('/api/stats');
                    const d = await r.json();
                    document.getElementById('stat-polls').innerText = d.polls;
                    document.getElementById('stat-uptime').innerText = d.uptime;
                    document.getElementById('stat-courses').innerText = d.total_courses;
                    document.getElementById('stat-latency').innerText = d.latency;

                    const lr = await fetch('/api/logs');
                    const ld = await lr.json();
                    const term = document.getElementById('terminal');
                    const scroll = term.scrollHeight - term.clientHeight <= term.scrollTop + 50;
                    term.innerHTML = ld.logs.map(l => {
                        let cls = '';
                        if(l.includes('✅') || l.includes('SUCCESS')) cls = 'log-msg-success';
                        if(l.includes('❌') || l.includes('ERROR')) cls = 'log-msg-error';
                        if(l.includes('[Bot]')) cls = 'log-msg-info';
                        return `<div class="log-entry"><span class="log-time">[${l.substring(0,8)}]</span><span class="${cls}">${l.substring(10)}</span></div>`;
                    }).join('');
                    if(scroll) term.scrollTop = term.scrollHeight;

                    const hr = await fetch('/api/history');
                    renderChart(await hr.json());
                } catch(e) {}
            }

            function renderChart(data) {
                const ctx = document.getElementById('mainChart').getContext('2d');
                if(!mainChart) {
                    mainChart = new Chart(ctx, {
                        type: 'line',
                        data: data,
                        options: {
                            responsive: true, maintainAspectRatio: false, animation: false,
                            scales: { 
                                y: { grid: {color: 'rgba(255,255,255,0.05)'}, ticks: {color: '#9ca3af'} },
                                x: { grid: {display: false}, ticks: {color: '#9ca3af'} }
                            },
                            plugins: { legend: { labels: { color: '#f3f4f6', font: {family: 'Outfit'} } } }
                        }
                    });
                } else {
                    mainChart.data = data;
                    mainChart.update();
                }
            }

            // --- Config & Slots ---
            async function loadSlots() {
                const r = await fetch('/api/settings');
                const d = await r.json();
                const list = document.getElementById('slot-list');
                list.innerHTML = '';
                d.slots.forEach(s => addSlotRow(s.id, s.label));
            }

            function addSlotRow(id='', label='') {
                const div = document.createElement('div');
                div.className = 'slot-config-item';
                div.innerHTML = `
                    <input type="number" value="${id}" placeholder="ID" style="width: 100px;">
                    <input type="text" value="${label}" placeholder="Slot Name" style="flex:1;">
                    <button class="btn btn-secondary" onclick="this.parentElement.remove()" style="padding: 10px;">✕</button>
                `;
                document.getElementById('slot-list').appendChild(div);
            }

            async function saveSlots() {
                const slots = [];
                document.querySelectorAll('.slot-config-item').forEach(row => {
                    const inputs = row.querySelectorAll('input');
                    if(inputs[0].value && inputs[1].value) slots.push({id: parseInt(inputs[0].value), label: inputs[1].value});
                });
                await fetch('/api/settings', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({slots})
                });
                alert('Slots updated successfully!');
            }

            async function loadConfig() {
                const r = await fetch('/api/config');
                const d = await r.json();
                document.getElementById('arms-user').value = d.arms_username;
                document.getElementById('arms-pass').value = d.arms_password;
                document.getElementById('poll-int').value = d.poll_interval;
            }

            async function saveConfig() {
                const data = {
                    arms_username: document.getElementById('arms-user').value,
                    arms_password: document.getElementById('arms-pass').value,
                    poll_interval: parseInt(document.getElementById('poll-int').value)
                };
                await fetch('/api/config', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                alert('Security credentials updated! The bot will now use these for ARMS login.');
            }

            updateStats();
            setInterval(updateStats, 5000);
        </script>
    </body>
    </html>
    """
    return html

@app.route("/api/stats")
@requires_auth
def api_stats():
    db = load_db()
    metrics = {
        "start_time": get_ist_now().isoformat(),
        "polls": 0,
        "latency": "0.00s",
        "total_courses": 0
    }
    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE, "r") as f:
                saved = json.load(f)
                metrics.update(saved)
        except Exception:
            pass
            
    try:
        start_time = datetime.datetime.fromisoformat(metrics["start_time"])
    except:
        start_time = get_ist_now()

    uptime_delta = get_ist_now() - start_time
    hours, remainder = divmod(uptime_delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    uptime_str = f"{uptime_delta.days}d {hours}h {minutes}m" if uptime_delta.days > 0 else f"{hours}h {minutes}m"
    
    return jsonify({
        "subscribers": len(db.get("approved", [])),
        "slots": len(db.get("slots", [])),
        "total_courses": metrics["total_courses"],
        "uptime": uptime_str,
        "polls": metrics["polls"],
        "latency": metrics["latency"],
        "time": f"{get_ist_now().strftime('%I:%M:%S %p')} IST"
    })
@app.route("/api/history")
@requires_auth
def api_history():
    # Provide Chart.js formatting from SQLite History
    db = load_db()
    active_slots = db.get("slots", [])
    
    conn = sqlite3.connect("history.db")
    c = conn.cursor()
    # Fetch last 50 distinct timestamps
    c.execute("SELECT DISTINCT timestamp FROM history ORDER BY timestamp DESC LIMIT 50")
    times = [r[0] for r in c.fetchall()][::-1] 
    
    datasets = []
    colors = ['#58a6ff', '#238636', '#d29922', '#8a2be2', '#da3633']
    
    for idx, slot in enumerate(active_slots):
        sid = slot["id"]
        color = colors[idx % len(colors)]
        
        c.execute("SELECT timestamp, course_count FROM history WHERE slot_id = ? ORDER BY timestamp DESC LIMIT 50", (sid,))
        # Map out the values against the standard times
        raw_data = {r[0]: r[1] for r in c.fetchall()}
        
        data_points = []
        last_val = 0
        for t in times:
            if t in raw_data:
                last_val = raw_data[t]
            data_points.append(last_val)
            
        datasets.append({
            "label": f"Slot {slot['label']} ({sid})",
            "data": data_points,
            "borderColor": color,
            "backgroundColor": color + "33",
            "borderWidth": 2,
            "pointRadius": 0,
            "fill": True,
            "tension": 0.4
        })
    conn.close()
    
    # Format labels cleanly (HH:MM)
    clean_labels = [datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S").strftime("%H:%M") for t in times]
    return jsonify({"labels": clean_labels, "datasets": datasets})

@app.route("/api/settings", methods=["GET", "POST"])
@requires_auth
def api_settings():
    db = load_db()
    if request.method == "POST":
        data = request.json
        if "slots" in data:
            db["slots"] = data["slots"]
            save_db(db)
            return jsonify({"status": "success"})
    return jsonify({"slots": db.get("slots", [])})

@app.route("/api/logs")
@requires_auth
def api_logs():
    try:
        # Read last 150 lines efficiently without blowing up memory
        if not os.path.exists("slot_monitor.log"):
            return jsonify({"logs": ["No logs yet."]})
            
        with open("slot_monitor.log", "rb") as f:
            try:
                f.seek(-15000, os.SEEK_END)
            except IOError:
                pass
            lines = f.read().decode("utf-8", errors="ignore").splitlines()
            return jsonify({"logs": lines[-150:]})
    except Exception as e:
        return jsonify({"logs": [f"Error reading logs: {e}"]})

@app.route("/ping")
def ping():
    return "pong"


if __name__ == "__main__":
    import werkzeug.serving
    import logging
    
    log_werkzeug = logging.getLogger('werkzeug')
    log_werkzeug.setLevel(logging.ERROR)
    log_werkzeug.disabled = True

    class NoLogRequestHandler(werkzeug.serving.WSGIRequestHandler):
        def log_request(self, code='-', size='-'):
            pass
        def log(self, type, message, *args):
            pass

    port = int(os.environ.get("PORT", 8100))
    ip_addr = os.environ.get("IP", "0.0.0.0")
    print(f"  [Web] Attempting to start Flask WSGI on {ip_addr}:{port} (Silent HTTP mode)")
    werkzeug.serving.run_simple(
        ip_addr, port, app,
        use_reloader=False, 
        use_debugger=False,
        request_handler=NoLogRequestHandler
    )
