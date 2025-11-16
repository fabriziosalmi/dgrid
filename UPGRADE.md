# D-GRID Upgrade Guide

## Overview

This guide helps you upgrade to the improved D-GRID with Phase 1 and Phase 2 enhancements.

## What's New

### Phase 1: Quick Wins & Stability ✅

1. **Git Optimization (#5)**
   - Shallow clones (80-90% faster)
   - Reduced bandwidth usage (99%+)
   - Faster worker startup

2. **Smart Polling (#6)**
   - Intelligent Git operations
   - 90%+ reduction in unnecessary pulls
   - Exponential backoff retry logic

3. **Resource Quotas (#10)**
   - Task rate limiting
   - CPU/memory thresholds
   - Fair resource allocation

4. **Health Monitoring (#18)**
   - Automated health checks
   - Self-healing capabilities
   - Docker resource cleanup

### Phase 2: Security Hardening ✅

1. **Secure Credentials (#12)**
   - SSH key support (recommended)
   - Git credential helper integration
   - GitHub App token support
   - Automatic method detection

2. **Task Signing (#9)**
   - GPG/PGP signature verification
   - Trusted key management
   - Prevent malicious task injection

### Phase 3: Scalability (Partial)

1. **Task Sharding (#1)**
   - Priority queues (critical, high, medium, low)
   - Hash-based distribution
   - Reduced contention

2. **Auto-Scaling Signals (#3)**
   - Metrics collection workflow
   - Scaling recommendations
   - Real-time dashboard

3. **Result Archival (#4)**
   - Monthly automated archival
   - Compression support
   - Long-term performance

## Upgrading

### For Existing Workers

#### 1. Update Docker Image

```bash
# Pull latest image
docker pull fabriziosalmi/d-grid-worker:latest

# Or rebuild locally
cd /path/to/dgrid
docker build -t dgrid-worker:latest .
```

#### 2. Update Environment Variables

Add new optimization settings to your docker-compose.yml or docker run command:

```yaml
services:
  dgrid-worker:
    image: fabriziosalmi/d-grid-worker:latest
    environment:
      # Existing settings
      NODE_ID: worker-001
      DGRID_REPO_URL: https://github.com/user/repo.git
      
      # Phase 1: Performance
      USE_SHALLOW_CLONE: "true"         # Default: true
      USE_SMART_POLLING: "true"         # Default: true
      MAX_TASKS_PER_HOUR: "100"        # Default: 0 (unlimited)
      MAX_CPU_PERCENT: "80"            # Default: 80
      MAX_MEMORY_PERCENT: "80"         # Default: 80
      
      # Phase 2: Security (optional)
      ENABLE_TASK_SIGNING: "false"     # Default: false
      TRUSTED_KEYS_FILE: "/app/trusted_keys.txt"
```

#### 3. Migrate to SSH Authentication (Recommended)

**Why?** SSH keys are more secure than tokens and don't expose credentials.

```bash
# 1. Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "dgrid-worker@example.com"

# 2. Add public key to GitHub
# Copy contents of ~/.ssh/id_ed25519.pub
# GitHub: Settings → SSH and GPG keys → New SSH key

# 3. Mount SSH keys in container
docker run -d \
  --name dgrid-worker \
  -e NODE_ID=worker-001 \
  -e DGRID_REPO_URL=git@github.com:user/repo.git \
  -v ~/.ssh:/root/.ssh:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  fabriziosalmi/d-grid-worker:latest
```

Or with docker-compose:

```yaml
services:
  dgrid-worker:
    volumes:
      - ~/.ssh:/root/.ssh:ro
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      DGRID_REPO_URL: git@github.com:user/repo.git
```

#### 4. Enable Task Signing (Optional, Recommended for Production)

**Why?** Prevents unauthorized task injection and ensures task authenticity.

```bash
# 1. Create trusted keys file
cat > trusted_keys.txt << EOF
# Add GPG key fingerprints (one per line)
ABCD1234567890ABCDEF1234567890ABCDEF12
1234567890ABCDEF1234567890ABCDEF123456
EOF

# 2. Run worker with task signing enabled
docker run -d \
  --name dgrid-worker \
  -e ENABLE_TASK_SIGNING=true \
  -e TRUSTED_KEYS_FILE=/app/trusted_keys.txt \
  -v $(pwd)/trusted_keys.txt:/app/trusted_keys.txt:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  fabriziosalmi/d-grid-worker:latest
```

#### 5. Restart Worker

```bash
# Docker
docker restart dgrid-worker

# Docker Compose
docker-compose restart dgrid-worker

# Check logs
docker logs -f dgrid-worker
```

Look for:
- "Using credential method: SSH key authentication (most secure)" ✅
- "Optimizations: Shallow Clone=True, Smart Polling=True" ✅
- "Task signing enabled with X trusted keys" (if enabled) ✅

### For Repository Owners

#### 1. Add GitHub Workflows

Copy new workflows to your repository:

```bash
# Archive old results monthly
.github/workflows/archive-results.yml

# Collect metrics every 5 minutes
.github/workflows/collect-metrics.yml
```

#### 2. Create Archive Directory

```bash
mkdir -p archive
echo "# D-GRID Archives" > archive/README.md
git add archive/
git commit -m "Add archive directory"
git push
```

#### 3. Create Metrics Directory

```bash
mkdir -p metrics
echo "{}" > metrics/current.json
git add metrics/
git commit -m "Add metrics directory"
git push
```

#### 4. Enable Task Sharding (Optional)

Migrate to priority-based queue structure:

```bash
# Create priority subdirectories
mkdir -p tasks/queue/{critical,high,medium,low}

# Each priority has 16 hash-based shards (0-9, a-f)
for priority in critical high medium low; do
  for shard in {0..9} {a..f}; do
    mkdir -p tasks/queue/$priority/$shard
  done
done

git add tasks/queue/
git commit -m "Add priority queue structure"
git push
```

Tasks can now be submitted to priority queues:
- `tasks/queue/critical/` - Highest priority
- `tasks/queue/high/` - High priority
- `tasks/queue/medium/` - Normal priority (default)
- `tasks/queue/low/` - Low priority

#### 5. Configure GitHub Pages

Enable the metrics dashboard:

1. Go to Settings → Pages
2. Source: Deploy from a branch
3. Branch: gh-pages / root
4. Save

Access at: `https://YOUR_USERNAME.github.io/dgrid/metrics.html`

### For Task Submitters

#### 1. Sign Tasks (if enabled)

When task signing is enabled, you must sign all tasks:

```bash
# 1. Create task file
cat > my-task.json << 'EOF'
{
  "task_id": "my-task-001",
  "script": "echo 'Hello D-GRID'",
  "timeout_seconds": 30,
  "priority": "medium"
}
EOF

# 2. Sign task
gpg --detach-sign --armor -o my-task.json.sig my-task.json

# 3. Submit both files
git add my-task.json my-task.json.sig
git commit -m "Add signed task: my-task-001"
git push
```

#### 2. Use Priority Queues (optional)

Submit tasks to specific priority levels:

```bash
# Critical priority (executed first)
git add tasks/queue/critical/urgent-task.json

# High priority
git add tasks/queue/high/important-task.json

# Medium priority (default)
git add tasks/queue/medium/normal-task.json

# Low priority (executed last)
git add tasks/queue/low/background-task.json
```

Or specify priority in task JSON:

```json
{
  "task_id": "my-task-001",
  "script": "echo 'Hello'",
  "timeout_seconds": 30,
  "priority": "high"
}
```

## Verification

### Check Worker Logs

```bash
docker logs dgrid-worker | grep -E "(Optimization|credential|signing|Health)"
```

Expected output:
```
✅ Configuration validated.
Using credential method: SSH key authentication (most secure)
Optimizations: Shallow Clone=True, Smart Polling=True
Rate Limit: 100 tasks/hour
✅ Node registered and ready.
✅ Health check passed - CPU: 25%, Memory: 40%, Disk: 30%
```

### Test Performance

Before upgrade:
```bash
time git clone https://github.com/user/repo.git
# ~15 seconds
```

After upgrade (shallow clone):
```bash
time git clone --depth 1 https://github.com/user/repo.git
# ~2 seconds (87% faster!)
```

### Monitor Metrics

Visit your metrics dashboard:
```
https://YOUR_USERNAME.github.io/dgrid/metrics.html
```

Check for:
- Active workers
- Queue depth
- Scaling recommendations
- Task completion rate

## Troubleshooting

### Worker Won't Start

**Symptom:** Worker exits immediately

**Solution:** Check logs for configuration errors
```bash
docker logs dgrid-worker
```

Common issues:
- Invalid `DGRID_REPO_URL`
- SSH keys not mounted
- Missing required environment variables

### Tasks Not Being Picked Up

**Symptom:** Tasks stay in queue

**Solutions:**

1. **Check task signing:**
   ```bash
   # If signing enabled, ensure tasks are signed
   ls tasks/queue/*.sig
   ```

2. **Check worker logs:**
   ```bash
   docker logs dgrid-worker | grep -i signature
   ```

3. **Verify SSH access:**
   ```bash
   docker exec dgrid-worker ssh -T git@github.com
   ```

### High Resource Usage

**Symptom:** Worker consuming too much CPU/memory

**Solution:** Adjust resource quotas
```yaml
environment:
  MAX_CPU_PERCENT: "60"
  MAX_MEMORY_PERCENT: "60"
  MAX_TASKS_PER_HOUR: "50"
  DOCKER_CPUS: "1"
  DOCKER_MEMORY: "512m"
```

### Signature Verification Fails

**Symptom:** "Task signature verification failed"

**Solutions:**

1. **Verify GPG key is trusted:**
   ```bash
   cat /app/trusted_keys.txt
   ```

2. **Re-sign task:**
   ```bash
   gpg --detach-sign --armor -o task.json.sig task.json
   ```

3. **Check GPG key ID:**
   ```bash
   gpg --list-keys
   ```

## Rollback

If you encounter issues, you can rollback:

### 1. Revert to Previous Version

```bash
# Use specific version tag
docker run fabriziosalmi/d-grid-worker:v1.0.0

# Or use your backup configuration
docker-compose -f docker-compose.backup.yml up -d
```

### 2. Disable New Features

```yaml
environment:
  USE_SHALLOW_CLONE: "false"
  USE_SMART_POLLING: "false"
  ENABLE_TASK_SIGNING: "false"
```

### 3. Restore Configuration

```bash
# Revert to HTTPS + token
DGRID_REPO_URL: https://github.com/user/repo.git
GIT_TOKEN: ghp_your_token
```

## Migration Checklist

- [ ] Update worker Docker image
- [ ] Add new environment variables
- [ ] Migrate to SSH authentication (recommended)
- [ ] Enable task signing (recommended for production)
- [ ] Add GitHub workflows (archive, metrics)
- [ ] Create archive and metrics directories
- [ ] Enable GitHub Pages for metrics
- [ ] Test worker startup
- [ ] Verify task execution
- [ ] Monitor performance improvements
- [ ] Update documentation

## Support

If you need help:

1. Check logs: `docker logs dgrid-worker`
2. Review documentation: `SECURITY.md`, `PERFORMANCE.md`
3. Open an issue on GitHub
4. Join discussions

## Next Steps

After upgrading:

1. **Monitor metrics** - Check scaling recommendations
2. **Review security** - Ensure signing is enabled for production
3. **Optimize configuration** - Tune quotas and thresholds
4. **Plan scaling** - Add/remove workers based on metrics
5. **Archive results** - Let automated archival maintain performance

## References

- [SECURITY.md](SECURITY.md) - Security guide
- [PERFORMANCE.md](PERFORMANCE.md) - Performance optimization
- [README.md](README.md) - General documentation
- [GitHub Workflows](.github/workflows/) - Automation
