#!/usr/bin/env python3
"""
D-GRID Mission Control Dashboard Generator

Responsabilità:
1. Scannerizza lo stato dei nodi (attivo/inattivo)
2. Conta i task per stato (queue, in_progress, completed, failed)
3. Identifica e ripulisce task orfani (nodo inattivo > 5 min)
4. Genera HTML della dashboard con stato real-time
5. Committa e pusha su gh-pages

Logica di Cleanup:
- Task in 'in_progress' il cui nodo è inattivo da > 5 min vengono rimessi in queue
- Viene eseguito git mv per atomicità
- Se ci sono cambiamenti, automaticamente committati e pushati
"""

import os
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import subprocess

# --- CONFIGURAZIONE ---
REPO_ROOT = Path(__file__).parent.parent.parent
NODES_DIR = REPO_ROOT / "nodes"
TASKS_DIR = REPO_ROOT / "tasks"
ORPHAN_TIMEOUT_MINUTES = 5  # Task orfani se nodo inattivo > 5 min


def get_nodes_status():
    """
    Scan nodes, calculate their status (active/inactive).
    
    Returns:
        list: List of dicts with node info sorted by recent heartbeat
    """
    nodes = []
    if not NODES_DIR.exists():
        print(f"⚠️  Directory {NODES_DIR} does not exist yet. No nodes registered.")
        return nodes
    
    now = datetime.now(timezone.utc)
    for node_file in NODES_DIR.glob("*.json"):
        try:
            with open(node_file, 'r') as f:
                data = json.load(f)
            
            # Parse ISO timestamp and ensure it's timezone-aware
            last_heartbeat = datetime.fromisoformat(data['last_heartbeat'])
            # If the timestamp is naive (no timezone info), assume UTC.
            # This maintains backward compatibility with worker nodes that store
            # timestamps without timezone info, as D-GRID operates in UTC by convention.
            if last_heartbeat.tzinfo is None:
                last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
            uptime = now - last_heartbeat
            
            # Determine if active (recent heartbeat)
            is_active = uptime < timedelta(minutes=ORPHAN_TIMEOUT_MINUTES)
            data['status'] = "🟢 ACTIVE" if is_active else "🔴 INACTIVE"
            data['last_seen_seconds'] = int(uptime.total_seconds())
            data['last_seen'] = f"{data['last_seen_seconds']} seconds ago"
            
            nodes.append(data)
            print(f"✓ Node '{data['node_id']}': {data['status']} ({data['last_seen']})")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️  Error reading {node_file}: {e}")
            continue
    
    return sorted(nodes, key=lambda x: x.get('last_seen_seconds', float('inf')))


def get_task_counts():
    """
    Count tasks in each status.
    
    Returns:
        dict: Count per status (queue, in_progress, completed, failed)
    """
    counts = {}
    for status in ["queue", "in_progress", "completed", "failed"]:
        status_dir = TASKS_DIR / status
        if status_dir.exists():
            # Count only .json files (exclude .gitkeep)
            count = len(list(status_dir.glob("*.json")))
            counts[status] = count
            print(f"  {status}: {count} tasks")
        else:
            counts[status] = 0
            print(f"  {status}: 0 tasks (dir does not exist)")
    
    return counts


def cleanup_orphan_tasks(nodes_status):
    """
    Identify orphan tasks (whose worker node is inactive > ORPHAN_TIMEOUT_MINUTES)
    and move them back to queue using git mv.
    
    Args:
        nodes_status (list): List of active/inactive nodes
        
    Returns:
        list: List of cleaned up tasks
    """
    print("\n🧹 Checking for orphan tasks...")
    in_progress_dir = TASKS_DIR / "in_progress"
    queue_dir = TASKS_DIR / "queue"
    
    if not in_progress_dir.exists():
        print(f"  Directory {in_progress_dir} does not exist. Skipping cleanup.")
        return []

    # Identify active nodes
    active_node_ids = {node['node_id'] for node in nodes_status if node['status'] == "🟢 ACTIVE"}
    cleaned_tasks = []

    for task_file in in_progress_dir.glob("*.json"):
        try:
            # Filename format: {node_id}-{task_id}.json
            # E.g.: worker-001-fibonacci-2025.json
            parts = task_file.name.split('-', 1)
            if len(parts) < 2:
                print(f"  ⚠️  Unexpected filename format: {task_file.name}, skipping")
                continue
            
            node_id_in_charge = parts[0]
            task_name = parts[1]
            
            # If node is inactive, task is orphan
            if node_id_in_charge not in active_node_ids:
                new_path = queue_dir / task_name
                print(f"  ❗️ Orphan task: {task_file.name}")
                print(f"     Node '{node_id_in_charge}' inactive. Moving back to queue...")
                
                # Use git mv for consistency with worker logic
                result = subprocess.run(
                    ["git", "mv", str(task_file), str(new_path)],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    print(f"     ⚠️  git mv failed: {result.stderr}")
                else:
                    cleaned_tasks.append(task_file.name)
                    print(f"     ✓ Moved to {new_path.name}")
        except Exception as e:
            print(f"  ⚠️  Error during cleanup of {task_file.name}: {e}")
            continue
    
    # If there are cleaned tasks, commit and push
    if cleaned_tasks:
        print(f"\n✅ Cleanup completed: {len(cleaned_tasks)} tasks moved back to queue")
        try:
            subprocess.run(
                ["git", "config", "user.name", "D-GRID Maintainer Bot"],
                check=True,
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "actions@github.com"],
                check=True,
                capture_output=True
            )
            
            commit_message = f"chore: Auto-cleanup {len(cleaned_tasks)} orphan tasks"
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                check=True,
                capture_output=True
            )
            
            subprocess.run(
                ["git", "push"],
                check=True,
                capture_output=True
            )
            print("✓ Commit and push completed")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Error during commit/push: {e}")
    else:
        print("✓ No orphan tasks found")
    
    return cleaned_tasks


def generate_html(nodes, counts):
    """
    Genera una pagina HTML con lo stato della D-GRID.
    
    Args:
        nodes (list): Lista di nodi con info
        counts (dict): Conteggi task per stato
        
    Returns:
        str: HTML della dashboard
    """
    # Costruisci tabella nodi
    nodes_html = "<tr><td colspan='5' style='text-align: center; color: #999;'>Nessun nodo registrato.</td></tr>"
    if nodes:
        rows = []
        for node in nodes:
            status_emoji = node['status'].split()[0]  # Estrae emoji
            rows.append(f"""<tr>
                <td style="text-align: center;">{node['status']}</td>
                <td><code>{node.get('node_id', 'N/A')}</code></td>
                <td>{node.get('cpu_cores', 'N/A')}</td>
                <td>{node.get('memory_gb', 'N/A')} GB</td>
                <td>{node.get('last_seen', 'N/A')}</td>
            </tr>""")
        nodes_html = "".join(rows)
    
    # Conta totali
    total_tasks = sum(counts.values())
    active_nodes = len([n for n in nodes if n['status'].startswith('🟢')])
    
    html_template = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="60">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>D-GRID Mission Control</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 2em;
        }}
        
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            padding: 2.5em;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 2em;
            border-bottom: 3px solid #667eea;
            padding-bottom: 1.5em;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            color: #333;
            margin-bottom: 0.5em;
        }}
        
        .header p {{
            color: #666;
            font-size: 1.1em;
            margin-bottom: 0.5em;
        }}
        
        .update-info {{
            color: #999;
            font-size: 0.9em;
            font-style: italic;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5em;
            margin: 2em 0;
        }}
        
        .stat {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1.5em;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }}
        
        .stat h3 {{
            font-size: 2.8em;
            margin-bottom: 0.3em;
            font-weight: 700;
        }}
        
        .stat p {{
            font-size: 0.95em;
            opacity: 0.95;
        }}
        
        .stat.active {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        
        .stat.queue {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        
        .stat.running {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }}
        
        .stat.completed {{
            background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
        }}
        
        h2 {{
            color: #333;
            font-size: 1.5em;
            margin: 2em 0 1em 0;
            border-bottom: 2px solid #eee;
            padding-bottom: 0.7em;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1em;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }}
        
        th {{
            background-color: #f8f9fa;
            color: #333;
            padding: 1em;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #ddd;
        }}
        
        td {{
            padding: 0.9em 1em;
            border-bottom: 1px solid #eee;
        }}
        
        tr:hover {{
            background-color: #f8f9fa;
        }}
        
        tr:last-child td {{
            border-bottom: none;
        }}
        
        code {{
            background-color: #f5f5f5;
            padding: 0.2em 0.5em;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        .empty-message {{
            text-align: center;
            color: #999;
            padding: 2em;
            font-style: italic;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 3em;
            padding-top: 2em;
            border-top: 2px solid #eee;
            color: #888;
            font-size: 0.9em;
        }}
        
        .badge {{
            display: inline-block;
            padding: 0.3em 0.8em;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        
        .badge.active {{
            background-color: #d4edda;
            color: #155724;
        }}
        
        .badge.inactive {{
            background-color: #f8d7da;
            color: #721c24;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌐 D-GRID Mission Control</h1>
            <p>Status of the decentralized task execution network</p>
            <div class="update-info">
                Last update: <strong>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</strong>
                • Auto-refresh every 60 seconds
            </div>
        </div>
        
        <h2>📊 Stato Generale</h2>
        <div class="stats">
            <div class="stat active">
                <h3>{active_nodes}</h3>
                <p>Active Nodes</p>
            </div>
            <div class="stat queue">
                <h3>{counts['queue']}</h3>
                <p>Tasks in Queue</p>
            </div>
            <div class="stat running">
                <h3>{counts['in_progress']}</h3>
                <p>Running Tasks</p>
            </div>
            <div class="stat completed">
                <h3>{counts['completed']}</h3>
                <p>Completed Tasks</p>
            </div>
        </div>
        
        <h2>🖥️ Nodi della Rete</h2>
        <table>
            <thead>
                <tr>
                    <th style="width: 15%;">Status</th>
                    <th style="width: 20%;">Node ID</th>
                    <th style="width: 15%;">CPU Cores</th>
                    <th style="width: 15%;">Memory</th>
                    <th style="width: 35%;">Last Heartbeat</th>
                </tr>
            </thead>
            <tbody>
                {nodes_html}
            </tbody>
        </table>
        
        <h2>⚙️ Dettagli Task</h2>
        <p style="color: #666; margin-bottom: 1em;">
            Total: <strong>{total_tasks}</strong> tasks in the system
            • Failed: <strong>{counts['failed']}</strong>
        </p>
        
        <div class="footer">
            <p>
                D-GRID v2.0 • Decentralized Operation<br>
                <small>Dashboard generated automatically every 5 minutes</small>
            </p>
        </div>
    </div>
</body>
</html>"""
    
    return html_template


def main():
    """Main entry point."""
    print("=" * 70)
    print("🚀 D-GRID Mission Control Dashboard Generator")
    print("=" * 70)
    
    print("\n📍 Paths:")
    print(f"  Repo root: {REPO_ROOT}")
    print(f"  Nodes dir: {NODES_DIR}")
    print(f"  Tasks dir: {TASKS_DIR}")
    
    print("\n1️⃣  Scanning node status...")
    nodes = get_nodes_status()
    print(f"   → {len(nodes)} total nodes")
    
    print("\n2️⃣  Cleaning orphan tasks...")
    cleaned = cleanup_orphan_tasks(nodes)
    
    print("\n3️⃣  Counting tasks per status...")
    counts = get_task_counts()
    
    print("\n4️⃣  Generating dashboard HTML...")
    html_content = generate_html(nodes, counts)
    
    print("\n5️⃣  Saving dashboard...")
    docs_dir = REPO_ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    output_path = docs_dir / "index.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"   ✓ Dashboard saved to {output_path}")
    
    print("\n" + "=" * 70)
    print("✅ Dashboard generation completed successfully")
    print("=" * 70 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
