#!/usr/bin/env python3
"""
D-GRID Worker Node - Main Entry Point
The heart of the worker: main execution loop.
"""
import time
import signal
import sys
from logger_config import get_logger
from git_handler import get_git_handler
from state_manager import StateManager
from task_runner import TaskRunner
from config import PULL_INTERVAL, HEARTBEAT_INTERVAL, NODE_ID, validate_config
from web_server import start_web_server

logger = get_logger("main")

# Flag for graceful shutdown
shutdown_requested = False
task_in_progress = False

def signal_handler(sig, frame):
    """
    Handles termination signals (SIGTERM, SIGINT).
    Sets the shutdown flag so the worker terminates gracefully.
    """
    global shutdown_requested
    signal_name = signal.Signals(sig).name if hasattr(signal, 'Signals') else str(sig)
    logger.warning(f"🛑 Signal {signal_name} received. Starting graceful shutdown...")
    logger.info("Worker will complete current task (if any) and do a final push.")
    shutdown_requested = True

def main():
    """Main worker loop."""
    logger.info("=" * 60)
    logger.info("🚀 D-GRID Worker Node - Starting")
    logger.info(f"   Node ID: {NODE_ID}")
    logger.info("=" * 60)
    
    # Validate configuration at startup
    config_errors = validate_config()
    if config_errors:
        logger.error("❌ Configuration errors detected:")
        for error in config_errors:
            logger.error(f"   - {error}")
        logger.error("Cannot start worker. Fix configuration errors.")
        sys.exit(1)
    
    logger.info("✅ Configuration validated.")
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize components
    git_handler = get_git_handler()
    if not git_handler:
        logger.error("Unable to initialize Git Handler. Exiting.")
        sys.exit(1)
    
    state_manager = StateManager(git_handler)
    task_runner = TaskRunner(git_handler)
    
    # Register the node
    if not state_manager.register_node():
        logger.error("Unable to register node. Exiting.")
        sys.exit(1)
    
    logger.info("✅ Node registered and ready.")
    
    # Start the web server for local dashboard
    logger.info("Starting local web server...")
    try:
        start_web_server()
        logger.info("✅ Web server started on http://0.0.0.0:8000")
    except Exception as e:
        logger.warning(f"⚠️  Unable to start web server: {e}")
    
    logger.info("Starting main loop...")
    logger.info("-" * 60)
    
    # Main loop with race condition and retry handling
    try:
        while not shutdown_requested:
            try:
                # Pull the latest state (ALWAYS the first step)
                logger.debug("Pulling latest state...")
                if not git_handler.pull_rebase():
                    logger.warning("Pull failed, retrying in %ds...", PULL_INTERVAL)
                    time.sleep(PULL_INTERVAL)
                    continue
                
                # Look for a task to execute
                task_file = task_runner.find_task_to_run()
                
                if task_file:
                    # Execute the task
                    logger.info(f"Executing task: {task_file.name}")
                    result = task_runner.execute_task(task_file)
                    
                    # Report the result (critical operation)
                    logger.info(f"Reporting result: exit_code={result['exit_code']}")
                    if not task_runner.report_task_result(task_file, result):
                        logger.error("Failed to report result. Task may remain orphaned.")
                        # Note: Task has already been moved locally, but push failed.
                        # Do a reset for consistency with remote state.
                        logger.warning("Resetting local state after report failure...")
                        git_handler.pull_rebase()  # Reacquire remote state
                else:
                    # No task, send heartbeat
                    logger.debug("No task available, sending heartbeat...")
                    state_manager.send_heartbeat()
                
                # Sleep before next cycle
                logger.debug(f"Sleep {PULL_INTERVAL}s...")
                time.sleep(PULL_INTERVAL)
            
            except Exception as e:
                # Catch ALL loop errors
                logger.error(f"Error in main loop: {e}", exc_info=True)
                logger.warning("Executing reset of local state and retrying...")
                
                # Local reset to avoid inconsistent states
                try:
                    git_handler.pull_rebase()
                except Exception as reset_error:
                    logger.error(f"Failed reset during recovery: {reset_error}")
                
                # Sleep before restarting
                time.sleep(PULL_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    
    finally:
        logger.info("-" * 60)
        logger.info("🛑 SHUTDOWN SEQUENCE STARTED")
        logger.info("Sending last heartbeat before exiting...")
        try:
            state_manager.send_heartbeat()
            logger.info("✅ Last heartbeat sent.")
        except Exception as e:
            logger.warning(f"Failed to send last heartbeat: {e}")
        
        logger.info("✅ Worker shutdown complete.")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
