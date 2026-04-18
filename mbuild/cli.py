"""MBuild CLI - Command line interface."""

import click
import sys
from pathlib import Path

from .config import Config
from .git_manager import GitManager
from .builder import Builder
from .installer import Installer
from .deployer import Deployer
from .cross_compile import CrossCompiler
from .deps import topological_sort
from .exceptions import MBuildError, ConfigError, ComponentNotFoundError


DEFAULT_CONFIG = 'moss.yaml'


@click.group()
@click.version_option(version='0.2.0')
def cli():
    """MBuild - Universal build tool with component self-description."""
    pass


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file (moss.yaml)')
@click.option('-j', '--jobs', default=4, help='Number of parallel jobs')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
def build(config: str, jobs: int, verbose: bool):
    """Build all components in dependency order."""
    try:
        cfg = Config.from_yaml(config)
        
        if verbose:
            click.echo(f"Build root: {cfg.get_build_root()}")
            click.echo(f"Cache dir: {cfg.get_cache_dir()}")
            click.echo(f"Components: {len(cfg.get_enabled_components())}")
            click.echo("")

        # Sync all remote sources first
        git_manager = GitManager(cfg.get_cache_dir())
        for comp in cfg.get_enabled_components():
            if comp.repository and comp.repository.get('url'):
                if verbose:
                    click.echo(f"Syncing {comp.name} from {comp.repository['url']}...")
                git_manager.sync(comp)

        # Build
        builder = Builder(cfg, jobs=jobs, verbose=verbose)
        builder.build_all()

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def sync(config: str):
    """Sync (clone/update) all remote component sources."""
    try:
        cfg = Config.from_yaml(config)
        git_manager = GitManager(cfg.get_cache_dir())

        for comp in cfg.get_enabled_components():
            if comp.repository and comp.repository.get('url'):
                click.echo(f"Syncing {comp.name}...")
                path = git_manager.sync(comp)
                click.echo(f"  -> {path}")
            else:
                click.echo(f"  {comp.name}: local, no sync needed")
        
        click.echo("\n✅ Sync complete!")

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
def install(config: str, verbose: bool):
    """Install all components based on their install rules."""
    try:
        cfg = Config.from_yaml(config)
        
        if verbose:
            click.echo(f"Install root: {cfg.get_install_root()}")
            click.echo("")

        installer = Installer(cfg, verbose=verbose)
        installer.install_all()

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def list(config: str):
    """List all components with their dependencies."""
    try:
        cfg = Config.from_yaml(config)
        order = cfg.get_build_order()

        click.echo(f"Project: {cfg.manifest.name}")
        click.echo(f"Components ({len(order)}):\n")
        
        for i, comp in enumerate(order, 1):
            status = "✅" if comp.enabled else "❌"
            local_deps = comp.dependencies.get('local', [])
            
            deps_str = f"  deps: {', '.join(local_deps)}" if local_deps else "  (no dependencies)"
            
            click.echo(f"{i}. [{status}] {comp.name}")
            click.echo(f"   {comp.description or 'No description'}")
            click.echo(f"   {deps_str}")
            click.echo("")

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
@click.option('-v', '--verbose', is_flag=True, help='Show dependency details')
def deps(config: str, verbose: bool):
    """Show component dependencies (topological order)."""
    try:
        cfg = Config.from_yaml(config)
        order = cfg.get_build_order()

        click.echo("Dependency build order:\n")
        for i, comp in enumerate(order, 1):
            local_deps = comp.dependencies.get('local', [])
            deps_str = ', '.join(local_deps) if local_deps else "(none)"
            
            click.echo(f"{i}. {comp.name}")
            if verbose:
                click.echo(f"   depends on: {deps_str}")
            else:
                click.echo(f"   -> {deps_str}")
            click.echo("")

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def validate(config: str):
    """Validate the moss.yaml and component.yaml files."""
    try:
        cfg = Config.from_yaml(config)
        
        click.echo(f"✅ Configuration valid: {config}")
        click.echo(f"   Project: {cfg.manifest.name}")
        click.echo(f"   Build options: {cfg.manifest.build_options_path}")
        click.echo(f"   Total components: {len(cfg.manifest._components)}")
        click.echo(f"   Enabled: {len(cfg.get_enabled_components())}")
        
        # Validate dependency graph
        order = cfg.get_build_order()
        click.echo(f"\n📋 Build order ({len(order)} steps):")
        for i, comp in enumerate(order, 1):
            click.echo(f"   {i}. {comp.name}")
        
        # Check for missing dependencies
        click.echo("\n🔍 Checking dependencies...")
        missing = []
        for comp in cfg.get_enabled_components():
            for dep_name in comp.dependencies.get('local', []):
                try:
                    cfg.get_component(dep_name)
                except ComponentNotFoundError:
                    missing.append(f"{comp.name} -> {dep_name}")
        
        if missing:
            click.echo("   ⚠️  Missing dependencies:")
            for m in missing:
                click.echo(f"      {m}")
        else:
            click.echo("   ✅ All dependencies resolved")
        
        click.echo("\n✅ Validation passed!")

    except MBuildError as e:
        click.echo(f"❌ Validation failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
@click.option('-v', '--verbose', is_flag=True, help='Show what would be cleaned')
def clean(config: str, verbose: bool):
    """Clean build and install directories."""
    try:
        cfg = Config.from_yaml(config)
        
        import shutil
        
        # Clean build directory
        build_root = cfg.get_build_root()
        if build_root.exists():
            if verbose:
                for p in build_root.rglob('*'):
                    print(f"   rm -rf {p}")
            shutil.rmtree(build_root)
            click.echo(f"Removed {build_root}")
        else:
            click.echo("No build directory to clean")
        
        # Clean install directory
        install_root = cfg.get_install_root()
        if install_root.exists():
            if verbose:
                for p in install_root.rglob('*'):
                    print(f"   rm -rf {p}")
            shutil.rmtree(install_root)
            click.echo(f"Removed {install_root}")
        else:
            click.echo("No install directory to clean")

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def tree(config: str):
    """Show component tree (what would be built, installed)."""
    try:
        cfg = Config.from_yaml(config)
        
        click.echo(f"Project: {cfg.manifest.name}")
        click.echo(f"Install root: {cfg.get_install_root()}\n")
        
        for comp in cfg.get_build_order():
            icon = "📦" if comp.enabled else "📦❌"
            install_type = comp.install.get('type', 'library') if comp.install else 'library'
            
            click.echo(f"{icon} {comp.name} [{install_type}]")
            
            # Source
            if comp.repository and comp.repository.get('url'):
                click.echo(f"   source: {comp.repository['url']}")
                if comp.repository.get('branch'):
                    click.echo(f"   branch: {comp.repository['branch']}")
            else:
                click.echo(f"   source: local")
            
            # Dependencies
            local_deps = comp.dependencies.get('local', [])
            if local_deps:
                click.echo(f"   deps: {', '.join(local_deps)}")
            
            # Build options
            opts = cfg.get_build_options(comp)
            click.echo(f"   build: {opts.build_type}, {opts.cxx_standard}")
            click.echo("")

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('prefix', default='./dist')
@click.option('--strip', is_flag=True, help='Strip debug symbols')
@click.option('--generate-env/--no-generate-env', default=True, help='Generate environment setup script')
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
def deploy(prefix: str, strip: bool, generate_env: bool, config: str, verbose: bool):
    """Deploy all components to specified directory.

    Examples:
        mbuild deploy /opt/moss
        mbuild deploy --strip --generate-env /usr/local/moss
    """
    try:
        cfg = Config.from_yaml(config)

        deployer = Deployer(cfg, verbose=verbose)
        deployer.deploy(Path(prefix), strip=strip, generate_env=generate_env)

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command('cross-build')
@click.option('--toolchain', help='CMake toolchain file path')
@click.option('--target', help='Target triple (e.g., aarch64-linux-gnu)')
@click.option('--sysroot', help='Sysroot path for target')
@click.option('-j', '--jobs', default=8, help='Number of parallel jobs')
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
def cross_build(toolchain: str, target: str, sysroot: str, jobs: int, config: str, verbose: bool):
    """Cross-compile for target platform.

    Examples:
        mbuild cross-build --target aarch64-linux-gnu
        mbuild cross-build --toolchain toolchain-armhf.cmake
        mbuild cross-build --target aarch64-linux-gnu --sysroot /opt/sysroot-aarch64
    """
    try:
        cfg = Config.from_yaml(config)

        if not target and not toolchain:
            click.echo("❌ Error: --target or --toolchain is required", err=True)
            sys.exit(1)

        cross = CrossCompiler(cfg, verbose=verbose)

        if target:
            if not cross.check_toolchain(target):
                click.echo(f"❌ Error: Cross-compiler for {target} not found", err=True)
                click.echo(f"   Install with: sudo apt-get install gcc-{target} g++-{target}")
                sys.exit(1)

        cross.build(target=target or '', toolchain=toolchain, sysroot=sysroot, jobs=jobs)

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command('cross-targets')
def cross_targets():
    """List supported cross-compilation targets."""
    try:
        cfg = Config.from_yaml(DEFAULT_CONFIG)
        cross = CrossCompiler(cfg)
        cross.list_targets()
    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('prefix')
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def undeploy(prefix: str, config: str):
    """Remove deployed files from specified directory.

    Examples:
        mbuild undeploy /opt/moss
    """
    try:
        cfg = Config.from_yaml(config)

        deployer = Deployer(cfg)
        deployer.undeploy(Path(prefix))

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
@click.option('--only', help='Only show status for specified component')
def status(config: str, only: str):
    """Show build status of all components."""
    try:
        cfg = Config.from_yaml(config)
        build_root = cfg.get_build_root()

        click.echo(f"Build root: {build_root}\n")
        click.echo("Component Status:\n")

        for comp in cfg.get_build_order():
            if only and comp.name != only:
                continue

            build_path = build_root / comp.name

            if build_path.exists():
                cmake_cache = build_path / 'CMakeCache.txt'
                if cmake_cache.exists():
                    click.echo(f"  ✅ {comp.name}: built")
                else:
                    click.echo(f"  🔧 {comp.name}: configured (not built)")
            else:
                click.echo(f"  ❌ {comp.name}: not built")

    except MBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
