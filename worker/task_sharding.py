"""
D-GRID Task Sharding & Priority Queue Module
Implements #1: Task Sharding & Priority Queues.
Reduces contention and enables task prioritization.
"""
import hashlib
from pathlib import Path
from logger_config import get_logger

logger = get_logger("task_sharding")


class TaskSharding:
    """Manages task sharding and priority queues."""
    
    PRIORITY_LEVELS = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3
    }
    
    def __init__(self, queue_base_path):
        """
        Initialize task sharding.
        
        Args:
            queue_base_path: Base path for task queue (e.g., tasks/queue)
        """
        self.queue_base_path = Path(queue_base_path)
        self._ensure_shard_directories()
    
    def _ensure_shard_directories(self):
        """Create shard directories for priorities and hash buckets."""
        try:
            # Create priority subdirectories
            for priority in self.PRIORITY_LEVELS.keys():
                priority_dir = self.queue_base_path / priority
                priority_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created priority directory: {priority}")
            
            # Create hash-based shards within each priority (0-9, a-f)
            for priority in self.PRIORITY_LEVELS.keys():
                for shard in "0123456789abcdef":
                    shard_dir = self.queue_base_path / priority / shard
                    shard_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info("✅ Task shard directories initialized")
            
        except Exception as e:
            logger.error(f"Error creating shard directories: {e}")
    
    def get_task_shard_path(self, task_id, priority="medium"):
        """
        Get the shard path for a task based on its ID and priority.
        
        Args:
            task_id: Unique task identifier
            priority: Task priority (critical, high, medium, low)
        
        Returns:
            Path: Full path to the task's shard directory
        """
        # Validate priority
        if priority not in self.PRIORITY_LEVELS:
            logger.warning(f"Invalid priority '{priority}', defaulting to 'medium'")
            priority = "medium"
        
        # Hash-based sharding: use first character of task_id hash
        task_hash = hashlib.md5(task_id.encode()).hexdigest()
        shard_id = task_hash[0]
        
        return self.queue_base_path / priority / shard_id
    
    def find_next_task(self):
        """
        Find the next task to execute, respecting priority order.
        Scans from highest to lowest priority.
        
        Returns:
            Path: Path to the task file, or None if no tasks available
        """
        try:
            # Iterate through priorities (critical -> high -> medium -> low)
            for priority in sorted(self.PRIORITY_LEVELS.keys(), 
                                 key=lambda p: self.PRIORITY_LEVELS[p]):
                priority_dir = self.queue_base_path / priority
                
                if not priority_dir.exists():
                    continue
                
                # Scan all shards within this priority
                for shard_dir in sorted(priority_dir.iterdir()):
                    if not shard_dir.is_dir():
                        continue
                    
                    # Find first available task in this shard
                    tasks = sorted([f for f in shard_dir.iterdir() if f.is_file() and f.suffix == '.json'])
                    if tasks:
                        logger.info(f"Found task in {priority}/{shard_dir.name}: {tasks[0].name}")
                        return tasks[0]
            
            logger.debug("No tasks found in any shard")
            return None
            
        except Exception as e:
            logger.error(f"Error finding next task: {e}")
            return None
    
    def get_queue_stats(self):
        """
        Get statistics about the task queue.
        
        Returns:
            dict: Queue statistics by priority and shard
        """
        stats = {
            "total": 0,
            "by_priority": {}
        }
        
        try:
            for priority in self.PRIORITY_LEVELS.keys():
                priority_dir = self.queue_base_path / priority
                
                if not priority_dir.exists():
                    stats["by_priority"][priority] = 0
                    continue
                
                count = 0
                for shard_dir in priority_dir.iterdir():
                    if shard_dir.is_dir():
                        tasks = [f for f in shard_dir.iterdir() if f.is_file() and f.suffix == '.json']
                        count += len(tasks)
                
                stats["by_priority"][priority] = count
                stats["total"] += count
            
            logger.debug(f"Queue stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return stats


# Legacy support: check if task is in old flat queue structure
def migrate_legacy_tasks(old_queue_path, sharding):
    """
    Migrate tasks from old flat queue structure to sharded structure.
    
    Args:
        old_queue_path: Path to old queue directory
        sharding: TaskSharding instance
    """
    try:
        old_path = Path(old_queue_path)
        if not old_path.exists():
            return
        
        # Check if there are any tasks in the root queue directory
        tasks = [f for f in old_path.iterdir() if f.is_file() and f.suffix == '.json']
        
        if not tasks:
            return
        
        logger.info(f"Found {len(tasks)} tasks in legacy queue, migrating...")
        
        for task_file in tasks:
            try:
                # Parse task to get priority (default to medium)
                import json
                with open(task_file, 'r') as f:
                    task_data = json.load(f)
                
                task_id = task_data.get("task_id", task_file.stem)
                priority = task_data.get("priority", "medium")
                
                # Get new shard path
                shard_path = sharding.get_task_shard_path(task_id, priority)
                new_path = shard_path / task_file.name
                
                # Move task to new location
                task_file.rename(new_path)
                logger.info(f"Migrated task {task_file.name} to {priority} queue")
                
            except Exception as e:
                logger.error(f"Error migrating task {task_file.name}: {e}")
        
        logger.info("✅ Legacy task migration completed")
        
    except Exception as e:
        logger.error(f"Error during legacy task migration: {e}")
