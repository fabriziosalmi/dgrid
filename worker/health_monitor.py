"""
D-GRID Health Monitor Module
Implements #18: Health Monitoring & Self-Healing.
Monitors worker health and performs self-healing actions.
"""
import time
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from logger_config import get_logger
from config import MAX_CPU_PERCENT, MAX_MEMORY_PERCENT, REPO_PATH

logger = get_logger("health_monitor")


class HealthMonitor:
    """Monitors worker health and performs self-healing actions."""
    
    def __init__(self):
        self.task_count = 0
        self.task_count_reset_time = datetime.utcnow()
        self.failed_pulls = 0
        self.failed_pushes = 0
        self.last_health_check = datetime.utcnow()
        
    def check_system_resources(self):
        """
        Check system resource usage (CPU, memory, disk).
        
        Returns:
            dict: Health status with resource metrics
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(REPO_PATH)
            
            health = {
                "healthy": True,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "warnings": []
            }
            
            # Check thresholds
            if cpu_percent > MAX_CPU_PERCENT:
                health["healthy"] = False
                health["warnings"].append(f"High CPU usage: {cpu_percent}% (threshold: {MAX_CPU_PERCENT}%)")
                logger.warning(f"⚠️  High CPU usage: {cpu_percent}%")
            
            if memory.percent > MAX_MEMORY_PERCENT:
                health["healthy"] = False
                health["warnings"].append(f"High memory usage: {memory.percent}% (threshold: {MAX_MEMORY_PERCENT}%)")
                logger.warning(f"⚠️  High memory usage: {memory.percent}%")
            
            if disk.percent > 90:
                health["healthy"] = False
                health["warnings"].append(f"Low disk space: {disk.percent}% used")
                logger.warning(f"⚠️  Low disk space: {disk.percent}% used")
            
            if health["healthy"]:
                logger.debug(f"✅ Health check passed - CPU: {cpu_percent}%, Memory: {memory.percent}%, Disk: {disk.percent}%")
            
            return health
            
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return {"healthy": False, "error": str(e)}
    
    def check_git_health(self, git_handler):
        """
        Check Git repository health.
        
        Returns:
            dict: Git health status
        """
        try:
            repo_path = Path(REPO_PATH)
            
            health = {
                "healthy": True,
                "repo_exists": repo_path.exists(),
                "is_git_repo": (repo_path / ".git").exists(),
                "warnings": []
            }
            
            if not health["repo_exists"]:
                health["healthy"] = False
                health["warnings"].append("Repository directory does not exist")
                logger.error("❌ Repository directory missing")
            elif not health["is_git_repo"]:
                health["healthy"] = False
                health["warnings"].append("Not a valid Git repository")
                logger.error("❌ Invalid Git repository")
            
            return health
            
        except Exception as e:
            logger.error(f"Error checking Git health: {e}")
            return {"healthy": False, "error": str(e)}
    
    def self_heal(self, git_handler):
        """
        Perform self-healing actions based on health status.
        
        Args:
            git_handler: GitHandler instance for repo operations
        """
        try:
            logger.info("🔧 Starting self-healing procedures...")
            
            # Check system resources
            system_health = self.check_system_resources()
            if not system_health["healthy"]:
                logger.warning("System resource issues detected")
                
                # Clean up old Docker containers/images if disk is low
                if any("disk" in w.lower() for w in system_health.get("warnings", [])):
                    self._cleanup_docker()
            
            # Check Git health
            git_health = self.check_git_health(git_handler)
            if not git_health["healthy"]:
                logger.warning("Git repository issues detected")
                
                # If repo is corrupted, trigger re-clone on next restart
                if not git_health.get("is_git_repo", True):
                    logger.error("Git repository corrupted - manual intervention required")
            
            logger.info("✅ Self-healing completed")
            
        except Exception as e:
            logger.error(f"Error during self-healing: {e}")
    
    def _cleanup_docker(self):
        """Clean up unused Docker resources to free disk space."""
        try:
            import subprocess
            logger.info("Cleaning up Docker resources...")
            
            # Remove stopped containers
            subprocess.run(["docker", "container", "prune", "-f"], 
                         capture_output=True, timeout=30)
            
            # Remove dangling images
            subprocess.run(["docker", "image", "prune", "-f"], 
                         capture_output=True, timeout=30)
            
            logger.info("✅ Docker cleanup completed")
            
        except Exception as e:
            logger.warning(f"Docker cleanup failed: {e}")
    
    def record_task_execution(self):
        """Record a task execution for rate limiting."""
        self.task_count += 1
        
        # Reset counter every hour
        if datetime.utcnow() - self.task_count_reset_time > timedelta(hours=1):
            self.task_count = 1
            self.task_count_reset_time = datetime.utcnow()
    
    def can_execute_task(self, max_tasks_per_hour):
        """
        Check if worker can execute another task (rate limiting).
        Implementation of #10: Resource Quotas & Rate Limiting.
        
        Args:
            max_tasks_per_hour: Maximum tasks allowed per hour (0 = unlimited)
        
        Returns:
            bool: True if can execute, False otherwise
        """
        if max_tasks_per_hour == 0:
            return True
        
        # Reset counter if hour has passed
        if datetime.utcnow() - self.task_count_reset_time > timedelta(hours=1):
            self.task_count = 0
            self.task_count_reset_time = datetime.utcnow()
        
        if self.task_count >= max_tasks_per_hour:
            logger.warning(f"⚠️  Rate limit reached: {self.task_count}/{max_tasks_per_hour} tasks/hour")
            return False
        
        return True
    
    def get_health_summary(self):
        """Get a summary of worker health status."""
        return {
            "tasks_executed_this_hour": self.task_count,
            "task_count_reset_time": self.task_count_reset_time.isoformat(),
            "failed_pulls": self.failed_pulls,
            "failed_pushes": self.failed_pushes,
            "last_health_check": self.last_health_check.isoformat()
        }
