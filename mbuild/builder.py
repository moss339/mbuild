"""CMake-based component builder for MOSS Build - New Design."""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Dict

from .config import Config, Component, BuildOptions
from .git_manager import GitManager
from .exceptions import BuildError


class Builder:
    """Builds components using CMake."""

    def __init__(self, config: Config, jobs: int = 4, verbose: bool = False):
        self.config = config
        self.jobs = jobs
        self.verbose = verbose
        self.git_manager = GitManager(config.get_cache_dir())
        self.build_root = config.get_build_root()
        self.build_root.mkdir(parents=True, exist_ok=True)

    def build_all(self):
        """Build all enabled components in dependency order."""
        order = self.config.get_build_order()
        failed = []
        
        for comp in order:
            try:
                self.build_component(comp)
            except BuildError as e:
                print(f"❌ {comp.name}: build failed", file=sys.stderr)
                print(f"   {e}", file=sys.stderr)
                failed.append(comp.name)
        
        if failed:
            raise BuildError(f"Build failed for: {', '.join(failed)}")
        
        print(f"✅ All {len(order)} components built successfully")

    def build_component(self, comp: Component):
        """Build a single component."""
        if not comp.enabled:
            return

        print(f"📦 Building {comp.name}...")

        # Get source (sync if remote)
        src_path = Path(self.git_manager.sync(comp))

        if not src_path.exists():
            raise BuildError(f"Source path not found: {src_path}")

        # Create build directory
        build_path = self.build_root / comp.name
        build_path.mkdir(parents=True, exist_ok=True)

        # Get build options (merged global + component)
        build_opts = self.config.get_build_options(comp)

        # Run CMake configuration
        cmake_args = self._build_cmake_args(src_path, build_path, build_opts, comp)

        if self.verbose:
            print(f"   cmake {' '.join(cmake_args)}")

        self._run_cmake(cmake_args)

        # Run build
        self._run_build(str(build_path))

        # Fixup: Copy Targets.cmake to cmake/ dir for find_package from build tree
        self._fixup_cmake_config(build_path, comp.name)

        print(f"   ✅ {comp.name} built")

    def _fixup_cmake_config(self, build_path: Path, comp_name: str):
        """Fix CMake config files for find_package from build tree.

        CMake generates *Targets.cmake in build root, but *Config.cmake
        expects it in the same cmake/ subdirectory. This copies it there.
        """
        targets_file = build_path / f'{comp_name}Targets.cmake'
        cmake_dir = build_path / 'cmake'

        if targets_file.exists() and cmake_dir.exists():
            import shutil
            dest = cmake_dir / f'{comp_name}Targets.cmake'
            shutil.copy2(targets_file, dest)

    def _build_cmake_args(self, src: Path, build: Path, opts: BuildOptions, comp: Component) -> List[str]:
        """Build CMake arguments."""
        args = [
            '-S', str(src),
            '-B', str(build),
        ]

        # Add build options
        args.extend(opts.to_cmake_args())

        # Build CMAKE_PREFIX_PATH from ALL already-built components
        # This handles transitive dependencies (e.g., mdds -> mshm)
        prefix_paths = []
        rpath_dirs = []

        for built_comp in self.build_root.iterdir():
            if built_comp.is_dir() and built_comp.name != comp.name:
                cmake_dir = built_comp / 'cmake'
                if cmake_dir.exists():
                    prefix_paths.append(str(built_comp))
                lib_dir = built_comp / 'lib'
                if lib_dir.exists():
                    rpath_dirs.append(str(lib_dir))

        # Add proto/build for protobuf definitions
        proto_build = self.config.get_manifest_dir() / 'proto' / 'build'
        if proto_build.exists():
            prefix_paths.append(str(proto_build))

        if prefix_paths:
            args.append(f'-DCMAKE_PREFIX_PATH={";".join(prefix_paths)}')

        if rpath_dirs:
            rpath = ':'.join(rpath_dirs)
            args.append(f'-DCMAKE_INSTALL_RPATH={rpath}')

        return args

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
            elif self.verbose:
                print(result.stdout)
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
            elif self.verbose:
                print(result.stdout)
        except FileNotFoundError as e:
            raise BuildError("cmake not found. Please install CMake.") from e
