"""Git repository management for MOSS Build."""

import subprocess
from pathlib import Path
from typing import Optional

from .config import Component
from .exceptions import GitError


class GitManager:
    """Manages git clone, fetch, and checkout operations."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _run_git(self, args: list, cwd: Optional[str] = None, check: bool = True) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=check,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitError(f"Git command failed: git {' '.join(args)}\n{e.stderr}") from e

    def get_current_commit(self, path: str) -> str:
        """Get current commit SHA for a repository."""
        try:
            return self._run_git(['rev-parse', 'HEAD'], cwd=path)
        except GitError:
            return ""

    def sync(self, component: Component) -> str:
        """
        Sync a component's repository (clone or update).
        
        For local components (no repository URL), returns the local path.
        For remote components, clones/updates in cache directory.

        Returns the source path of the repository.
        """
        repo_info = component.repository
        if not repo_info or not repo_info.get('url'):
            # Local component - return its path directly
            return str(component._component_dir)

        url = repo_info.get('url', '')
        branch = repo_info.get('branch', 'main')
        commit = repo_info.get('commit')
        
        # Determine cache path from URL
        repo_name = url.rstrip('/').split('/')[-1].replace('.git', '')
        repo_path = self.cache_dir / repo_name

        if not repo_path.exists():
            # Clone the repository
            self._run_git([
                'clone',
                '--branch', branch,
                '--single-branch',
                '--depth', '1',
                url,
                str(repo_path),
            ])
            if commit:
                self._run_git(['checkout', commit], cwd=str(repo_path))
        else:
            # Update existing repository
            self._run_git(['fetch', 'origin', branch], cwd=str(repo_path))

            if commit:
                self._run_git(['checkout', commit], cwd=str(repo_path))
            else:
                self._run_git(['checkout', branch], cwd=str(repo_path))

        return str(repo_path)
    
    def is_synced(self, component: Component) -> bool:
        """Check if component is already at target commit/branch."""
        repo_info = component.repository
        if not repo_info or not repo_info.get('url'):
            # Local component - always "synced"
            return True

        repo_name = repo_info.get('url', '').rstrip('/').split('/')[-1].replace('.git', '')
        repo_path = self.cache_dir / repo_name
        
        if not repo_path.exists():
            return False

        current_commit = self.get_current_commit(str(repo_path))
        target_commit = repo_info.get('commit')

        if target_commit:
            return current_commit == target_commit
        return True  # No specific commit, assume synced if exists
