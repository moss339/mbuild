"""Component installer for MOSS Build - New Design.

Install rules are component self-deciding via component.yaml.
Follows convention-over-configuration for library/application types.
"""

import shutil
import yaml
import stat
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import Config, Component
from .git_manager import GitManager
from .exceptions import InstallError


class Installer:
    """Installs built components based on their component.yaml install rules."""

    def __init__(self, config: Config, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.git_manager = GitManager(config.get_cache_dir())
        self.build_root = config.get_build_root()
        self.install_root = config.get_install_root()
        
        # Create standard directories
        self.lib_dir = self.install_root / 'lib'
        self.include_dir = self.install_root / 'include'
        self.bin_dir = self.install_root / 'bin'
        self.etc_dir = self.install_root / 'etc'
        
        for d in [self.lib_dir, self.include_dir, self.bin_dir, self.etc_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def install_all(self):
        """Install all enabled components."""
        for comp in self.config.get_enabled_components():
            try:
                self.install_component(comp)
            except InstallError as e:
                print(f"⚠️  {comp.name}: install warning: {e}", file=__import__('sys').stderr)
        
        self.generate_manifest()
        print(f"✅ Installed to {self.install_root}")

    def install_component(self, comp: Component):
        """Install a single component's artifacts based on its install rules."""
        build_path = self.build_root / comp.name
        if not build_path.exists():
            print(f"   ⚠️  {comp.name}: build directory not found, skipping install")
            return
        
        install_rule = comp.install
        install_type = install_rule.get('type', 'library') if install_rule else 'library'
        
        if install_type == 'library':
            self._install_library(comp, build_path, install_rule)
        elif install_type == 'application':
            self._install_application(comp, build_path, install_rule)
        else:
            # Fallback: try library pattern
            self._install_library(comp, build_path, install_rule)
        
        print(f"   📦 {comp.name} installed")

    def _install_library(self, comp: Component, build_path: Path, rule: Dict[str, Any]):
        """Install a library type component."""
        # Headers
        headers = rule.get('headers', {})
        if headers:
            src_dir = build_path / headers.get('from', 'include')
            dest_dir = self.include_dir / headers.get('to', f'include/{comp.name}')
            if src_dir.exists():
                self._copy_tree(src_dir, dest_dir)
        
        # Libraries
        libs = rule.get('libraries', {})
        if libs:
            src_dir = build_path / libs.get('from', 'lib')
            patterns = libs.get('patterns', [f'lib{comp.name}.*'])
            
            for pattern in patterns:
                for lib_file in src_dir.glob(pattern):
                    dest = self.lib_dir / lib_file.name
                    self._copy_file(lib_file, dest)
                    # Set permissions
                    dest.chmod(0o644)

    def _install_application(self, comp: Component, build_path: Path, rule: Dict[str, Any]):
        """Install an application type component."""
        # Executables
        executables = rule.get('executables', [])
        if isinstance(executables, dict):
            executables = [executables]
        
        for exec_rule in executables:
            src_file = build_path / exec_rule.get('from', f'{comp.name}')
            dest_file = self.bin_dir / exec_rule.get('to', comp.name)
            
            if src_file.exists():
                self._copy_file(src_file, dest_file)
                dest_file.chmod(exec_rule.get('mode', 0o755))
        
        # Configs
        configs = rule.get('configs', {})
        if configs:
            src_dir = build_path / configs.get('from', 'config')
            dest_dir = self.etc_dir / configs.get('to', comp.name)
            if src_dir.exists():
                self._copy_tree(src_dir, dest_dir)

    def _copy_file(self, src: Path, dest: Path):
        """Copy a single file."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        if self.verbose:
            print(f"   cp {src} -> {dest}")
        shutil.copy2(src, dest)

    def _copy_tree(self, src: Path, dest: Path):
        """Copy a directory tree."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        if self.verbose:
            print(f"   cp -r {src} -> {dest}")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    def generate_manifest(self):
        """Generate deploy_manifest.yaml."""
        manifest_path = self.install_root / 'deploy_manifest.yaml'
        
        components_data = []
        for comp in self.config.get_enabled_components():
            data = {
                'name': comp.name,
                'description': comp.description,
                'type': comp.install.get('type', 'library') if comp.install else 'library',
                'dependencies': {
                    'local': comp.dependencies.get('local', []),
                    'system': comp.dependencies.get('system', []),
                },
            }
            
            # Add repository info if remote
            if comp.repository and comp.repository.get('url'):
                data['repository'] = comp.repository
            
            components_data.append(data)
        
        manifest = {
            'version': '1.0',
            'name': self.config.manifest.name,
            'installed_at': str(Path(__import__('datetime').datetime.now().isoformat())),
            'components': components_data,
        }
        
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False)
        
        if self.verbose:
            print(f"   Generated {manifest_path}")
