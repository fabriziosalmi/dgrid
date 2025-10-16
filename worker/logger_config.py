"""
D-GRID Logger Unificato
Un logger centralizzato usato da tutti i moduli del worker.
"""
import logging
import sys
from pathlib import Path
from config import LOG_LEVEL, LOG_FILE

# Crea directory di log se non esiste
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

# Configura il logger root
logger = logging.getLogger("d-grid")
logger.setLevel(LOG_LEVEL)

# Handler per file
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(LOG_LEVEL)

# Handler per console
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(LOG_LEVEL)

# Formatter
formatter = logging.Formatter(
    "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Aggiungi i handler al logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def get_logger(module_name):
    """Ritorna un logger per un modulo specifico."""
    return logging.getLogger(f"d-grid.{module_name}")
