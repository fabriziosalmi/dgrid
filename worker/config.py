"""
D-GRID Worker Configuration Module
Manages all global configuration for the worker node.
"""
import os
import socket
import json
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None

# === Git Repository Configuration ===
REPO_URL = os.getenv("DGRID_REPO_URL", "https://github.com/fabriziopandini/d-grid.git")
REPO_PATH = os.getenv("DGRID_REPO_PATH", "/tmp/d-grid-repo")

# === Node Configuration ===
NODE_ID = os.getenv("NODE_ID", socket.gethostname())
NODE_NAME = os.getenv("NODE_NAME", f"worker-{NODE_ID}")

# === Git Credentials ===
GIT_USER_NAME = os.getenv("GIT_USER_NAME", "D-GRID Worker")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", f"worker+{NODE_ID}@d-grid.local")
GIT_TOKEN = os.getenv("GIT_TOKEN", None)  # For HTTPS authentication

# === Docker Configuration ===
DOCKER_CPUS = os.getenv("DOCKER_CPUS", "1")
DOCKER_MEMORY = os.getenv("DOCKER_MEMORY", "512m")
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "3600"))  # seconds

# === Worker Loop Configuration ===
PULL_INTERVAL = int(os.getenv("PULL_INTERVAL", "10"))  # seconds between pulls
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "60"))  # seconds between heartbeats

# === Performance & Optimization (Phase 1 Improvements) ===
USE_SHALLOW_CLONE = os.getenv("USE_SHALLOW_CLONE", "true").lower() == "true"  # #5: Optimize Git Ops
USE_SMART_POLLING = os.getenv("USE_SMART_POLLING", "true").lower() == "true"  # #6: Local Task Cache
MAX_PARALLEL_TASKS = int(os.getenv("MAX_PARALLEL_TASKS", "1"))  # #7: Parallel execution (Phase 3)

# === Resource Quotas & Rate Limiting (#10) ===
MAX_TASKS_PER_HOUR = int(os.getenv("MAX_TASKS_PER_HOUR", "0"))  # 0 = unlimited
MAX_CPU_PERCENT = int(os.getenv("MAX_CPU_PERCENT", "80"))  # Maximum CPU usage threshold
MAX_MEMORY_PERCENT = int(os.getenv("MAX_MEMORY_PERCENT", "80"))  # Maximum memory usage threshold

# === Logging ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "/tmp/d-grid-worker.log")

# === Node Specs (for registration) ===
def get_node_specs():
    """
    Returns node specs (CPU, RAM, etc).
    If psutil is not available, returns conservative fallback values.
    """
    try:
        if psutil is None:
            raise ImportError("psutil not available")
        
        return {
            "node_id": NODE_ID,
            "node_name": NODE_NAME,
            "cpu_count": psutil.cpu_count(logical=False) or 1,
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "disk_gb": round(psutil.disk_usage("/").total / (1024**3), 2),
        }
    except Exception as e:
        # Fallback: minimal specs if psutil is not available or system is anomalous
        return {
            "node_id": NODE_ID,
            "node_name": NODE_NAME,
            "cpu_count": 1,
            "memory_gb": 0.5,
            "disk_gb": 10.0,
        }

def get_git_auth_url():
    """
    Returns the Git authentication URL.
    
    ⚠️  SECURITY WARNING ⚠️
    If GIT_TOKEN is used, the URL will contain the token in plaintext.
    NEVER log this full URL. Use this function only in private contexts
    (e.g., inside subprocess with stderr/stdout managed).
    
    Preferably use SSH with keys instead of HTTPS + token.
    """
    if GIT_TOKEN and REPO_URL.startswith("https://"):
        # Construct URL with token (used only in private contexts)
        url = REPO_URL.replace("https://", f"https://x-access-token:{GIT_TOKEN}@")
        return url
    return REPO_URL

def validate_config():
    """
    Validates configuration at worker startup.
    Returns a list of errors (empty if all OK).
    """
    errors = []
    
    # Validate REPO_URL
    if not REPO_URL or not REPO_URL.startswith(("https://", "git@", "file://")):
        errors.append(f"DGRID_REPO_URL invalid: '{REPO_URL}'. Must start with https://, git@, or file://")
    
    # Validate NODE_ID
    if not NODE_ID or NODE_ID.strip() == "":
        errors.append("NODE_ID cannot be empty. Set via env var or hostname fallback.")
    
    # Validate intervals
    if PULL_INTERVAL < 1:
        errors.append(f"PULL_INTERVAL must be >= 1s, found: {PULL_INTERVAL}s")
    
    if PULL_INTERVAL > 3600:
        errors.append(f"PULL_INTERVAL seems too high: {PULL_INTERVAL}s (max recommended: 3600s)")
    
    if HEARTBEAT_INTERVAL < 1:
        errors.append(f"HEARTBEAT_INTERVAL must be >= 1s, found: {HEARTBEAT_INTERVAL}s")
    
    if HEARTBEAT_INTERVAL < PULL_INTERVAL:
        errors.append(f"HEARTBEAT_INTERVAL ({HEARTBEAT_INTERVAL}s) < PULL_INTERVAL ({PULL_INTERVAL}s). Heartbeat should be less frequent than pull.")
    
    # Validate Docker timeout
    if DOCKER_TIMEOUT < 5:
        errors.append(f"DOCKER_TIMEOUT must be >= 5s, found: {DOCKER_TIMEOUT}s")
    
    # Validate Docker resources
    try:
        float(DOCKER_CPUS)
    except (ValueError, TypeError):
        errors.append(f"DOCKER_CPUS is not a valid number: '{DOCKER_CPUS}'")
    
    if DOCKER_MEMORY not in ["512m", "1g", "2g", "4g", "8g", "16g"] and not DOCKER_MEMORY.endswith(("m", "g")):
        errors.append(f"DOCKER_MEMORY format not recognized: '{DOCKER_MEMORY}' (use: 512m, 1g, 2g, etc.)")
    
    # Validate LOG_LEVEL
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if LOG_LEVEL not in valid_levels:
        errors.append(f"LOG_LEVEL invalid: '{LOG_LEVEL}'. Use one of: {', '.join(valid_levels)}")
    
    # Validate Phase 1 improvements
    if MAX_PARALLEL_TASKS < 1:
        errors.append(f"MAX_PARALLEL_TASKS must be >= 1, found: {MAX_PARALLEL_TASKS}")
    
    if MAX_PARALLEL_TASKS > 10:
        errors.append(f"MAX_PARALLEL_TASKS seems too high: {MAX_PARALLEL_TASKS} (max recommended: 10)")
    
    if MAX_TASKS_PER_HOUR < 0:
        errors.append(f"MAX_TASKS_PER_HOUR must be >= 0, found: {MAX_TASKS_PER_HOUR}")
    
    if MAX_CPU_PERCENT < 1 or MAX_CPU_PERCENT > 100:
        errors.append(f"MAX_CPU_PERCENT must be 1-100, found: {MAX_CPU_PERCENT}")
    
    if MAX_MEMORY_PERCENT < 1 or MAX_MEMORY_PERCENT > 100:
        errors.append(f"MAX_MEMORY_PERCENT must be 1-100, found: {MAX_MEMORY_PERCENT}")
    
    return errors
