# D-GRID Security Guide

## Overview

This guide covers the security enhancements implemented in D-GRID Phase 1 and Phase 2 improvements.

## Phase 1: Security Basics

### Container Isolation

All tasks execute in isolated Docker containers with strict security:

```bash
docker run \
  --network=none \       # No network access
  --read-only \          # Read-only filesystem
  --user=1000:1000 \     # Non-root user
  --pids-limit=10 \      # Limited processes
  --cpus=1 \             # CPU limits
  --memory=512m \        # Memory limits
  python:3.11-alpine sh -c "$TASK_SCRIPT"
```

### Output Limits

Task output is limited to 10KB to prevent DoS attacks:
- stdout: max 10KB
- stderr: max 10KB

### Resource Quotas (#10)

Workers can be configured with resource quotas:

```bash
# Limit tasks per hour
MAX_TASKS_PER_HOUR=100

# System resource thresholds
MAX_CPU_PERCENT=80
MAX_MEMORY_PERCENT=80
```

When limits are reached, workers skip task execution and send heartbeats instead.

## Phase 2: Security Hardening

### Secure Credential Management (#12)

**CRITICAL**: Never store Git tokens in plain environment variables!

#### Recommended: SSH Key Authentication

1. Generate SSH key:
```bash
ssh-keygen -t ed25519 -C "worker@dgrid"
```

2. Add public key to GitHub:
   - Settings → SSH and GPG keys → New SSH key
   - Paste contents of `~/.ssh/id_ed25519.pub`

3. Update repository URL:
```bash
DGRID_REPO_URL=git@github.com:user/repo.git
```

#### Alternative: Git Credential Helper

For HTTPS repositories, use Git credential helper:

```bash
# Cache credentials for 1 hour
git config --global credential.helper 'cache --timeout=3600'

# Or store in OS keychain (macOS)
git config --global credential.helper osxkeychain

# Or store in OS keychain (Linux)
git config --global credential.helper libsecret
```

#### Alternative: GitHub App Token

Use GitHub App tokens for better security:

```bash
GITHUB_APP_TOKEN=ghs_your_app_token_here
```

#### Legacy: Environment Token (Not Recommended)

```bash
GIT_TOKEN=ghp_your_token_here
```

**⚠️ WARNING**: This method exposes tokens in process environment. Use only for testing.

#### Credential Method Priority

The system automatically detects and uses credentials in this order:
1. SSH keys (most secure)
2. Git credential helper
3. GitHub App token
4. Environment token (legacy, least secure)

### Task Signing & Verification (#9)

**CRITICAL**: Enable task signing to prevent malicious task injection!

#### Setup

1. Enable task signing:
```bash
ENABLE_TASK_SIGNING=true
```

2. Create trusted keys file:
```bash
# Add GPG key fingerprints (one per line)
cat > /app/trusted_keys.txt << EOF
ABCD1234567890ABCDEF1234567890ABCDEF12
1234567890ABCDEF1234567890ABCDEF123456
EOF
```

3. Configure trusted keys file location:
```bash
TRUSTED_KEYS_FILE=/app/trusted_keys.txt
```

#### Signing Tasks

Task submitters must sign their tasks with GPG:

```bash
# Sign task file
gpg --detach-sign --armor -o task-001.json.sig task-001.json

# Submit both files
git add task-001.json task-001.json.sig
git commit -m "Add signed task"
git push
```

#### Verification Process

Workers automatically verify signatures:
1. Check if signature file exists (`.json.sig`)
2. Verify signature with GPG
3. Extract signer's key fingerprint
4. Check if fingerprint is in trusted keys list
5. Reject task if any check fails

#### Managing Trusted Keys

Add trusted key:
```python
from task_signing import get_task_signer
signer = get_task_signer()
signer.add_trusted_key("ABCD1234567890ABCDEF1234567890ABCDEF12")
```

Remove trusted key:
```python
signer.remove_trusted_key("ABCD1234567890ABCDEF1234567890ABCDEF12")
```

#### Security Impact

When task signing is enabled:
- ✅ Only tasks from trusted keys are executed
- ✅ Prevents unauthorized task injection
- ✅ Provides task authenticity and integrity
- ❌ Requires GPG setup for task submitters
- ❌ Additional overhead for signature verification

When disabled (default):
- ⚠️ Anyone with write access can submit tasks
- ⚠️ No authentication or integrity checking
- ✅ Simpler workflow
- ✅ No GPG dependencies

### Container Image Verification (#11)

**TODO**: This feature is planned for future implementation.

Planned capabilities:
- Hash-based allowlist for container images
- Vulnerability scanning integration
- Automatic image verification before execution

## Security Best Practices

### For Repository Owners

1. **Enable task signing** for production deployments
2. **Use private repositories** for sensitive workloads
3. **Limit write access** to repository
4. **Monitor task submissions** via GitHub Actions
5. **Review worker logs** regularly
6. **Use SSH keys** for worker authentication

### For Workers

1. **Use SSH keys** instead of tokens
2. **Enable task signing** verification
3. **Set resource quotas** to prevent abuse
4. **Monitor system resources** via health checks
5. **Run workers** in isolated environments (containers, VMs)
6. **Update regularly** to get security patches

### For Task Submitters

1. **Sign all tasks** with GPG (when enabled)
2. **Use minimal scripts** - only what's necessary
3. **Avoid sensitive data** in task scripts
4. **Test tasks locally** before submission
5. **Review task results** for anomalies

## Security Configuration Summary

```bash
# Phase 1: Basic Security (Already Implemented)
DOCKER_CPUS=1
DOCKER_MEMORY=512m
DOCKER_TIMEOUT=300
MAX_TASKS_PER_HOUR=100
MAX_CPU_PERCENT=80
MAX_MEMORY_PERCENT=80

# Phase 2: Advanced Security
# Credential Management
DGRID_REPO_URL=git@github.com:user/repo.git  # Use SSH
# Or configure credential helper (see above)

# Task Signing
ENABLE_TASK_SIGNING=true
TRUSTED_KEYS_FILE=/app/trusted_keys.txt
```

## Security Incident Response

If you suspect a security incident:

1. **Stop all workers** immediately
2. **Review recent task submissions** in Git history
3. **Check worker logs** for anomalies
4. **Revoke compromised credentials** (tokens, keys)
5. **Update trusted keys list** if needed
6. **Review and update security settings**
7. **Report to repository owners**

## Security Roadmap

### Completed
- ✅ Container isolation (Phase 1)
- ✅ Output limits (Phase 1)
- ✅ Resource quotas (Phase 1)
- ✅ Secure credential management (Phase 2)
- ✅ Task signing & verification (Phase 2)

### Planned
- [ ] Container image verification (Phase 2)
- [ ] Consensus mechanism (Phase 5)
- [ ] Worker reputation system (Phase 5)
- [ ] End-to-end encryption for results
- [ ] Audit logging
- [ ] Intrusion detection

## References

- [GPG Quick Start](https://www.gnupg.org/gph/en/manual.html)
- [GitHub SSH Setup](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [Git Credential Storage](https://git-scm.com/docs/gitcredentials)
- [Docker Security](https://docs.docker.com/engine/security/)

## Reporting a Vulnerability

We take the security of D-GRID seriously. If you believe you have found a security vulnerability, please report it to us as described below.

**Please do not report security vulnerabilities through public GitHub issues.**

### Reporting Process

1.  Email your findings to [fabrizio.salmi@gmail.com](mailto:fabrizio.salmi@gmail.com).
2.  Include a detailed description of the vulnerability, steps to reproduce, and potential impact.
3.  We will acknowledge receipt of your report within 48 hours.
4.  We will work with you to assess the issue and determine a timeline for a fix.
5.  Once a fix is released, we will credit you in our release notes (unless you prefer to remain anonymous).

### Scope

The following are in scope for security reports:
-   Worker node remote code execution vulnerabilities.
-   Task isolation bypasses.
-   Git history manipulation vulnerabilities.
-   Dashboard XSS vulnerabilities.

The following are out of scope:
-   DDoS attacks on the GitHub infrastructure itself.
-   Social engineering attacks.
-   Vulnerabilities in third-party dependencies (unless they are directly exploitable in D-GRID).
