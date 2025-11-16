"""
D-GRID Task Signing & Verification Module
Implements #9: Task Signing & Verification.
Requires GPG/PGP signatures for task authentication.
"""
import os
import json
import subprocess
from pathlib import Path
from logger_config import get_logger

logger = get_logger("task_signing")


class TaskSigner:
    """Handles task signing and verification using GPG."""
    
    def __init__(self):
        self.enabled = os.getenv("ENABLE_TASK_SIGNING", "false").lower() == "true"
        self.trusted_keys_file = os.getenv("TRUSTED_KEYS_FILE", "/app/trusted_keys.txt")
        self.trusted_keys = self._load_trusted_keys()
        
        if self.enabled:
            logger.info("🔐 Task signing/verification enabled")
            logger.info(f"Trusted keys: {len(self.trusted_keys)} loaded")
        else:
            logger.warning("⚠️  Task signing/verification DISABLED - tasks not authenticated")
    
    def _load_trusted_keys(self):
        """
        Load list of trusted GPG key fingerprints.
        
        Returns:
            set: Set of trusted key fingerprints
        """
        trusted_keys = set()
        
        try:
            keys_path = Path(self.trusted_keys_file)
            if not keys_path.exists():
                logger.warning(f"Trusted keys file not found: {self.trusted_keys_file}")
                return trusted_keys
            
            with open(keys_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('#'):
                        # Normalize fingerprint (remove spaces, uppercase)
                        fingerprint = line.replace(' ', '').upper()
                        trusted_keys.add(fingerprint)
            
            logger.info(f"Loaded {len(trusted_keys)} trusted GPG keys")
            return trusted_keys
            
        except Exception as e:
            logger.error(f"Error loading trusted keys: {e}")
            return trusted_keys
    
    def sign_task(self, task_file_path, key_id=None):
        """
        Sign a task file with GPG.
        
        Args:
            task_file_path: Path to the task JSON file
            key_id: GPG key ID to use for signing (optional)
        
        Returns:
            bool: True if signing succeeded
        """
        try:
            task_path = Path(task_file_path)
            if not task_path.exists():
                logger.error(f"Task file not found: {task_path}")
                return False
            
            # Create detached signature
            sig_path = task_path.with_suffix(task_path.suffix + '.sig')
            
            cmd = ["gpg", "--detach-sign", "--armor"]
            if key_id:
                cmd.extend(["--local-user", key_id])
            cmd.extend(["--output", str(sig_path), str(task_path)])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"✅ Task signed successfully: {task_path.name}")
                return True
            else:
                logger.error(f"Failed to sign task: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("GPG signing timed out")
            return False
        except Exception as e:
            logger.error(f"Error signing task: {e}")
            return False
    
    def verify_task(self, task_file_path):
        """
        Verify a task's GPG signature.
        
        Args:
            task_file_path: Path to the task JSON file
        
        Returns:
            bool: True if signature is valid and from trusted key
        """
        if not self.enabled:
            logger.debug("Task signing disabled - skipping verification")
            return True  # Allow unsigned tasks when signing is disabled
        
        try:
            task_path = Path(task_file_path)
            sig_path = task_path.with_suffix(task_path.suffix + '.sig')
            
            # Check if signature file exists
            if not sig_path.exists():
                logger.error(f"❌ Task signature not found: {task_path.name}")
                return False
            
            # Verify signature with GPG
            result = subprocess.run(
                ["gpg", "--verify", str(sig_path), str(task_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"❌ Invalid signature for task: {task_path.name}")
                logger.debug(f"GPG output: {result.stderr}")
                return False
            
            # Extract key fingerprint from GPG output
            fingerprint = self._extract_fingerprint(result.stderr)
            
            if not fingerprint:
                logger.error(f"❌ Could not extract key fingerprint from signature")
                return False
            
            # Check if key is trusted
            if fingerprint not in self.trusted_keys:
                logger.error(f"❌ Task signed by untrusted key: {fingerprint}")
                logger.error(f"Task rejected: {task_path.name}")
                return False
            
            logger.info(f"✅ Task signature valid and trusted: {task_path.name}")
            logger.debug(f"Signed by: {fingerprint}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("GPG verification timed out")
            return False
        except Exception as e:
            logger.error(f"Error verifying task signature: {e}")
            return False
    
    def _extract_fingerprint(self, gpg_output):
        """
        Extract key fingerprint from GPG verification output.
        
        Args:
            gpg_output: GPG stderr output
        
        Returns:
            str: Key fingerprint (normalized), or None
        """
        try:
            # Look for fingerprint in GPG output
            # Example: "Primary key fingerprint: ABCD 1234 5678 ..."
            for line in gpg_output.split('\n'):
                if 'fingerprint:' in line.lower():
                    # Extract and normalize fingerprint
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        fingerprint = parts[1].strip().replace(' ', '').upper()
                        return fingerprint
            
            # Alternative: look for key ID
            # Example: "using RSA key 1234567890ABCDEF"
            for line in gpg_output.split('\n'):
                if 'using' in line.lower() and 'key' in line.lower():
                    parts = line.split()
                    if len(parts) >= 4:
                        key_id = parts[-1].replace(' ', '').upper()
                        return key_id
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting fingerprint: {e}")
            return None
    
    def add_trusted_key(self, fingerprint):
        """
        Add a key fingerprint to the trusted keys list.
        
        Args:
            fingerprint: GPG key fingerprint
        
        Returns:
            bool: True if added successfully
        """
        try:
            # Normalize fingerprint
            fingerprint = fingerprint.replace(' ', '').upper()
            
            if fingerprint in self.trusted_keys:
                logger.info(f"Key already trusted: {fingerprint}")
                return True
            
            # Add to in-memory set
            self.trusted_keys.add(fingerprint)
            
            # Append to file
            with open(self.trusted_keys_file, 'a') as f:
                f.write(f"{fingerprint}\n")
            
            logger.info(f"✅ Added trusted key: {fingerprint}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding trusted key: {e}")
            return False
    
    def remove_trusted_key(self, fingerprint):
        """
        Remove a key fingerprint from the trusted keys list.
        
        Args:
            fingerprint: GPG key fingerprint
        
        Returns:
            bool: True if removed successfully
        """
        try:
            fingerprint = fingerprint.replace(' ', '').upper()
            
            if fingerprint not in self.trusted_keys:
                logger.warning(f"Key not in trusted list: {fingerprint}")
                return True
            
            # Remove from in-memory set
            self.trusted_keys.remove(fingerprint)
            
            # Rewrite file without this key
            keys_path = Path(self.trusted_keys_file)
            if keys_path.exists():
                with open(keys_path, 'r') as f:
                    lines = f.readlines()
                
                with open(keys_path, 'w') as f:
                    for line in lines:
                        normalized = line.strip().replace(' ', '').upper()
                        if normalized != fingerprint and not line.startswith('#'):
                            f.write(line)
            
            logger.info(f"✅ Removed trusted key: {fingerprint}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing trusted key: {e}")
            return False
    
    def get_trusted_keys_count(self):
        """Get the number of trusted keys."""
        return len(self.trusted_keys)
    
    def is_enabled(self):
        """Check if task signing is enabled."""
        return self.enabled


def get_task_signer():
    """Factory function to get a TaskSigner instance."""
    return TaskSigner()
