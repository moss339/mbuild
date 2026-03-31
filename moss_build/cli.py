"""MOSS Build CLI - Command line interface - New Design."""

import click
import sys
from pathlib import Path

from .config import Config
from .git_manager import GitManager
from .builder import Builder
from .installer import Installer
from .deps import topological_sort
from .exceptions import MossBuildError, ConfigError, ComponentNotFoundError


DEFAULT_CONFIG = 'moss.yaml'


@click.group()
@click.version_option(version='0.2.0')
def cli():
    """MOSS Build System - Universal build tool with component self-description."""
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

    except MossBuildError as e:
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

    except MossBuildError as e:
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

    except MossBuildError as e:
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
            system_deps = comp.dependencies.get('system', [])
            
            deps_str = ""
            if local_deps:
                deps_str += f"  Local deps: {', '.join(local_deps)}"
            if system_deps:
                deps_str += f"  System: {', '.join(system_deps)}"
            if not deps_str:
                deps_str = "  (no dependencies)"
            
            click.echo(f"{i}. [{status}] {comp.name}")
            click.echo(f"   {comp.description or 'No description'}")
            click.echo(f"   {deps_str}")
            click.echo("")

    except MossBuildError as e:
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

    except MossBuildError as e:
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

    except MossBuildError as e:
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

    except MossBuildError as e:
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

    except MossBuildError as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
