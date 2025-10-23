"""
D-GRID State Manager Module
Manages node registration and heartbeats.
"""
import json
from datetime import datetime
from pathlib import Path
from logger_config import get_logger
from config import NODE_ID, get_node_specs

logger = get_logger("state_manager")

class StateManager:
    """Manager per lo stato dei nodi e gli heartbeat."""
    
    def __init__(self, git_handler):
        self.git_handler = git_handler
        self.repo_path = git_handler.get_repo_path()
        self.nodes_dir = self.repo_path / "nodes"
        self.node_file = self.nodes_dir / f"{NODE_ID}.json"
    
    def register_node(self):
        """
        Registra il nodo creando/aggiornando il file nodes/{node_id}.json
        con le specs e il timestamp.
        """
        try:
            self.nodes_dir.mkdir(parents=True, exist_ok=True)
            
            specs = get_node_specs()
            specs["last_heartbeat"] = datetime.utcnow().isoformat()
            specs["status"] = "active"
            
            with open(self.node_file, "w") as f:
                json.dump(specs, f, indent=2)
            
            logger.info(f"Nodo registrato: {self.node_file}")
            logger.debug(f"Specs: {json.dumps(specs, indent=2)}")
            
            # Commit e push
            if self.git_handler.commit_and_push(
                f"[D-GRID] Registrazione nodo {NODE_ID}",
                paths=[str(self.node_file)]
            ):
                logger.info("Registrazione nodo pushata.")
                return True
            else:
                logger.error("Errore nel push della registrazione nodo.")
                return False
        except Exception as e:
            logger.error(f"Errore nella registrazione del nodo: {e}")
            return False
    
    def send_heartbeat(self):
        """
        Aggiorna semplicemente il timestamp nel file del nodo (heartbeat).
        """
        try:
            if not self.node_file.exists():
                logger.warning(f"File del nodo non esiste: {self.node_file}, registrando...")
                return self.register_node()
            
            with open(self.node_file, "r") as f:
                data = json.load(f)
            
            data["last_heartbeat"] = datetime.utcnow().isoformat()
            data["status"] = "active"
            
            with open(self.node_file, "w") as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Heartbeat inviato per {NODE_ID}")
            
            # Commit e push
            if self.git_handler.commit_and_push(
                f"[D-GRID] Heartbeat da {NODE_ID}",
                paths=[str(self.node_file)]
            ):
                return True
            else:
                logger.error("Errore nel push dell'heartbeat.")
                return False
        except Exception as e:
            logger.error(f"Errore nell'invio dell'heartbeat: {e}")
            return False
    
    def get_node_status(self):
        """Ritorna lo stato corrente del nodo."""
        try:
            if self.node_file.exists():
                with open(self.node_file, "r") as f:
                    return json.load(f)
            else:
                return None
        except Exception as e:
            logger.error(f"Errore nella lettura dello stato del nodo: {e}")
            return None
