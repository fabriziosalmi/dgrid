#!/usr/bin/env python3
"""
D-GRID Worker Node - Main Entry Point
Il cuore del worker: ciclo principale di esecuzione.
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

# Flag per il graceful shutdown
shutdown_requested = False
task_in_progress = False

def signal_handler(sig, frame):
    """
    Gestisce i segnali di termination (SIGTERM, SIGINT).
    Imposta il flag di shutdown in modo che il worker termini gracefully.
    """
    global shutdown_requested
    signal_name = signal.Signals(sig).name if hasattr(signal, 'Signals') else str(sig)
    logger.warning(f"🛑 Segnale {signal_name} ricevuto. Avvio shutdown graceful...")
    logger.info("Il worker terminerà il task corrente (se presente) e farà un ultimo push.")
    shutdown_requested = True

def main():
    """Main loop del worker."""
    logger.info("=" * 60)
    logger.info("🚀 D-GRID Worker Node - Avvio")
    logger.info(f"   Node ID: {NODE_ID}")
    logger.info("=" * 60)
    
    # Valida la configurazione all'avvio
    config_errors = validate_config()
    if config_errors:
        logger.error("❌ Errori di configurazione rilevati:")
        for error in config_errors:
            logger.error(f"   - {error}")
        logger.error("Impossibile avviare il worker. Correggi gli errori di configurazione.")
        sys.exit(1)
    
    logger.info("✅ Configurazione validata.")
    
    # Registra i signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Inizializza i componenti
    git_handler = get_git_handler()
    if not git_handler:
        logger.error("Impossibile inizializzare Git Handler. Uscita.")
        sys.exit(1)
    
    state_manager = StateManager(git_handler)
    task_runner = TaskRunner(git_handler)
    
    # Registra il nodo
    if not state_manager.register_node():
        logger.error("Impossibile registrare il nodo. Uscita.")
        sys.exit(1)
    
    logger.info("✅ Nodo registrato e pronto.")
    
    # Avvia il web server per la dashboard locale
    logger.info("Avvio web server locale...")
    try:
        start_web_server()
        logger.info("✅ Web server avviato su http://0.0.0.0:8000")
    except Exception as e:
        logger.warning(f"⚠️  Non è stato possibile avviare il web server: {e}")
    
    logger.info("Avvio loop principale...")
    logger.info("-" * 60)
    
    # Loop principale con gestione race condition e retry
    try:
        while not shutdown_requested:
            try:
                # Pull dello stato più recente (SEMPRE il primo passo)
                logger.debug("Pull dello stato più recente...")
                if not git_handler.pull_rebase():
                    logger.warning("Pull fallito, ritentando tra %ds...", PULL_INTERVAL)
                    time.sleep(PULL_INTERVAL)
                    continue
                
                # Cerca un task da eseguire
                task_file = task_runner.find_task_to_run()
                
                if task_file:
                    # Esegui il task
                    logger.info(f"Esecuzione task: {task_file.name}")
                    result = task_runner.execute_task(task_file)
                    
                    # Riporta il risultato (operazione critica)
                    logger.info(f"Reporting risultato: exit_code={result['exit_code']}")
                    if not task_runner.report_task_result(task_file, result):
                        logger.error("Fallito il report del risultato. Task potrebbe rimanere orfano.")
                        # Nota: Il task è già stato spostato localmente, ma il push è fallito.
                        # Fare un reset per coerenza con lo stato remoto.
                        logger.warning("Reset dello stato locale dopo fallimento report...")
                        git_handler.pull_rebase()  # Reacquisire lo stato remoto
                else:
                    # Nessun task, invia heartbeat
                    logger.debug("Nessun task disponibile, invio heartbeat...")
                    state_manager.send_heartbeat()
                
                # Sleep prima del prossimo ciclo
                logger.debug(f"Sleep {PULL_INTERVAL}s...")
                time.sleep(PULL_INTERVAL)
            
            except Exception as e:
                # Cattura TUTTI gli errori del loop
                logger.error(f"Errore nel loop principale: {e}", exc_info=True)
                logger.warning("Esecuzione reset dello stato locale e ritentativo...")
                
                # Reset locale per evitare stati inconsistenti
                try:
                    git_handler.pull_rebase()
                except Exception as reset_error:
                    logger.error(f"Fallito il reset durante recovery: {reset_error}")
                
                # Sleep prima di ricominciare
                time.sleep(PULL_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt ricevuto.")
    
    finally:
        logger.info("-" * 60)
        logger.info("🛑 SHUTDOWN SEQUENZA AVVIATA")
        logger.info("Invio dell'ultimo heartbeat prima di uscire...")
        try:
            state_manager.send_heartbeat()
            logger.info("✅ Ultimo heartbeat inviato.")
        except Exception as e:
            logger.warning(f"Fallito l'invio dell'ultimo heartbeat: {e}")
        
        logger.info("✅ Worker shutdown completato.")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
