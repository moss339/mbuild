"""CMake-based component builder for MOSS Build."""

import subprocess
from pathlib import Path
from typing import Optional

from .config import Config, Component
from .git_manager import GitManager
from .exceptions import BuildError


class Builder:
    """Builds components using CMake."""

    def __init__(self, config: Config, build_dir: str, jobs: int = 4):
        self.config = config
        self.build_dir = Path(build_dir)
        self.jobs = jobs
        cache_dir = config.get_setting('cache_dir', '.moss/cache')
        self.git_manager = GitManager(cache_dir)

    def build_all(self):
        """Build all enabled components in dependency order."""
        order = self.config.get_build_order()
        for comp in order:
            self.build_component(comp)

    def build_component(self, comp: Component):
        """Build a single component."""
        if not comp.enabled:
            return

        # Sync source code
        src_path = self.git_manager.sync(comp)
        src_path = Path(src_path)

        # Create build directory
        build_path = self.build_dir / comp.local_path
        build_path.mkdir(parents=True, exist_ok=True)

        # Build type from settings
        build_type = self.config.get_setting('build_type', 'Release')

        # Run CMake
        cmake_opts = comp.build.get('cmake_options', [])
        cmake_args = [
            '-S', str(src_path),
            '-B', str(build_path),
            f'-DCMAKE_BUILD_TYPE={build_type}',
        ]
        for opt in cmake_opts:
            cmake_args.append(f'-D{opt}')

        self._run_cmake(cmake_args)
        self._run_build(str(build_path))

    def _run_cmake(self, args: list):
        """Run CMake configuration."""
        try:
            result = subprocess.run(
                ['cmake'] + args,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise BuildError(f"CMake configuration failed:\n{result.stderr}")
        except FileNotFoundError as e:
            raise BuildError("cmake not found. Please install CMake.") from e

    def _run_build(self, build_path: str):
        """Run CMake build."""
        try:
            result = subprocess.run(
                ['cmake', '--build', build_path, '--parallel', str(self.jobs)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise BuildError(f"Build failed:\n{result.stderr}")
        except FileNotFoundError as e:
            raise BuildError("cmake not found. Please install CMake.") from e
