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
from health_monitor import HealthMonitor
from config import (PULL_INTERVAL, HEARTBEAT_INTERVAL, NODE_ID, validate_config,
                    USE_SHALLOW_CLONE, USE_SMART_POLLING, MAX_TASKS_PER_HOUR)
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
    logger.info(f"   Optimizations: Shallow Clone={USE_SHALLOW_CLONE}, Smart Polling={USE_SMART_POLLING}")
    logger.info(f"   Rate Limit: {MAX_TASKS_PER_HOUR if MAX_TASKS_PER_HOUR > 0 else 'Unlimited'} tasks/hour")
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
    health_monitor = HealthMonitor()
    
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
    
    # Health check interval (every 10 cycles)
    health_check_counter = 0
    
    # Main loop with race condition and retry handling
    try:
        while not shutdown_requested:
            try:
                # Periodic health check (#18: Health Monitoring)
                health_check_counter += 1
                if health_check_counter >= 10:
                    health_check_counter = 0
                    system_health = health_monitor.check_system_resources()
                    if not system_health["healthy"]:
                        logger.warning("⚠️  System health check failed, running self-heal...")
                        health_monitor.self_heal(git_handler)
                
                # Pull the latest state with smart polling (#6)
                logger.debug("Pulling latest state...")
                if not git_handler.pull_rebase(smart_poll=USE_SMART_POLLING):
                    logger.warning("Pull failed, retrying in %ds...", PULL_INTERVAL)
                    health_monitor.failed_pulls += 1
                    time.sleep(PULL_INTERVAL)
                    continue
                
                # Check rate limiting (#10)
                if not health_monitor.can_execute_task(MAX_TASKS_PER_HOUR):
                    logger.debug("Rate limit reached, sending heartbeat instead...")
                    state_manager.send_heartbeat()
                    time.sleep(PULL_INTERVAL)
                    continue
                
                # Look for a task to execute
                task_file = task_runner.find_task_to_run()
                
                if task_file:
                    # Execute the task
                    logger.info(f"Executing task: {task_file.name}")
                    result = task_runner.execute_task(task_file)
                    
                    # Record task execution for rate limiting
                    health_monitor.record_task_execution()
                    
                    # Report the result (critical operation)
                    logger.info(f"Reporting result: exit_code={result['exit_code']}")
                    if not task_runner.report_task_result(task_file, result):
                        logger.error("Failed to report result. Task may remain orphaned.")
                        health_monitor.failed_pushes += 1
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
        
        # Log health summary
        health_summary = health_monitor.get_health_summary()
        logger.info(f"Health Summary: {health_summary}")
        
        logger.info("✅ Worker shutdown complete.")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
