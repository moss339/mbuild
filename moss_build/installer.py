"""Component installer for MOSS Build."""

import shutil
import yaml
from pathlib import Path
from typing import List, Dict, Any

from .config import Config, Component
from .git_manager import GitManager


class Installer:
    """Installs built components to an install root."""

    def __init__(self, config: Config, install_root: str):
        self.config = config
        self.install_root = Path(install_root)
        cache_dir = config.get_setting('cache_dir', '.moss/cache')
        self.git_manager = GitManager(cache_dir)
        self.build_dir = Path(config.get_setting('build_root', './build'))

    def install_all(self):
        """Install all enabled components."""
        for comp in self.config.get_enabled_components():
            self.install_component(comp)
        self.generate_manifest()

    def install_component(self, comp: Component):
        """Install a single component's artifacts."""
        artifacts = comp.install.get('artifacts', [])
        if not artifacts:
            return

        # Ensure install directories exist
        lib_dir = self.install_root / 'lib'
        include_dir = self.install_root / 'include'
        lib_dir.mkdir(parents=True, exist_ok=True)
        include_dir.mkdir(parents=True, exist_ok=True)

        # Copy artifacts
        build_path = self.build_dir / comp.local_path
        for artifact in artifacts:
            src_pattern = artifact.get('src')
            dest_rel = artifact.get('dest', '')
            if not src_pattern:
                continue

            src_path = build_path / src_pattern
            dest_dir = self.install_root / dest_rel
            dest_dir.mkdir(parents=True, exist_ok=True)

            if src_path.exists():
                if src_path.is_dir():
                    shutil.copytree(src_path, dest_dir / src_path.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dest_dir / src_path.name)
            else:
                # Try glob patterns
                for match in build_path.glob(src_pattern):
                    if match.is_file():
                        shutil.copy2(match, dest_dir / match.name)

    def generate_manifest(self):
        """Generate deploy_manifest.yaml."""
        manifest_path = self.install_root / 'deploy_manifest.yaml'
        components_data = []

        for comp in self.config.get_enabled_components():
            components_data.append({
                'name': comp.name,
                'local_path': comp.local_path,
                'repository': comp.repository,
                'dependencies': comp.dependencies,
            })

        manifest = {
            'version': '1.0',
            'components': components_data,
        }

        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False)
