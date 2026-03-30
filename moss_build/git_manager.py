"""Git repository management for MOSS Build."""

import subprocess
from pathlib import Path
from typing import Optional

from .config import Component
from .exceptions import GitError


class GitManager:
    """Manages git clone, fetch, and checkout operations."""

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)

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

    def is_synced(self, component: Component) -> bool:
        """Check if component is already at target commit/branch."""
        repo_path = self.cache_dir / component.local_path
        if not repo_path.exists():
            return False

        current_commit = self.get_current_commit(str(repo_path))
        target_commit = component.repository.get('commit')

        if target_commit:
            return current_commit == target_commit
        return True  # No specific commit, assume synced if exists

    def sync(self, component: Component) -> str:
        """
        Clone or update a component's repository.

        Returns the source path of the repository.
        """
        repo_path = self.cache_dir / component.local_path
        url = component.repository.get('url', '')
        branch = component.repository.get('branch', 'main')
        commit = component.repository.get('commit')

        if not url:
            raise GitError(f"No repository URL for component: {component.name}")

        # Ensure cache directory exists
        repo_path.parent.mkdir(parents=True, exist_ok=True)

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
