"""Component installer for MOSS Build - Simplified Design.

Leverages CMake's native install() rules instead of YAML configuration.
Each component's CMakeLists.txt defines what to install.
"""

import subprocess
import shutil
import yaml
from pathlib import Path
from typing import List, Optional

from .config import Config, Component
from .exceptions import InstallError


class Installer:
    """Installs built components using CMake's native install mechanism."""

    def __init__(self, config: Config, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.build_root = config.get_build_root()
        self.install_root = config.get_install_root()
        
        # Clean install root
        if self.install_root.exists():
            shutil.rmtree(self.install_root)
        self.install_root.mkdir(parents=True)

    def install_all(self):
        """Install all enabled components in build order."""
        failed = []
        
        for comp in self.config.get_build_order():
            if not comp.enabled:
                continue
            try:
                self.install_component(comp)
            except InstallError as e:
                print(f"⚠️  {comp.name}: {e}", file=__import__('sys').stderr)
                failed.append(comp.name)
        
        if failed:
            print(f"\n⚠️  Install warnings for: {', '.join(failed)}")
        
        self.generate_manifest()
        print(f"\n✅ Installed to {self.install_root}")

    def install_component(self, comp: Component):
        """Install a single component using cmake --install."""
        build_path = self.build_root / comp.name
        
        if not build_path.exists():
            raise InstallError(f"build directory not found: {build_path}")
        
        # Check if component has any installable targets
        cmake_cache = build_path / 'CMakeCache.txt'
        if not cmake_cache.exists():
            raise InstallError(f"not a cmake build directory: {build_path}")
        
        if self.verbose:
            print(f"   Installing {comp.name}...")
        
        # Run cmake --install with a component-specific prefix
        # This allows each component to install to its own subtree
        comp_install_dir = self.install_root / comp.name
        
        try:
            result = subprocess.run(
                ['cmake', '--install', str(build_path), '--prefix', str(comp_install_dir)],
                capture_output=True,
                text=True,
            )
            
            if result.returncode != 0:
                # Some components might not have install targets - that's ok
                if 'no install target' in result.stderr.lower() or \
                   'nothing to be done' in result.stderr.lower():
                    if self.verbose:
                        print(f"   {comp.name}: no install targets")
                    return
                raise InstallError(result.stderr.strip())
            
            if self.verbose and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    print(f"   {line}")
                    
            # Collect installed files for manifest
            self._collect_installed_files(comp, comp_install_dir)
                    
        except subprocess.CalledProcessError as e:
            raise InstallError(str(e))
        
        print(f"   ✅ {comp.name}")
    
    def _collect_installed_files(self, comp: Component, comp_install_dir: Path):
        """Collect all installed file paths for this component."""
        installed_files = []
        
        if not comp_install_dir.exists():
            return
        
        for item in comp_install_dir.rglob('*'):
            if item.is_file():
                # Get path relative to install root
                rel_path = item.relative_to(comp_install_dir)
                installed_files.append(str(rel_path))
        
        comp._installed_files = sorted(installed_files)

    def generate_manifest(self):
        """Generate deploy_manifest.yaml."""
        manifest_path = self.install_root / 'deploy_manifest.yaml'
        
        components_data = []
        for comp in self.config.get_enabled_components():
            data = {
                'name': comp.name,
                'description': comp.description,
                'type': comp.build.get('type', 'library') if comp.build else 'library',
                'dependencies': comp.dependencies.get('local', []),  # Only local deps for graph
            }
            
            # Add installed files
            installed_files = getattr(comp, '_installed_files', [])
            if installed_files:
                data['installed_files'] = installed_files
            
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


def install_to_flat_prefix(config: Config, prefix: Path, verbose: bool = False) -> Path:
    """
    Alternative installer that collects all components into a flat prefix.
    
    Instead of each component having its own subdirectory:
        dist/mshm/...
        dist/mcom/...
    
    It installs everything flat:
        dist/lib/...
        dist/include/...
        dist/bin/...
    
    This is useful for creating a deployable package.
    """
    # Build a unified install prefix
    unified_prefix = prefix / 'unified'
    
    if unified_prefix.exists():
        shutil.rmtree(unified_prefix)
    unified_prefix.mkdir(parents=True)
    
    for comp in config.get_build_order():
        if not comp.enabled:
            continue
        
        build_path = config.get_build_root() / comp.name
        if not build_path.exists():
            continue
        
        try:
            subprocess.run(
                ['cmake', '--install', str(build_path), '--prefix', str(unified_prefix)],
                capture_output=True,
                text=True,
                check=True,
            )
            if verbose:
                print(f"   ✅ {comp.name}")
        except subprocess.CalledProcessError as e:
            if verbose:
                print(f"   ⚠️  {comp.name}: {e.stderr.strip()}")
            continue
    
    return unified_prefix
