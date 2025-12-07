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
    """Runner for task execution."""
    
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
        Scans tasks/queue and tries to pick up a task.
        Uses 'git mv' for an atomic transaction.
        
        Returns:
            Path of the task in in_progress, or None if no task available.
        """
        try:
            if not self.queue_dir.exists():
                logger.debug("Queue directory does not exist.")
                return None
            
            # Iterate files in queue
            tasks = sorted([f for f in self.queue_dir.iterdir() if f.is_file()])
            if not tasks:
                logger.debug("No tasks available in queue.")
                return None
            
            # Pick the first task
            task_file = tasks[0]
            task_name = task_file.name
            
            logger.info(f"Attempting to acquire task: {task_name}")
            
            # Move file from queue to in_progress using git mv
            src = f"tasks/queue/{task_name}"
            dst = f"tasks/in_progress/{NODE_ID}-{task_name}"
            
            if self.git_handler.move_file(src, dst):
                # Atomic commit and push - first to push wins
                if self.git_handler.commit_and_push(
                    f"[D-GRID] {NODE_ID} acquires task {task_name}",
                    paths=[src, dst]
                ):
                    logger.info(f"Task acquired: {NODE_ID}-{task_name}")
                    return self.in_progress_dir / f"{NODE_ID}-{task_name}"
                else:
                    logger.warning(f"Failed to push task acquisition for {task_name}, retrying...")
                    return None
            else:
                logger.warning(f"Failed to move task {task_name}")
                return None
        except Exception as e:
            logger.error(f"Error finding/acquiring task: {e}")
            return None
    
    def execute_task(self, task_file):
        """
        Reads the task file and executes the command in an isolated Docker container.
        
        SECURITY: The container is executed with:
        - --network=none: No network access
        - --read-only: Read-only filesystem
        - --rm: Automatic cleanup
        - CPU and memory limits
        
        Args:
            task_file: Path of the task file.
        
        Returns:
            Dict with exit_code, stdout, stderr.
        """
        task_id = "unknown"
        try:
            if not task_file.exists():
                logger.error(f"Task file does not exist: {task_file}")
                return {"exit_code": -1, "stdout": "", "stderr": "File not found"}
            
            # Verify task signature (#9: Task Signing & Verification)
            if self.task_signer and self.task_signer.is_enabled():
                if not self.task_signer.verify_task(task_file):
                    logger.error(f"❌ Task signature verification failed: {task_file.name}")
                    return {
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": "Task signature verification failed - task rejected for security"
                    }
            
            # Read task file
            with open(task_file, "r") as f:
                task_data = json.load(f)
            
            # Schema: task_id, script, timeout_seconds
            task_id = task_data.get("task_id", "unknown")
            task_script = task_data.get("script", "")
            task_timeout = task_data.get("timeout_seconds", 60)
            
            # Script validation
            if not task_script or task_script.strip() == "":
                logger.error(f"Task {task_id}: empty script")
                return {"exit_code": -1, "stdout": "", "stderr": "Task script is empty"}
            
            # Timeout validation (must be between 10 and 300)
            if not isinstance(task_timeout, int) or task_timeout < 10 or task_timeout > 300:
                logger.error(f"Task {task_id}: invalid timeout_seconds: {task_timeout}")
                return {"exit_code": -1, "stdout": "", "stderr": f"Invalid timeout (required 10-300): {task_timeout}"}
            
            # ⚠️  SECURITY: Image always python:3.11-alpine
            task_image = "python:3.11-alpine"
            logger.info(f"Executing task {task_id}")
            logger.debug(f"Script length: {len(task_script)} char, timeout: {task_timeout}s")
            
            # Prepare Docker command with maximum isolation
            docker_cmd = [
                "docker", "run",
                "--rm",
                # Network isolation
                "--network=none",
                # Protected filesystem
                "--read-only",
                # Resource limits
                f"--cpus={DOCKER_CPUS}",
                f"--memory={DOCKER_MEMORY}",
                # Process time limits (protects against infinite loops)
                f"--pids-limit=10",
                # Do not run as root
                "--user=1000:1000",
                # Image and command
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
                
                logger.info(f"Task {task_id} completed with exit code {result.returncode}")
                
                return {
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:10000],  # Limit output to 10KB
                    "stderr": result.stderr[:10000]
                }
            except subprocess.TimeoutExpired:
                logger.error(f"Task {task_id} timeout (>{task_timeout}s)")
                return {
                    "exit_code": -2,
                    "stdout": "",
                    "stderr": f"Timeout after {task_timeout}s"
                }
        except json.JSONDecodeError as e:
            logger.error(f"Task {task_id}: malformed JSON file: {e}")
            return {"exit_code": -1, "stdout": "", "stderr": f"Malformed JSON: {e}"}
        except Exception as e:
            logger.error(f"Task {task_id}: execution error: {e}", exc_info=True)
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}
    
    def report_task_result(self, task_file, result):
        """
        Reports the task result by moving the file to the appropriate folder
        and creating a log file with the output.
        
        Args:
            task_file: Path of the task file in in_progress.
            result: Dict with exit_code, stdout, stderr.
        
        Returns:
            True if success, False otherwise.
        """
        try:
            if not task_file.exists():
                logger.error(f"Task file does not exist: {task_file}")
                return False
            
            # Read task
            with open(task_file, "r") as f:
                task_data = json.load(f)
            
            task_id = task_data.get("id", "unknown")
            task_name = task_file.name
            is_success = result["exit_code"] == 0
            
            # Determine destination directory
            dest_dir = self.completed_dir if is_success else self.failed_dir
            dest_file = dest_dir / task_name
            
            # Create log file
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
            
            # Move task file
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            task_file.rename(dest_file)
            logger.info(f"Task file moved: {task_name} -> {dest_file.name}")
            
            # Write log
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2)
            logger.info(f"Task log written: {log_file.name}")
            
            # Commit and push
            src = f"tasks/in_progress/{task_name}"
            dst_relative = f"tasks/{'completed' if is_success else 'failed'}/{task_name}"
            log_relative = f"tasks/{'completed' if is_success else 'failed'}/{task_name}.log"
            
            if self.git_handler.commit_and_push(
                f"[D-GRID] Task {task_id} {'completed' if is_success else 'failed'} by {NODE_ID}",
                paths=[str(dest_file), str(log_file)]
            ):
                logger.info(f"Task {task_id} result pushed.")
                return True
            else:
                logger.error(f"Error pushing task {task_id} result")
                return False
        except Exception as e:
            logger.error(f"Error reporting task result: {e}")
            return False
