"""
D-GRID Git Handler Module
Gestisce tutte le operazioni Git (clone, pull, commit, push).
"""
import os
import subprocess
import shutil
from pathlib import Path
from git import Repo
from git.exc import GitCommandError
from logger_config import get_logger
from config import REPO_URL, REPO_PATH, GIT_USER_NAME, GIT_USER_EMAIL, get_git_auth_url

logger = get_logger("git_handler")

class GitHandler:
    """Handler per tutte le operazioni Git."""
    
    def __init__(self):
        self.repo_path = Path(REPO_PATH)
        self.repo = None
    
    def clone_or_open_repo(self):
        """Clona il repo se non esiste, altrimenti lo apre."""
        try:
            # Check se è davvero un repo (esiste .git)
            is_repo = self.repo_path.exists() and (self.repo_path / ".git").exists()
            
            if is_repo:
                logger.info(f"Repository esiste già in {self.repo_path}, apertura...")
                self.repo = Repo(self.repo_path)
                logger.info("Repository aperto con successo.")
            else:
                # Ripulisci directory se esiste ma non è un repo
                if self.repo_path.exists():
                    logger.info(f"Directory {self.repo_path} esiste ma non è un repo, pulizia...")
                    import shutil
                    shutil.rmtree(self.repo_path)
                
                logger.info(f"Clonazione repository da {REPO_URL}...")
                git_url = get_git_auth_url()
                self.repo = Repo.clone_from(git_url, self.repo_path)
                logger.info(f"Repository clonato con successo in {self.repo_path}.")
            
            # Configura git user
            self._configure_git_user()
            return True
        except Exception as e:
            logger.error(f"Errore nel clone/apertura del repository: {e}")
            return False
    
    def _configure_git_user(self):
        """Configura l'utente git per i commit."""
        try:
            self.repo.config_writer().set_value("user", "name", GIT_USER_NAME).release()
            self.repo.config_writer().set_value("user", "email", GIT_USER_EMAIL).release()
            logger.debug(f"Git user configurato: {GIT_USER_NAME} <{GIT_USER_EMAIL}>")
        except Exception as e:
            logger.error(f"Errore nella configurazione del git user: {e}")
    
    def pull_rebase(self):
        """Fa un pull con rebase per restare sempre aggiornati."""
        try:
            logger.info("Eseguendo pull con rebase...")
            self.repo.remotes.origin.pull(rebase=True)
            logger.info("Pull con rebase completato.")
            return True
        except GitCommandError as e:
            logger.error(f"Errore nel pull: {e}")
            return False
        except Exception as e:
            logger.error(f"Errore durante il pull: {e}")
            return False
    
    def commit_and_push(self, message, paths=None):
        """
        Fa un commit atomico e un push dei cambiamenti.
        
        Args:
            message: Messaggio del commit.
            paths: Lista di percorsi da committare (default: tutti i cambiamenti).
        
        Returns:
            True se successo, False altrimenti.
        """
        try:
            if paths:
                self.repo.index.add(paths)
            else:
                self.repo.index.add(["."])
            
            # Controlla se ci sono cambiamenti
            if self.repo.index.diff("HEAD"):
                self.repo.index.commit(message)
                logger.info(f"Commit creato: '{message}'")
            else:
                logger.debug("Nessun cambiamento da committare.")
                return True
            
            # Push
            self.repo.remotes.origin.push()
            logger.info("Push completato.")
            return True
        except GitCommandError as e:
            logger.error(f"Errore nel commit/push: {e}")
            return False
        except Exception as e:
            logger.error(f"Errore durante commit/push: {e}")
            return False
    
    def move_file(self, src, dst):
        """
        Sposta un file usando 'git mv' (atomico dal punto di vista di git).
        
        Args:
            src: Percorso sorgente (relativo al repo).
            dst: Percorso destinazione (relativo al repo).
        
        Returns:
            True se successo, False altrimenti.
        """
        try:
            full_src = self.repo_path / src
            full_dst = self.repo_path / dst
            
            if not full_src.exists():
                logger.error(f"File sorgente non esiste: {full_src}")
                return False
            
            # Assicurati che la directory di destinazione esista
            full_dst.parent.mkdir(parents=True, exist_ok=True)
            
            # Usa git mv
            self.repo.index.move([str(src), str(dst)])
            logger.debug(f"File spostato: {src} -> {dst}")
            return True
        except Exception as e:
            logger.error(f"Errore nello spostamento del file: {e}")
            return False
    
    def get_repo_path(self):
        """Ritorna il percorso del repository."""
        return self.repo_path

def get_git_handler():
    """Factory function per ottenere un GitHandler inizializzato."""
    handler = GitHandler()
    if handler.clone_or_open_repo():
        return handler
    else:
        logger.error("Impossibile inizializzare GitHandler.")
        return None
