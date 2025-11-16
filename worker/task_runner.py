"""
D-GRID Task Runner Module
Manages task recognition, execution, and reporting.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from logger_config import get_logger
from config import NODE_ID, DOCKER_CPUS, DOCKER_MEMORY, DOCKER_TIMEOUT

logger = get_logger("task_runner")


class TaskRunner:
    """Runner per l'esecuzione dei task."""
    
    def __init__(self, git_handler):
        self.git_handler = git_handler
        self.repo_path = git_handler.get_repo_path()
        self.queue_dir = self.repo_path / "tasks" / "queue"
        self.in_progress_dir = self.repo_path / "tasks" / "in_progress"
        self.completed_dir = self.repo_path / "tasks" / "completed"
        self.failed_dir = self.repo_path / "tasks" / "failed"
        
        # Initialize task signing (#9: Task Signing & Verification)
        self.task_signer = None
        try:
            from task_signing import get_task_signer
            self.task_signer = get_task_signer()
            if self.task_signer.is_enabled():
                logger.info(f"🔐 Task signing enabled with {self.task_signer.get_trusted_keys_count()} trusted keys")
        except Exception as e:
            logger.warning(f"Could not initialize task signer: {e}")
    
    def find_task_to_run(self):
        """
        Scansiona tasks/queue e prova a prendere in carico un task.
        Usa 'git mv' per una transazione atomica.
        
        Returns:
            Path del task in in_progress, o None se nessun task disponibile.
        """
        try:
            if not self.queue_dir.exists():
                logger.debug("Queue directory non esiste.")
                return None
            
            # Scorri i file nella queue
            tasks = sorted([f for f in self.queue_dir.iterdir() if f.is_file()])
            if not tasks:
                logger.debug("Nessun task disponibile nella queue.")
                return None
            
            # Prendi il primo task
            task_file = tasks[0]
            task_name = task_file.name
            
            logger.info(f"Tentando di acquisire task: {task_name}")
            
            # Sposta il file da queue a in_progress usando git mv
            src = f"tasks/queue/{task_name}"
            dst = f"tasks/in_progress/{NODE_ID}-{task_name}"
            
            if self.git_handler.move_file(src, dst):
                # Commit e push atomico - il primo che pushes vince
                if self.git_handler.commit_and_push(
                    f"[D-GRID] {NODE_ID} acquisisce task {task_name}",
                    paths=[src, dst]
                ):
                    logger.info(f"Task acquisito: {NODE_ID}-{task_name}")
                    return self.in_progress_dir / f"{NODE_ID}-{task_name}"
                else:
                    logger.warning(f"Fallito il push dell'acquisizione del task {task_name}, riprovando...")
                    return None
            else:
                logger.warning(f"Fallito lo spostamento del task {task_name}")
                return None
        except Exception as e:
            logger.error(f"Errore nel trovare/acquisire un task: {e}")
            return None
    
    def execute_task(self, task_file):
        """
        Legge il file del task ed esegue il comando in un container Docker isolato.
        
        SICUREZZA: Il container è eseguito con:
        - --network=none: Nessun accesso alla rete
        - --read-only: Filesystem in sola lettura
        - --rm: Pulizia automatica
        - Limiti di CPU e memoria
        
        Args:
            task_file: Path del file del task.
        
        Returns:
            Dict con exit_code, stdout, stderr.
        """
        task_id = "unknown"
        try:
            if not task_file.exists():
                logger.error(f"File del task non esiste: {task_file}")
                return {"exit_code": -1, "stdout": "", "stderr": "File non trovato"}
            
            # Verify task signature (#9: Task Signing & Verification)
            if self.task_signer and self.task_signer.is_enabled():
                if not self.task_signer.verify_task(task_file):
                    logger.error(f"❌ Task signature verification failed: {task_file.name}")
                    return {
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": "Task signature verification failed - task rejected for security"
                    }
            
            # Leggi il file del task
            with open(task_file, "r") as f:
                task_data = json.load(f)
            
            # Schema: task_id, script, timeout_seconds
            task_id = task_data.get("task_id", "unknown")
            task_script = task_data.get("script", "")
            task_timeout = task_data.get("timeout_seconds", 60)
            
            # Validazione script
            if not task_script or task_script.strip() == "":
                logger.error(f"Task {task_id}: script vuoto")
                return {"exit_code": -1, "stdout": "", "stderr": "Script del task vuoto"}
            
            # Validazione timeout (deve essere tra 10 e 300)
            if not isinstance(task_timeout, int) or task_timeout < 10 or task_timeout > 300:
                logger.error(f"Task {task_id}: timeout_seconds non valido: {task_timeout}")
                return {"exit_code": -1, "stdout": "", "stderr": f"Timeout non valido (richiesto 10-300): {task_timeout}"}
            
            # ⚠️  SECURITY: Immagine sempre python:3.11-alpine
            task_image = "python:3.11-alpine"
            logger.info(f"Eseguendo task {task_id}")
            logger.debug(f"Script length: {len(task_script)} char, timeout: {task_timeout}s")
            
            # Prepara il comando Docker con isolamento massimo
            docker_cmd = [
                "docker", "run",
                "--rm",
                # Isolamento della rete
                "--network=none",
                # Filesystem protetto
                "--read-only",
                # Limiti di risorsa
                f"--cpus={DOCKER_CPUS}",
                f"--memory={DOCKER_MEMORY}",
                # Limiti di tempo del processo (protegge da loop infiniti)
                f"--pids-limit=10",
                # Non eseguire come root
                "--user=1000:1000",
                # Immagine e comando
                task_image,
                "sh", "-c", task_script
            ]
            
            logger.debug(f"Docker isolation: network=none, read-only, user=1000:1000, pids-limit=10")
            
            # Execute command with aggressive timeout
            try:
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=task_timeout
                )
                
                logger.info(f"Task {task_id} completato con exit code {result.returncode}")
                
                return {
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:10000],  # Limita l'output a 10KB
                    "stderr": result.stderr[:10000]
                }
            except subprocess.TimeoutExpired:
                logger.error(f"Task {task_id} timeout (>{task_timeout}s)")
                return {
                    "exit_code": -2,
                    "stdout": "",
                    "stderr": f"Timeout dopo {task_timeout}s"
                }
        except json.JSONDecodeError as e:
            logger.error(f"Task {task_id}: file JSON malformato: {e}")
            return {"exit_code": -1, "stdout": "", "stderr": f"JSON malformato: {e}"}
        except Exception as e:
            logger.error(f"Task {task_id}: errore nell'esecuzione: {e}", exc_info=True)
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}
    
    def report_task_result(self, task_file, result):
        """
        Riporta il risultato del task spostando il file nella cartella appropriata
        e creando un file di log con l'output.
        
        Args:
            task_file: Path del file del task in in_progress.
            result: Dict con exit_code, stdout, stderr.
        
        Returns:
            True se successo, False altrimenti.
        """
        try:
            if not task_file.exists():
                logger.error(f"File del task non esiste: {task_file}")
                return False
            
            # Leggi il task
            with open(task_file, "r") as f:
                task_data = json.load(f)
            
            task_id = task_data.get("id", "unknown")
            task_name = task_file.name
            is_success = result["exit_code"] == 0
            
            # Determina la directory di destinazione
            dest_dir = self.completed_dir if is_success else self.failed_dir
            dest_file = dest_dir / task_name
            
            # Crea un file di log
            log_file = dest_dir / f"{task_name}.log"
            log_data = {
                "task_id": task_id,
                "node_id": NODE_ID,
                "exit_code": result["exit_code"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "timestamp": datetime.utcnow().isoformat(),
                "status": "success" if is_success else "failed"
            }
            
            # Sposta il file del task
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            task_file.rename(dest_file)
            logger.info(f"Task file spostato: {task_name} -> {dest_file.name}")
            
            # Scrivi il log
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)
            logger.info(f"Log del task scritto: {log_file.name}")
            
            # Commit e push
            src = f"tasks/in_progress/{task_name}"
            dst_relative = f"tasks/{'completed' if is_success else 'failed'}/{task_name}"
            log_relative = f"tasks/{'completed' if is_success else 'failed'}/{task_name}.log"
            
            if self.git_handler.commit_and_push(
                f"[D-GRID] Task {task_id} {'completato' if is_success else 'fallito'} da {NODE_ID}",
                paths=[str(dest_file), str(log_file)]
            ):
                logger.info(f"Risultato del task {task_id} pushato.")
                return True
            else:
                logger.error(f"Errore nel push del risultato del task {task_id}")
                return False
        except Exception as e:
            logger.error(f"Errore nel reporting del risultato del task: {e}")
            return False
