# D-GRID Copilot Instructions

## Project Overview

D-GRID is a decentralized Git-Relay Infrastructure for Distributed Task execution. It uses Git/GitHub as a transactional distributed state database, enabling serverless, decentralized task execution without central dependencies.

### Core Concepts
- **Git as Database**: All system state (nodes, tasks, results) tracked in GitHub as single source of truth
- **Autonomous Workers**: Python workers in Docker containers that self-register and execute tasks
- **Atomic Operations**: Git operations ensure race-condition-free task acquisition
- **Zero Infrastructure**: Works with GitHub's free tier (Actions, Pages, API)

## Architecture

### Directory Structure
```
d-grid/
├── .github/
│   ├── workflows/          # GitHub Actions for validation and dashboard
│   └── scripts/            # Dashboard generation scripts
├── nodes/                  # Active node registry (JSON files)
├── tasks/
│   ├── queue/             # Pending tasks
│   ├── in_progress/       # Running tasks (atomically acquired)
│   ├── completed/         # Successful tasks
│   └── failed/            # Failed tasks
├── worker/                # Python worker implementation
│   ├── main.py           # Entry point
│   ├── config.py         # Configuration and validation
│   ├── git_handler.py    # Git operations
│   ├── state_manager.py  # Node registration & heartbeat
│   ├── task_runner.py    # Task execution in Docker
│   └── web_server.py     # Local worker dashboard
├── docs/                  # GitHub Pages dashboard
└── Dockerfile            # Worker container image
```

## Technology Stack

- **Language**: Python 3.11+
- **Containerization**: Docker Alpine-based images
- **Coordination**: Git for distributed state management
- **Dependencies**: GitPython (3.1.41), psutil (5.9.6)
- **CI/CD**: GitHub Actions
- **Dashboard**: GitHub Pages with auto-generated HTML

## Coding Standards

### Python Code Style
- Use type hints where appropriate
- Follow PEP 8 style guidelines
- Keep functions focused and single-purpose
- Use descriptive variable names
- Add docstrings for classes and public methods

### Error Handling
- Use specific exception types
- Always log errors with context
- Implement retry logic for transient failures (e.g., Git operations)
- Never expose sensitive information in error messages

### Git Operations
- Always use atomic operations (`git mv`) for task state transitions
- Pull with rebase before any push operation
- Handle merge conflicts gracefully
- Use descriptive commit messages

### Security Considerations
- **Container Isolation**: Tasks execute in isolated Docker containers with:
  - No network access (network=none)
  - Read-only filesystem where possible
  - Limited user privileges (uid=1000:1000)
- **Input Validation**: All task JSON files must be validated
- **Output Limits**: Task output limited to 10KB to prevent DoS
- **No Secrets in Code**: Use environment variables for credentials
- Never commit GitHub tokens or sensitive data

## Building and Testing

### Local Development Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd worker
pip install -r requirements.txt

# Run worker locally (requires Docker)
python main.py
```

### Docker Build
```bash
# Build worker image
docker build -t dgrid-worker:local .

# Run with environment variables
docker run -d \
  -e NODE_ID=test-worker \
  -e DGRID_REPO_URL=https://github.com/user/repo.git \
  -e GIT_TOKEN=ghp_token \
  -v /var/run/docker.sock:/var/run/docker.sock \
  dgrid-worker:local
```

### Testing
- No formal test suite yet (MVP phase)
- Manual testing required for worker functionality
- Test with demo tasks in `tasks/queue/`
- Verify task execution through worker logs and dashboard

## Key Configuration

### Environment Variables (worker/config.py)
- `NODE_ID`: Unique identifier for worker node
- `DGRID_REPO_URL`: Git repository URL
- `GIT_TOKEN`: GitHub personal access token
- `PULL_INTERVAL`: Seconds between Git pulls (default: 10)
- `HEARTBEAT_INTERVAL`: Seconds between heartbeats (default: 60)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Task Format
Tasks are JSON files in `tasks/queue/`:
```json
{
  "task_id": "unique-task-id",
  "script": "echo 'Hello' && python3 --version",
  "timeout_seconds": 30
}
```

## Common Patterns

### Adding New Features to Worker
1. Create focused module in `worker/` directory
2. Import in `main.py` and integrate with main loop
3. Update configuration in `config.py` if needed
4. Add logging using the configured logger
5. Handle exceptions and edge cases
6. Update README.md with feature documentation

### Modifying Task Execution
1. Changes go in `worker/task_runner.py`
2. Maintain Docker isolation and security constraints
3. Preserve atomic Git operations for state transitions
4. Update output size limits if necessary
5. Test with various task types

### Dashboard Changes
1. Modify `docs/index.html` for frontend
2. Update `.github/scripts/generate_dashboard.py` for backend
3. Ensure GitHub Actions workflow generates correctly
4. Test locally before committing

## Git Workflow

### For Contributors
1. Fork the repository
2. Create feature branch from `main`
3. Make focused, minimal changes
4. Test changes locally
5. Submit pull request with clear description
6. Address review feedback

### For Task Submission
1. Create JSON file in `tasks/queue/`
2. Commit and push to trigger validation
3. GitHub Actions validates format
4. Workers automatically pick up valid tasks

## Dependencies Management

### Adding Python Dependencies
1. Add to `worker/requirements.txt`
2. Pin specific versions for reproducibility
3. Update Dockerfile if system packages needed
4. Consider Alpine Linux compatibility
5. Document reason for new dependency

### Security Updates
- Monitor for security advisories
- Update dependencies promptly
- Test thoroughly after updates
- Document breaking changes

## Performance Considerations

- Workers should complete tasks within timeout (default 30s)
- Git operations include retry logic (max 5 attempts)
- Heartbeat prevents worker timeout (every 60s)
- Task output size limited to prevent memory issues
- Pull interval balances responsiveness vs. API limits

## Troubleshooting Common Issues

### Worker Won't Start
- Verify all required environment variables are set
- Check Docker socket access
- Validate Git credentials for private repos
- Review logs with LOG_LEVEL=DEBUG

### Tasks Not Being Picked Up
- Verify task JSON format is valid
- Check GitHub Actions validation passed
- Ensure worker is pulling successfully
- Review worker logs for errors

### Git Conflicts
- Workers automatically retry with backoff
- Check for concurrent modifications
- Verify Git configuration is correct

## Future Development Priorities

1. Add comprehensive test suite
2. Implement task signing and verification
3. Add rate limiting per worker
4. Develop task dependency management
5. Create worker reputation system
6. Build web UI for task submission

## Additional Resources

- [Main README](../README.md) - Complete project documentation
- [Development Progress](../progress.md) - Current development status
- [Worker Configuration](../worker/config.py) - All config options
- [GitHub Actions](.github/workflows/) - CI/CD pipelines
