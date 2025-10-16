# 🚀 Quick Start: Launch Local Test in 5 Minutes

**Goal:** Verify the entire D-GRID system works end-to-end in local environment.

**Time estimate:** 10 minutes (actual testing)

---

## Step 1: Setup Test Repository (1 min)

```bash
# Create temporary test repo
cd /tmp
rm -rf dgrid-test 2>/dev/null
mkdir dgrid-test && cd dgrid-test

# Initialize git
git init
git config user.email "test@local"
git config user.name "Test User"

# Create directory structure
mkdir -p nodes tasks/{queue,in_progress,completed,failed}
touch tasks/{queue,in_progress,completed,failed}/.gitkeep

# First commit
git add -A
git commit -m "Initial test repo structure"

echo "✅ Test repo ready: /tmp/dgrid-test"
```

---

## Step 2: Configure Worker Environment (1 min)

```bash
# Set test environment variables
export GIT_REPO_URL="file:///tmp/dgrid-test"
export NODE_ID="test-worker-001"
export HEARTBEAT_INTERVAL="10"
export TASK_CHECK_INTERVAL="5"
export DOCKER_TIMEOUT="30"
export LOG_LEVEL="DEBUG"

# Validate config
cd /Users/fab/GitHub/dgrid
python3 -c "from worker.config import validate_config; validate_config()" && echo "✅ Config valid"

# Install requirements if needed
pip install -q -r worker/requirements.txt 2>/dev/null
```

---

## Step 3: Start Worker in Background (1 min)

```bash
# Start worker with output to file
cd /Users/fab/GitHub/dgrid
python3 worker/main.py > /tmp/worker.log 2>&1 &
WORKER_PID=$!
echo "Worker started (PID: $WORKER_PID)"

# Wait for initialization
sleep 3

# Check if started successfully
if tail -20 /tmp/worker.log | grep -q "Clone"; then
    echo "✅ Worker initialized successfully"
else
    echo "❌ Worker initialization failed"
    cat /tmp/worker.log
    exit 1
fi
```

---

## Step 4: Submit and Execute a Task (2 min)

```bash
# Create a simple demo task
cd /tmp/dgrid-test

cat > tasks/queue/demo-hello.json << 'EOF'
{
  "task_id": "demo-hello",
  "script": "echo 'Hello from D-GRID'; echo 'Execution successful'; sleep 1",
  "timeout_seconds": 30
}
EOF

# Commit and push
git add tasks/queue/demo-hello.json
git commit -m "Add demo task"
git push origin main 2>&1 | head -5

echo "✅ Task submitted. Worker should pick it up in 5 seconds..."

# Wait for worker to process
sleep 8

# Check if task was executed
if [ -f tasks/completed/demo-hello-result.json ]; then
    echo "✅ Task COMPLETED"
    echo "Result:"
    cat tasks/completed/demo-hello-result.json | head -10
else
    echo "⚠️  Task not yet completed. Checking status..."
    echo "Queue files:" && ls -la tasks/queue/ | tail -3
    echo "In progress:" && ls -la tasks/in_progress/ | tail -3
fi
```

---

## Step 5: Generate Dashboard (1 min)

```bash
cd /tmp/dgrid-test

# Run dashboard generator
python3 /Users/fab/GitHub/dgrid/.github/scripts/generate_dashboard.py

# Check if dashboard was generated
if [ -f index.html ]; then
    echo "✅ Dashboard generated"
    echo "Checking contents..."
    grep -o "demo-hello" index.html && echo "✓ Task found in dashboard"
    grep -o "🟢 ATTIVO" index.html && echo "✓ Active node status visible"
else
    echo "❌ Dashboard generation failed"
fi
```

---

## Step 6: Verify Auto-Healing (2 min)

```bash
cd /tmp/dgrid-test

# Simulate node inactivity
python3 << 'PYTHON'
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Update node heartbeat to 10 minutes ago
node_file = Path("nodes/test-worker-001.json")
with open(node_file) as f:
    data = json.load(f)

past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
data['last_heartbeat'] = past

with open(node_file, 'w') as f:
    json.dump(data, f, indent=2)

print("✓ Node marked as inactive (10 min ago)")
PYTHON

# Create an orphaned task
cat > tasks/in_progress/test-worker-001-demo-orphan.json << 'EOF'
{
  "task_id": "demo-orphan",
  "script": "sleep 999",
  "timeout_seconds": 60
}
EOF

git add tasks/in_progress/test-worker-001-demo-orphan.json nodes/test-worker-001.json
git commit -m "Setup orphan task scenario"
git push origin main 2>&1 | head -3

echo "✓ Orphaned task created"

# Run dashboard cleanup
echo ""
echo "Running cleanup..."
python3 /Users/fab/GitHub/dgrid/.github/scripts/generate_dashboard.py

# Verify task was moved back to queue
if [ -f tasks/queue/demo-orphan.json ]; then
    echo "✅ Auto-healing SUCCESSFUL: orphaned task recovered to queue"
else
    echo "❌ Auto-healing FAILED: task not recovered"
fi
```

---

## Step 7: Cleanup (optional)

```bash
# Kill worker
kill $WORKER_PID 2>/dev/null

# View logs
echo ""
echo "=== Worker Logs (last 30 lines) ==="
tail -30 /tmp/worker.log

# Remove test repo
# rm -rf /tmp/dgrid-test
```

---

## Expected Output Summary

### If everything works ✅

```
✅ Test repo ready
✅ Config valid
✅ Worker initialized successfully
✅ Task COMPLETED
✅ Dashboard generated
✓ Active node status visible
✅ Auto-healing SUCCESSFUL: orphaned task recovered to queue
```

### Troubleshooting

**Worker doesn't start:**
```bash
# Check logs
cat /tmp/worker.log

# Verify config
python3 -c "from worker.config import validate_config; validate_config()"

# Try with DEBUG output
PYTHONUNBUFFERED=1 python3 worker/main.py
```

**Task not picked up:**
```bash
# Check worker logs for "find_task"
grep "find_task" /tmp/worker.log

# Verify task file is valid JSON
python3 -m json.tool /tmp/dgrid-test/tasks/queue/demo-hello.json

# Check if task was moved to in_progress
ls -la /tmp/dgrid-test/tasks/in_progress/
```

**Dashboard not generated:**
```bash
# Check if script exists
ls -la /Users/fab/GitHub/dgrid/.github/scripts/generate_dashboard.py

# Run with verbose output
python3 /Users/fab/GitHub/dgrid/.github/scripts/generate_dashboard.py

# Check permissions
chmod +x /Users/fab/GitHub/dgrid/.github/scripts/generate_dashboard.py
```

---

## Next Steps After Successful Test

✅ **Tests pass locally?** → Proceed to:

1. **Docker Build**
   ```bash
   docker build -t d-grid-worker:latest .
   docker run --rm d-grid-worker:latest python3 worker/main.py --help
   ```

2. **GitHub Setup**
   - Push repo to GitHub
   - Enable GitHub Pages
   - Enable GitHub Actions

3. **🚀 Launch**
   - Share with volunteers
   - Monitor first 24 hours

---

## Success Criteria

Mark each as complete:

- [ ] Worker starts without errors
- [ ] Node registered in `nodes/`
- [ ] Task found and executed
- [ ] Result file created in `completed/`
- [ ] Dashboard HTML generated
- [ ] Active node shows on dashboard
- [ ] Orphaned task recovered to queue
- [ ] Dashboard shows 2 completed tasks

If all above are ✅ → **You're ready for public launch!**

---

**Duration:** ~10 minutes  
**Complexity:** Low (all local, no network dependencies)  
**Risk:** Zero (test repo, no production impact)

**Status:** 🟢 Ready to test
