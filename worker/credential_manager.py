"""
D-GRID Secure Credential Management Module
Implements #12: Secure Credential Management.
Provides secure alternatives to storing Git tokens in environment variables.
"""
import os
import subprocess
from pathlib import Path
from logger_config import get_logger

logger = get_logger("credential_manager")


class CredentialManager:
    """Manages secure credential storage and retrieval."""
    
    CREDENTIAL_METHODS = {
        "ssh": "SSH key authentication (most secure)",
        "credential_helper": "Git credential helper",
        "github_app": "GitHub App token",
        "env_token": "Environment variable (legacy, less secure)"
    }
    
    def __init__(self):
        self.method = self._detect_credential_method()
        logger.info(f"Using credential method: {self.CREDENTIAL_METHODS.get(self.method, 'unknown')}")
    
    def _detect_credential_method(self):
        """
        Detect which credential method to use based on configuration.
        Priority: SSH > Credential Helper > GitHub App > Env Token
        """
        # Check for SSH configuration
        if self._is_ssh_configured():
            return "ssh"
        
        # Check for Git credential helper
        if self._is_credential_helper_configured():
            return "credential_helper"
        
        # Check for GitHub App token
        if os.getenv("GITHUB_APP_TOKEN"):
            return "github_app"
        
        # Fallback to environment token (legacy)
        if os.getenv("GIT_TOKEN"):
            logger.warning("⚠️  Using GIT_TOKEN from environment - consider upgrading to SSH or credential helper")
            return "env_token"
        
        logger.warning("No credential method configured - may fail for private repositories")
        return None
    
    def _is_ssh_configured(self):
        """Check if SSH key authentication is configured."""
        try:
            # Check for SSH key files
            ssh_dir = Path.home() / ".ssh"
            key_files = ["id_rsa", "id_ed25519", "id_ecdsa"]
            
            for key_file in key_files:
                key_path = ssh_dir / key_file
                if key_path.exists():
                    logger.debug(f"Found SSH key: {key_path}")
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking SSH configuration: {e}")
            return False
    
    def _is_credential_helper_configured(self):
        """Check if Git credential helper is configured."""
        try:
            result = subprocess.run(
                ["git", "config", "--global", "credential.helper"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                logger.debug(f"Git credential helper configured: {result.stdout.strip()}")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking credential helper: {e}")
            return False
    
    def configure_git_credentials(self, repo_url):
        """
        Configure Git credentials for the repository.
        
        Args:
            repo_url: Repository URL
        
        Returns:
            str: Configured URL (may be modified for authentication)
        """
        try:
            # SSH: no URL modification needed
            if self.method == "ssh":
                if repo_url.startswith("https://"):
                    # Convert HTTPS URL to SSH format
                    ssh_url = self._convert_to_ssh_url(repo_url)
                    logger.info(f"Converted HTTPS URL to SSH: {ssh_url}")
                    return ssh_url
                return repo_url
            
            # Credential helper: no URL modification needed
            if self.method == "credential_helper":
                return repo_url
            
            # GitHub App token: use as Bearer token
            if self.method == "github_app":
                token = os.getenv("GITHUB_APP_TOKEN")
                if token and repo_url.startswith("https://"):
                    # Use GitHub App token format
                    auth_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
                    logger.debug("Using GitHub App token authentication")
                    return auth_url
                return repo_url
            
            # Legacy env token
            if self.method == "env_token":
                token = os.getenv("GIT_TOKEN")
                if token and repo_url.startswith("https://"):
                    auth_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
                    logger.debug("Using environment token (legacy method)")
                    return auth_url
                return repo_url
            
            # No credentials configured
            logger.warning("No credentials configured - using URL as-is")
            return repo_url
            
        except Exception as e:
            logger.error(f"Error configuring credentials: {e}")
            return repo_url
    
    def _convert_to_ssh_url(self, https_url):
        """
        Convert HTTPS URL to SSH format.
        
        Example: https://github.com/user/repo.git -> git@github.com:user/repo.git
        """
        try:
            # Extract parts from HTTPS URL
            if https_url.startswith("https://"):
                url_parts = https_url.replace("https://", "").split("/")
                if len(url_parts) >= 3:
                    host = url_parts[0]
                    user = url_parts[1]
                    repo = "/".join(url_parts[2:])
                    ssh_url = f"git@{host}:{user}/{repo}"
                    return ssh_url
            
            return https_url
            
        except Exception as e:
            logger.error(f"Error converting URL to SSH: {e}")
            return https_url
    
    def setup_credential_helper(self, helper_type="cache"):
        """
        Configure Git credential helper for secure credential storage.
        
        Args:
            helper_type: Type of credential helper ('cache', 'store', or 'osxkeychain')
        """
        try:
            valid_helpers = ["cache", "store", "osxkeychain"]
            if helper_type not in valid_helpers:
                logger.error(f"Invalid credential helper type: {helper_type}")
                return False
            
            # Configure credential helper
            subprocess.run(
                ["git", "config", "--global", "credential.helper", helper_type],
                check=True,
                timeout=5
            )
            
            logger.info(f"✅ Git credential helper configured: {helper_type}")
            
            # For cache helper, optionally set timeout
            if helper_type == "cache":
                subprocess.run(
                    ["git", "config", "--global", "credential.helper", "cache --timeout=3600"],
                    check=True,
                    timeout=5
                )
                logger.info("Credential cache timeout set to 1 hour")
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to configure credential helper: {e}")
            return False
        except Exception as e:
            logger.error(f"Error setting up credential helper: {e}")
            return False
    
    def validate_credentials(self, repo_url):
        """
        Validate that credentials work by attempting to fetch from remote.
        
        Args:
            repo_url: Repository URL to test
        
        Returns:
            bool: True if credentials are valid
        """
        try:
            # Test with ls-remote (doesn't require cloning)
            configured_url = self.configure_git_credentials(repo_url)
            
            result = subprocess.run(
                ["git", "ls-remote", configured_url],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("✅ Credentials validated successfully")
                return True
            else:
                logger.error(f"❌ Credential validation failed: {result.stderr}")
                return False
            
        except subprocess.TimeoutExpired:
            logger.error("Credential validation timed out")
            return False
        except Exception as e:
            logger.error(f"Error validating credentials: {e}")
            return False
    
    def get_security_recommendations(self):
        """
        Get security recommendations based on current credential method.
        
        Returns:
            list: Security recommendations
        """
        recommendations = []
        
        if self.method == "env_token":
            recommendations.append("⚠️  CRITICAL: GIT_TOKEN in environment is insecure")
            recommendations.append("✅ RECOMMENDED: Switch to SSH key authentication")
            recommendations.append("   1. Generate SSH key: ssh-keygen -t ed25519 -C 'worker@dgrid'")
            recommendations.append("   2. Add public key to GitHub: Settings > SSH and GPG keys")
            recommendations.append("   3. Update DGRID_REPO_URL to use SSH format (git@github.com:...)")
        
        elif self.method == "credential_helper":
            recommendations.append("✅ Using Git credential helper - good security")
            recommendations.append("💡 TIP: Consider SSH keys for even better security")
        
        elif self.method == "ssh":
            recommendations.append("✅ Using SSH keys - excellent security")
            recommendations.append("💡 TIP: Ensure SSH keys are password-protected")
        
        elif self.method == "github_app":
            recommendations.append("✅ Using GitHub App token - good security")
            recommendations.append("💡 TIP: Ensure token has minimal required permissions")
        
        else:
            recommendations.append("⚠️  WARNING: No credential method configured")
            recommendations.append("Public repositories will work, but private repos will fail")
        
        return recommendations


def get_credential_manager():
    """Factory function to get a CredentialManager instance."""
    return CredentialManager()
