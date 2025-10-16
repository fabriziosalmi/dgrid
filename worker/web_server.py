#!/usr/bin/env python3
"""
D-GRID Worker Node - Local Dashboard Web Server

Espone una UI locale su localhost:8000 che mostra:
- Info del nodo (ID, uptime, status)
- Vista della rete dal punto di vista del worker
- Task locali e stato
- Health check dell'infrastruttura
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
from logger_config import get_logger

logger = get_logger("d-grid.web_server")

# Configurazione
REPO_PATH = Path(os.getenv("DGRID_REPO_PATH", "/tmp/dgrid-repo"))
NODE_ID = os.getenv("NODE_ID", "unknown-node")
PORT = 8000


class WorkerDashboardHandler(BaseHTTPRequestHandler):
    """Handler HTTP per la dashboard del worker"""

    def do_GET(self):
        """Gestisce richieste GET"""
        if self.path == "/" or self.path == "/index.html":
            self.serve_dashboard()
        elif self.path == "/api/status":
            self.serve_status_json()
        elif self.path == "/health":
            self.serve_health()
        else:
            self.send_error(404)

    def serve_dashboard(self):
        """Serve l'HTML della dashboard"""
        html = self.generate_dashboard_html()
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(html))
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def serve_status_json(self):
        """Serve lo stato del nodo come JSON"""
        status = self.get_node_status()
        json_str = json.dumps(status, indent=2, default=str)
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", len(json_str))
        self.end_headers()
        self.wfile.write(json_str.encode("utf-8"))

    def serve_health(self):
        """Simple health check"""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def generate_dashboard_html(self):
        """Genera l'HTML della dashboard del worker"""
        status = self.get_node_status()

        html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>D-GRID Worker: {NODE_ID}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            color: white;
            margin-bottom: 30px;
            text-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}
        
        header h1 {{
            font-size: 2.5em;
            margin-bottom: 5px;
        }}
        
        header .subtitle {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }}
        
        .card.status {{
            border-left-color: #{status.get('color', '667eea')};
        }}
        
        .card h2 {{
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #333;
        }}
        
        .info-group {{
            margin-bottom: 15px;
        }}
        
        .info-label {{
            font-size: 0.85em;
            color: #999;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .info-value {{
            font-size: 1.2em;
            color: #333;
            font-weight: 600;
            margin-top: 5px;
            font-family: 'Monaco', 'Courier New', monospace;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
            margin-top: 5px;
        }}
        
        .status-badge.active {{
            background: #10b981;
            color: white;
        }}
        
        .status-badge.inactive {{
            background: #ef4444;
            color: white;
        }}
        
        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #f0f0f0;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
        }}
        
        .tasks-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .task-item {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }}
        
        .task-item.completed {{
            border-left-color: #10b981;
        }}
        
        .task-item.failed {{
            border-left-color: #ef4444;
        }}
        
        .task-item .task-label {{
            font-size: 0.8em;
            color: #999;
            text-transform: uppercase;
        }}
        
        .task-item .task-value {{
            font-size: 0.95em;
            color: #333;
            font-weight: 600;
            margin-top: 3px;
            word-break: break-all;
        }}
        
        footer {{
            text-align: center;
            color: white;
            opacity: 0.8;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.2);
            font-size: 0.9em;
        }}
        
        .refresh-notice {{
            text-align: center;
            color: white;
            margin-top: 20px;
            opacity: 0.7;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 D-GRID Worker</h1>
            <div class="subtitle">Node: <strong>{status['node_id']}</strong></div>
        </header>
        
        <div class="grid">
            <!-- Node Status -->
            <div class="card status">
                <h2>📊 Status Nodo</h2>
                <div class="info-group">
                    <div class="info-label">Node ID</div>
                    <div class="info-value">{status['node_id']}</div>
                </div>
                <div class="info-group">
                    <div class="info-label">Status</div>
                    <div class="status-badge {'active' if status['is_active'] else 'inactive'}">
                        {'🟢 Attivo' if status['is_active'] else '🔴 Inattivo'}
                    </div>
                </div>
                <div class="info-group">
                    <div class="info-label">Uptime</div>
                    <div class="info-value">{status['uptime']}</div>
                </div>
                <div class="info-group">
                    <div class="info-label">Last Heartbeat</div>
                    <div class="info-value">{status['last_heartbeat']}</div>
                </div>
            </div>
            
            <!-- Network View -->
            <div class="card">
                <h2>🌐 Vista Rete</h2>
                <div class="info-group">
                    <div class="info-label">Repository URL</div>
                    <div class="info-value" style="font-size: 0.9em; word-break: break-all;">
                        {status['repo_url']}
                    </div>
                </div>
                <div class="info-group">
                    <div class="info-label">Repo Status</div>
                    <div class="info-value">{status['repo_status']}</div>
                </div>
                <div class="info-group">
                    <div class="info-label">Nodi Visibili</div>
                    <div class="info-value">{status['visible_nodes']}</div>
                </div>
            </div>
            
            <!-- Tasks Summary -->
            <div class="card">
                <h2>📋 Task Summary</h2>
                <div class="info-group">
                    <div class="info-label">In Coda</div>
                    <div class="info-value">{status['tasks_queue']}</div>
                </div>
                <div class="info-group">
                    <div class="info-label">In Esecuzione</div>
                    <div class="info-value">{status['tasks_in_progress']}</div>
                </div>
                <div class="info-group">
                    <div class="info-label">Completati</div>
                    <div class="info-value">{status['tasks_completed']}</div>
                </div>
                <div class="info-group">
                    <div class="info-label">Falliti</div>
                    <div class="info-value">{status['tasks_failed']}</div>
                </div>
            </div>
        </div>
        
        <!-- Detailed Tasks -->
        <div class="card">
            <h2>📝 Task Recenti</h2>
            {'<div class="tasks-grid">' + ''.join([
                f'<div class="task-item"><div class="task-label">Task</div><div class="task-value">{t}</div></div>'
                for t in status.get('recent_tasks', [])[:8]
            ]) + '</div>' if status.get('recent_tasks') else '<div style="color: #999; padding: 20px; text-align: center;">Nessun task recente</div>'}
        </div>
        
        <footer>
            <div>D-GRID Mission Control © 2025</div>
            <div>Last Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
        </footer>
        
        <div class="refresh-notice">
            🔄 Pagina si aggiorna ogni 5 secondi
        </div>
    </div>
    
    <script>
        // Auto-refresh ogni 5 secondi
        setTimeout(() => location.reload(), 5000);
    </script>
</body>
</html>
"""
        return html

    def get_node_status(self):
        """Raccoglie lo stato del nodo"""
        node_file = REPO_PATH / "nodes" / f"{NODE_ID}.json"
        is_active = False
        uptime = "N/A"
        last_heartbeat = "N/A"

        if node_file.exists():
            try:
                with open(node_file, "r") as f:
                    node_data = json.load(f)
                    last_heartbeat = node_data.get("last_heartbeat", "N/A")
                    
                    # Calcola se è attivo (heartbeat < 5 min fa)
                    if last_heartbeat != "N/A":
                        try:
                            ts = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
                            delta = (datetime.now(timezone.utc) - ts).total_seconds()
                            is_active = delta < 300  # 5 minuti
                        except:
                            pass
            except:
                pass

        # Conta task
        task_dirs = {
            "tasks_queue": REPO_PATH / "tasks" / "queue",
            "tasks_in_progress": REPO_PATH / "tasks" / "in_progress",
            "tasks_completed": REPO_PATH / "tasks" / "completed",
            "tasks_failed": REPO_PATH / "tasks" / "failed",
        }

        task_counts = {}
        recent_tasks = []
        for key, path in task_dirs.items():
            if path.exists():
                tasks = list(path.glob("*/"))
                task_counts[key] = len(tasks)
                recent_tasks.extend([t.name for t in tasks[:3]])
            else:
                task_counts[key] = 0

        # Conta nodi visibili
        nodes_dir = REPO_PATH / "nodes"
        visible_nodes = len(list(nodes_dir.glob("*.json"))) if nodes_dir.exists() else 0

        return {
            "node_id": NODE_ID,
            "is_active": is_active,
            "uptime": uptime,
            "last_heartbeat": last_heartbeat[:19] if last_heartbeat != "N/A" else "N/A",
            "repo_url": os.getenv("DGRID_REPO_URL", "N/A"),
            "repo_status": "✅ OK" if REPO_PATH.exists() else "❌ Errore",
            "visible_nodes": visible_nodes,
            "color": "10b981" if is_active else "ef4444",
            **task_counts,
            "recent_tasks": recent_tasks[:8],
        }

    def log_message(self, format, *args):
        """Silence default logging"""
        logger.debug(f"HTTP: {format % args}")


def start_web_server():
    """Avvia il web server in un thread separato"""
    server = HTTPServer(("0.0.0.0", PORT), WorkerDashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"🌐 Web Server avviato su http://0.0.0.0:{PORT}")
    return server


if __name__ == "__main__":
    server = start_web_server()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Web Server fermato.")
        server.shutdown()
