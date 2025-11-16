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

# === Configurazione Repository Git ===
REPO_URL = os.getenv("DGRID_REPO_URL", "https://github.com/fabriziopandini/d-grid.git")
REPO_PATH = os.getenv("DGRID_REPO_PATH", "/tmp/d-grid-repo")

# === Configurazione Nodo ===
NODE_ID = os.getenv("NODE_ID", socket.gethostname())
NODE_NAME = os.getenv("NODE_NAME", f"worker-{NODE_ID}")

# === Credenziali Git ===
GIT_USER_NAME = os.getenv("GIT_USER_NAME", "D-GRID Worker")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", f"worker+{NODE_ID}@d-grid.local")
GIT_TOKEN = os.getenv("GIT_TOKEN", None)  # Per autenticazione con HTTPS

# === Configurazione Docker ===
DOCKER_CPUS = os.getenv("DOCKER_CPUS", "1")
DOCKER_MEMORY = os.getenv("DOCKER_MEMORY", "512m")
DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "3600"))  # secondi

# === Configurazione Worker Loop ===
PULL_INTERVAL = int(os.getenv("PULL_INTERVAL", "10"))  # secondi tra i pull
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "60"))  # secondi tra gli heartbeat

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

# === Specs del Nodo (per la registrazione) ===
def get_node_specs():
    """
    Ritorna le specs del nodo (CPU, RAM, etc).
    Se psutil non è disponibile, ritorna valori di fallback conservativi.
    """
    try:
        if psutil is None:
            raise ImportError("psutil non disponibile")
        
        return {
            "node_id": NODE_ID,
            "node_name": NODE_NAME,
            "cpu_count": psutil.cpu_count(logical=False) or 1,
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "disk_gb": round(psutil.disk_usage("/").total / (1024**3), 2),
        }
    except Exception as e:
        # Fallback: specs minimali se psutil non è disponibile o sistema anomalo
        return {
            "node_id": NODE_ID,
            "node_name": NODE_NAME,
            "cpu_count": 1,
            "memory_gb": 0.5,
            "disk_gb": 10.0,
        }

def get_git_auth_url():
    """
    Ritorna l'URL di autenticazione Git.
    
    ⚠️  SECURITY WARNING ⚠️
    Se GIT_TOKEN è usato, l'URL conterrà il token in plaintext.
    NON loggare mai questo URL completo. Usare questa funzione solo in contesti
    privati (es. dentro subprocess con stderr/stdout gestito).
    
    Preferibilmente usare SSH con chiavi invece di HTTPS + token.
    """
    if GIT_TOKEN and REPO_URL.startswith("https://"):
        # Costruisci URL con token (usato solo in contesti privati)
        url = REPO_URL.replace("https://", f"https://x-access-token:{GIT_TOKEN}@")
        return url
    return REPO_URL

def validate_config():
    """
    Valida la configurazione all'avvio del worker.
    Ritorna una lista di errori (vuota se tutto OK).
    """
    errors = []
    
    # Validazione REPO_URL
    if not REPO_URL or not REPO_URL.startswith(("https://", "git@", "file://")):
        errors.append(f"DGRID_REPO_URL non valido: '{REPO_URL}'. Deve iniziare con https://, git@, o file://")
    
    # Validazione NODE_ID
    if not NODE_ID or NODE_ID.strip() == "":
        errors.append("NODE_ID non può essere vuoto. Impostare via env var o hostname fallback.")
    
    # Validazione intervalli
    if PULL_INTERVAL < 1:
        errors.append(f"PULL_INTERVAL deve essere >= 1s, trovato: {PULL_INTERVAL}s")
    
    if PULL_INTERVAL > 3600:
        errors.append(f"PULL_INTERVAL sembra troppo alto: {PULL_INTERVAL}s (max consigliato: 3600s)")
    
    if HEARTBEAT_INTERVAL < 1:
        errors.append(f"HEARTBEAT_INTERVAL deve essere >= 1s, trovato: {HEARTBEAT_INTERVAL}s")
    
    if HEARTBEAT_INTERVAL < PULL_INTERVAL:
        errors.append(f"HEARTBEAT_INTERVAL ({HEARTBEAT_INTERVAL}s) < PULL_INTERVAL ({PULL_INTERVAL}s). Heartbeat dovrebbe essere meno frequente di pull.")
    
    # Validazione timeout Docker
    if DOCKER_TIMEOUT < 5:
        errors.append(f"DOCKER_TIMEOUT deve essere >= 5s, trovato: {DOCKER_TIMEOUT}s")
    
    # Validazione risorze Docker
    try:
        float(DOCKER_CPUS)
    except (ValueError, TypeError):
        errors.append(f"DOCKER_CPUS non è un numero valido: '{DOCKER_CPUS}'")
    
    if DOCKER_MEMORY not in ["512m", "1g", "2g", "4g", "8g", "16g"] and not DOCKER_MEMORY.endswith(("m", "g")):
        errors.append(f"DOCKER_MEMORY formato non riconosciuto: '{DOCKER_MEMORY}' (usa: 512m, 1g, 2g, etc.)")
    
    # Validazione LOG_LEVEL
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if LOG_LEVEL not in valid_levels:
        errors.append(f"LOG_LEVEL non valido: '{LOG_LEVEL}'. Usa uno di: {', '.join(valid_levels)}")
    
    # Validazione Phase 1 improvements
    if MAX_PARALLEL_TASKS < 1:
        errors.append(f"MAX_PARALLEL_TASKS deve essere >= 1, trovato: {MAX_PARALLEL_TASKS}")
    
    if MAX_PARALLEL_TASKS > 10:
        errors.append(f"MAX_PARALLEL_TASKS sembra troppo alto: {MAX_PARALLEL_TASKS} (max consigliato: 10)")
    
    if MAX_TASKS_PER_HOUR < 0:
        errors.append(f"MAX_TASKS_PER_HOUR deve essere >= 0, trovato: {MAX_TASKS_PER_HOUR}")
    
    if MAX_CPU_PERCENT < 1 or MAX_CPU_PERCENT > 100:
        errors.append(f"MAX_CPU_PERCENT deve essere 1-100, trovato: {MAX_CPU_PERCENT}")
    
    if MAX_MEMORY_PERCENT < 1 or MAX_MEMORY_PERCENT > 100:
        errors.append(f"MAX_MEMORY_PERCENT deve essere 1-100, trovato: {MAX_MEMORY_PERCENT}")
    
    return errors

