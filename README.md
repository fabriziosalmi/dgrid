# D-GRID: Decentralized Git-Relay Infrastructure for Distributed Tasks

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-Latest-blue?logo=docker)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue?logo=github)](https://github.com/features/actions)

> Use Git as a transactional and distributed state database for decentralized task execution.

## Table of Contents

-   [Vision](#vision)
-   [Architecture](#architecture)
-   [Technology Stack](#technology-stack)
-   [How It Works](#how-it-works)
-   [Directory Structure](#directory-structure)
-   [Task Format](#task-format)
-   [Key Features](#key-features)
-   [Security](#security)
-   [Quick Start](#quick-start)
-   [Dashboard](#dashboard)
-   [Roadmap](#roadmap)
-   [Contributing](#contributing)
-   [Documentation](#documentation)
-   [Troubleshooting](#troubleshooting)
-   [License](#license)
-   [FAQ](#faq)

## Vision

D-GRID is a **serverless, decentralized task execution system** where:

-   **Git as Database**: All system state (nodes, tasks, results) is tracked on GitHub as the single source of truth.
-   **Auto-Generated Dashboard**: Public, real-time status dashboard on GitHub Pages.
-   **Autonomous Worker Nodes**: Python workers in Docker containers that self-register, execute tasks, and report results.
-   **Zero Central Dependencies**: No central APIs, no external databases, no orchestrators needed.

## Architecture

```mermaid
graph TD
    subgraph GitHub["GitHub Repository (Single Source of Truth)"]
        Nodes["nodes/ (Registry)"]
        Queue["tasks/queue/ (Pending)"]
        InProgress["tasks/in_progress/ (Running)"]
        Completed["tasks/completed/ (Success)"]
        Failed["tasks/failed/ (Failed)"]
    end

    subgraph Workers["Worker Nodes"]
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker 3]
    end

    subgraph Actions["GitHub Actions"]
        Validator[Task Validator]
        Generator[Dashboard Generator]
    end

    subgraph Pages["GitHub Pages"]
        Dashboard[Status Dashboard]
    end

    W1 <-->|Pull/Push| GitHub
    W2 <-->|Pull/Push| GitHub
    W3 <-->|Pull/Push| GitHub

    GitHub -->|Trigger| Actions
    Actions -->|Generate| Pages
```

## Technology Stack

| Component | Technology | Why |
| :--- | :--- | :--- |
| **Worker Node** | Python 3.11 | Fast development, mature libraries, great community |
| **Containerization** | Docker Alpine | Lightweight (~150MB), secure, includes Python |
| **Coordination** | Git + GitHub | Single source of truth, decentralized, built-in history |
| **Dashboard** | GitHub Pages + HTML | Free, integrated, no extra infrastructure |
| **CI/CD** | GitHub Actions | Free, serverless, GitHub-native |

## How It Works

### 1. Worker Node Lifecycle

```mermaid
sequenceDiagram
    participant W as Worker
    participant G as GitHub Repo
    
    Note over W: Start (docker run)
    W->>G: Clone/Pull Repo
    W->>G: Register (nodes/{id}.json)
    
    loop Main Loop
        W->>G: Pull (Rebase)
        alt Task Available?
            W->>G: git mv queue -> in_progress (Atomic)
            alt Success
                Note over W: Execute Task (Docker)
                W->>G: Push Result (completed/failed)
            else Conflict
                Note over W: Retry
            end
        else No Task
            W->>G: Send Heartbeat
        end
        Note over W: Sleep (PULL_INTERVAL)
    end
```

### 2. Task Submission Flow

1.  Fork Repository.
2.  Create task in `tasks/queue/`.
3.  Open Pull Request.
4.  Merge (auto-validated).
5.  GitHub Actions scans state.
6.  Worker node finds task.
7.  Execution.
8.  Result pushed back.

## Directory Structure

```text
d-grid/
├── .github/
│   └── workflows/
│       ├── process-task-pr.yml     # Validate task submissions
│       └── update-gh-pages.yml     # Generate dashboard & cleanup
├── nodes/
│   └── {node_id}.json              # State of each node
├── tasks/
│   ├── queue/                      # Pending tasks
│   ├── in_progress/                # Running tasks (atomic acquisition)
│   ├── completed/                  # Successfully completed tasks
│   └── failed/                     # Failed tasks
├── worker/
│   ├── main.py                     # Worker entry point
│   ├── config.py                   # Configuration & validation
│   ├── logger_config.py            # Unified logging
│   ├── git_handler.py              # Git operations
│   ├── state_manager.py            # Node registration & heartbeat
│   ├── task_runner.py              # Task execution
│   ├── web_server.py               # Local worker dashboard
│   └── requirements.txt            # Python dependencies
├── docs/
│   └── index.html                  # GitHub Pages dashboard
├── tests/                          # Unit tests
├── .gitignore
├── Dockerfile                       # Worker image build
├── docker-compose.yml              # Local development setup
├── README.md                        # This file
├── CONTRIBUTING.md                  # Contribution guidelines
├── CHANGELOG.md                     # Version history
└── LICENSE                          # MIT License
```

## Task Format

Submit tasks as JSON files in `tasks/queue/`:

```json
{
  "task_id": "task-001",
  "script": "echo 'Hello, D-GRID!' && python3 --version",
  "timeout_seconds": 30
}
```

Task results are stored in `tasks/completed/{node_id}-{task_id}.json`:

```json
{
  "task_id": "task-001",
  "node_id": "worker-001",
  "exit_code": 0,
  "stdout": "Hello, D-GRID!\nPython 3.11.0",
  "stderr": "",
  "timestamp": "2025-10-16T10:01:23Z",
  "status": "success"
}
```

## Key Features

-   **Atomic Operations**: Uses `git mv` for transactional task acquisition (no race conditions).
-   **Self-Healing**: Auto-detects orphaned tasks and moves them back to queue.
-   **Isolated Execution**: Docker containers with strict security (network=none, read-only FS, limited processes).
-   **Real-Time Dashboard**: Auto-generated, always up-to-date status view.
-   **Zero Infrastructure**: Works with free GitHub tier (no servers, no databases).
-   **Worker Autonomy**: Nodes self-register and heartbeat without central coordination.
-   **Full Transparency**: All state visible in Git history.

## Security

Production-ready security implementation:

-   ✅ Container isolation (network=none, read-only, user=1000:1000, pids-limit).
-   ✅ Fixed base image (python:3.11-alpine, not customizable).
-   ✅ Output limits (10KB max per task to prevent DoS).
-   ✅ JSON validation and required fields.
-   ✅ Task submission validation via GitHub Actions.
-   ✅ **Task signing & verification** - GPG-based authentication (optional, see [SECURITY.md](SECURITY.md)).
-   ✅ **Rate limiting per worker** - Configurable hourly task limits (MAX_TASKS_PER_HOUR).
-   ✅ **Resource quotas** - CPU/memory thresholds prevent system overload.

Advanced hardening in progress:

-   ⚠️ **Enhanced container sandboxing** - Basic isolation implemented, advanced features (seccomp profiles, AppArmor) planned.
-   🔮 **Multi-signature quorum** - Planned for Phase 5 (distributed consensus for critical operations).

### Security Configuration

Enable task signing for production deployments:

```bash
# Require GPG signatures on all tasks
ENABLE_TASK_SIGNING=true
TRUSTED_KEYS_FILE=/app/trusted_keys.txt

# Rate limiting (0 = unlimited)
MAX_TASKS_PER_HOUR=100

# Resource thresholds
MAX_CPU_PERCENT=80
MAX_MEMORY_PERCENT=80
```

For complete security documentation, see [SECURITY.md](SECURITY.md).

## Quick Start

### Prerequisites

-   GitHub account and a public repository.
-   Docker installed (for running workers).
-   Python 3.11+ (for local development).
-   Git CLI.

### For Repository Maintainers

```bash
# 1. Create a new repository on GitHub
# 2. Clone it locally
git clone https://github.com/<your-username>/d-grid.git
cd d-grid

# 3. Enable GitHub Pages
#    Settings → Pages → Source: gh-pages branch

# 4. Enable GitHub Actions
#    Settings → Actions → Allow all actions

# 5. Create a GitHub Personal Access Token (if needed for private repos)
#    Settings → Developer settings → Personal access tokens
#    Keep this secret!
```

### For Workers (Start a Node)

#### Using Docker (Recommended)

```bash
docker run -d   --name dgrid-worker-001   -e NODE_ID=worker-001   -e DGRID_REPO_URL=https://github.com/<your-username>/d-grid.git   -e GIT_TOKEN=ghp_your_token_here   -e PULL_INTERVAL=10   -e LOG_LEVEL=INFO   -v /var/run/docker.sock:/var/run/docker.sock   -p 8000:8000   fabriziosalmi/d-grid-worker:latest
```

Then check the dashboard at `http://localhost:8000`.

#### Using Docker Compose (Development)

```bash
# Clone the repository
git clone https://github.com/<your-username>/d-grid.git
cd d-grid

# Configure environment in docker-compose.yml
# Then start:
docker-compose up -d

# Check logs:
docker-compose logs -f dgrid-worker
```

#### Local Python (Development Only)

```bash
cd worker
pip install -r requirements.txt
python main.py
```

### Submitting Tasks

1.  **Fork the repository**

    ```bash
    git clone https://github.com/<your-username>/d-grid.git
    cd d-grid
    ```

2.  **Create a task file**

    ```bash
    cat > tasks/queue/my-first-task.json << 'EOF'
    {
      "task_id": "my-first-task",
      "script": "echo 'Hello from D-GRID!' && python3 --version",
      "timeout_seconds": 30
    }
    EOF
    ```

3.  **Commit and push**

    ```bash
    git add tasks/queue/my-first-task.json
    git commit -m "Add task: my-first-task"
    git push origin main
    ```

4.  **Monitor execution**

    Visit your dashboard at: `https://<your-username>.github.io/d-grid/`

    Results appear in `tasks/completed/` or `tasks/failed/` depending on outcome.

## Dashboard

Access your real-time dashboard at: `https://<your-username>.github.io/d-grid/`

**Dashboard shows:**

-   🟢 Active nodes (with last heartbeat time).
-   ⏳ Pending tasks in queue.
-   🔄 Currently executing tasks.
-   ✅ Successfully completed tasks.
-   ❌ Failed tasks.

The dashboard updates every 60 seconds and regenerates every 5 minutes via GitHub Actions.

## Roadmap

### Phase 1: ✅ Foundations (COMPLETE)

-   [x] Worker node core implementation.
-   [x] State manager (node registration & heartbeat).
-   [x] Task runner with Docker execution.
-   [x] Git coordination and atomic operations.
-   [x] Robust error handling and recovery.

### Phase 2: ✅ Security Hardening (COMPLETE)

-   [x] Task signing & verification (GPG-based).
-   [x] Rate limiting per worker.
-   [x] Resource quotas (CPU/memory thresholds).
-   [x] Secure credential management (SSH keys, credential helpers).
-   [x] Container image verification planning.

### Phase 3: 🚧 GitHub Actions & Automation (IN PROGRESS)

-   [x] Task submission validator.
-   [x] Dashboard generator.
-   [x] Orphan task cleanup.
-   [ ] Auto-scaling recommendations.
-   [ ] Performance metrics collection.

### Phase 4: 🎯 Deployment & Release

-   [ ] Publish Docker image to registries.
-   [ ] Enhanced documentation.
-   [ ] Example tasks and templates.
-   [ ] Public launch.

### Phase 5: 🔮 Advanced Features (Future)

-   [ ] End-to-end test suite.
-   [ ] Enhanced container sandboxing (seccomp profiles, AppArmor).
-   [ ] Multi-signature quorum for critical operations.
-   [ ] Task dependency management.
-   [ ] Worker reputation system.
-   [ ] Task priority levels.
-   [ ] Distributed consensus mechanisms.
-   [ ] Web UI for task submission.

## Contributing

Everyone can contribute! The easiest way is to launch a worker node:

```bash
docker run -e DGRID_REPO_URL=https://github.com/<repo>            -e NODE_ID=my-worker            -v /var/run/docker.sock:/var/run/docker.sock            fabriziosalmi/d-grid-worker:latest
```

You can also:

-   **Submit tasks** by creating JSON files in `tasks/queue/`.
-   **Improve code** by forking and submitting pull requests.
-   **Report issues** on the GitHub issue tracker.
-   **Suggest improvements** in discussions.

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

### Development Setup

```bash
# Clone and setup
git clone https://github.com/<your-fork>/d-grid.git
cd d-grid

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd worker
pip install -r requirements.txt

# Run locally (requires Docker)
python main.py
```

## Documentation

-   **[Worker Configuration](worker/config.py)** - All environment variables explained.
-   **[Task Format Specification](tasks/queue/demo-task-001.json)** - Create valid tasks.
-   **[Architecture Deep Dive](README.md#architecture)** - Understand how it works.
-   **[Development Progress](progress.md)** - Track ongoing development.

## Troubleshooting

**Worker won't start:**

```bash
# Check configuration validation
LOG_LEVEL=DEBUG python worker/main.py

# Verify Docker is running
docker ps

# Check Git credentials (if private repo)
git config credential.helper
```

**Tasks aren't being picked up:**

```bash
# Check repository sync
cd /tmp/d-grid-repo && git log --oneline -5

# Verify task format
cat tasks/queue/*.json | python3 -m json.tool

# Check worker logs
docker logs dgrid-worker-001
```

**Dashboard not updating:**

-   Verify GitHub Actions is enabled in Settings.
-   Check Actions tab for workflow run history.
-   Ensure GitHub Pages is configured in Settings.

## Support & Community

-   **Issues**: Report bugs on [GitHub Issues](../../issues).
-   **Discussions**: Ask questions in [GitHub Discussions](../../discussions).
-   **Wiki**: Additional info in [GitHub Wiki](../../wiki).

## License

MIT License - Feel free to use, experiment, and build your own D-GRID!

See [LICENSE](LICENSE) for full terms.

## Acknowledgments

Built with:

-   ❤️ Passion for decentralization.
-   🔧 Python, Git, and Docker.
-   🚀 GitHub's free tier (Actions, Pages, API).
-   🌟 Open source community.

---

## FAQ

**Q: Does this work without Internet?**
A: No, it requires connectivity to GitHub. It's designed for cloud/internet deployments.

**Q: Can I use this for production workloads?**
A: Currently MVP. For production, add the security hardening listed in the Security section.

**Q: How many workers can I run?**
A: Unlimited! Each worker is independent and only needs the repo URL.

**Q: What happens if GitHub is down?**
A: Workers will retry until connectivity is restored. No data is lost since Git stores everything.

**Q: Can I run on Kubernetes?**
A: Yes! Deploy workers as Kubernetes jobs that pull tasks from the Git repo.

**Q: How do I scale this?**
A: Run more worker containers. They auto-coordinate via Git atomic operations.
