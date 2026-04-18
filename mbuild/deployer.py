"""Deployer - Deploy built components to target directory."""

import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import yaml

from .config import Config, Component
from .exceptions import MBuildError, DeployError


class Deployer:
    """Deploys built components to a target directory."""

    def __init__(self, config: Config, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.build_root = config.get_build_root()

    def deploy(self, prefix: Path, strip: bool = False, generate_env: bool = True):
        """Deploy all components to prefix directory.

        Args:
            prefix: Target deployment directory
            strip: Whether to strip debug symbols
            generate_env: Whether to generate environment setup script
        """
        prefix = Path(prefix).resolve()

        if self.verbose:
            print(f"Deploying to: {prefix}")

        # Create directory structure
        self._create_layout(prefix)

        # Deploy each component
        components = self.config.get_build_order()
        deployed = []

        for comp in components:
            try:
                files = self._deploy_component(comp, prefix, strip)
                deployed.append({
                    'name': comp.name,
                    'version': comp.version or '1.0.0',
                    'files': files
                })
                if self.verbose:
                    print(f"  ✅ {comp.name}")
            except DeployError as e:
                print(f"  ❌ {comp.name}: {e}", file=sys.stderr)

        # Generate manifest
        self._generate_manifest(prefix, deployed)

        # Generate environment script
        if generate_env:
            self._generate_env_script(prefix)

        print(f"\n✅ Deployed {len(deployed)} components to {prefix}")

        # Print usage hint
        print(f"\nTo use MOSS:")
        print(f"  source {prefix}/share/moss/setup_env.sh")

    def _create_layout(self, prefix: Path):
        """Create deployment directory layout."""
        dirs = [
            prefix / 'lib',
            prefix / 'lib64',
            prefix / 'include',
            prefix / 'bin',
            prefix / 'cmake',
            prefix / 'share' / 'moss',
            prefix / 'libexec',
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _deploy_component(self, comp: Component, prefix: Path, strip: bool) -> List[str]:
        """Deploy a single component."""
        build_path = self.build_root / comp.name
        if not build_path.exists():
            raise DeployError(f"Build directory not found: {build_path}")

        deployed_files = []

        # Deploy libraries
        lib_dirs = [build_path / 'src', build_path]
        for lib_dir in lib_dirs:
            if lib_dir.exists():
                for lib in lib_dir.glob('lib*.so*'):
                    dest = prefix / 'lib' / lib.name
                    shutil.copy2(lib, dest)
                    deployed_files.append(f'lib/{lib.name}')

                    if strip:
                        subprocess.run(['strip', str(dest)], capture_output=True)

        # Deploy headers
        src_path = Path(comp.path)
        include_src = src_path / 'include'
        if include_src.exists():
            for header_dir in include_src.iterdir():
                if header_dir.is_dir():
                    dest = prefix / 'include' / header_dir.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(header_dir, dest)
                    deployed_files.append(f'include/{header_dir.name}/')

        # Deploy CMake config files
        cmake_src = build_path
        for cmake_file in cmake_src.glob('*Config.cmake'):
            cmake_dest_dir = prefix / 'cmake' / comp.name
            cmake_dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cmake_file, cmake_dest_dir / cmake_file.name)
            deployed_files.append(f'cmake/{comp.name}/{cmake_file.name}')

        for cmake_file in cmake_src.glob('*Targets.cmake'):
            cmake_dest_dir = prefix / 'cmake' / comp.name
            cmake_dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cmake_file, cmake_dest_dir / cmake_file.name)
            deployed_files.append(f'cmake/{comp.name}/{cmake_file.name}')

        # Deploy executables
        for exe in build_path.glob('**/mcom*'):
            if exe.is_file() and not exe.suffix:
                dest = prefix / 'bin' / exe.name
                shutil.copy2(exe, dest)
                dest.chmod(0o755)
                deployed_files.append(f'bin/{exe.name}')

        for exe in build_path.glob('**/mexem'):
            if exe.is_file():
                dest = prefix / 'bin' / exe.name
                shutil.copy2(exe, dest)
                dest.chmod(0o755)
                deployed_files.append(f'bin/{exe.name}')

        return deployed_files

    def _generate_manifest(self, prefix: Path, deployed: List[dict]):
        """Generate deployment manifest."""
        manifest = {
            'name': self.config.manifest.name,
            'version': self.config.manifest.version or '1.0.0',
            'deploy_time': datetime.now().isoformat(),
            'deploy_path': str(prefix),
            'components': deployed,
            'environment': {
                'LD_LIBRARY_PATH': f'{prefix}/lib',
                'CMAKE_PREFIX_PATH': f'{prefix}/cmake',
                'PATH': f'{prefix}/bin',
            }
        }

        manifest_path = prefix / 'share' / 'moss' / 'manifest.yaml'
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False)

    def _generate_env_script(self, prefix: Path):
        """Generate environment setup script."""
        script = f'''#!/bin/bash
# MOSS Environment Setup
# Generated by mbuild deploy

export MOSS_ROOT="{prefix}"
export LD_LIBRARY_PATH="${{MOSS_ROOT}}/lib${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
export CMAKE_PREFIX_PATH="${{MOSS_ROOT}}/cmake${{CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}}"
export PATH="${{MOSS_ROOT}}/bin${{PATH:+:$PATH}}"

# For pkg-config
export PKG_CONFIG_PATH="${{MOSS_ROOT}}/lib/pkgconfig${{PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}}"

echo "MOSS environment configured:"
echo "  MOSS_ROOT=${{MOSS_ROOT}}"
echo "  LD_LIBRARY_PATH includes ${{MOSS_ROOT}}/lib"
echo "  PATH includes ${{MOSS_ROOT}}/bin"
'''

        script_path = prefix / 'share' / 'moss' / 'setup_env.sh'
        with open(script_path, 'w') as f:
            f.write(script)
        script_path.chmod(0o755)

    def undeploy(self, prefix: Path):
        """Remove deployed files."""
        prefix = Path(prefix).resolve()

        if not prefix.exists():
            print(f"Deployment directory not found: {prefix}")
            return

        # Confirm before removing
        print(f"This will remove: {prefix}")

        # Remove the directory
        shutil.rmtree(prefix)
        print(f"✅ Removed {prefix}")
