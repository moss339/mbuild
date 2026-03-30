"""MOSS Build CLI - Command line interface."""

import click
import sys
from pathlib import Path

from .config import Config
from .git_manager import GitManager
from .builder import Builder
from .installer import Installer
from .deps import topological_sort
from .exceptions import MossBuildError


DEFAULT_CONFIG = 'moss.yaml'


@click.group()
def cli():
    """MOSS Build System - Universal build tool."""
    pass


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
@click.option('-j', '--jobs', default=4, help='Number of parallel jobs')
def build(config: str, jobs: int):
    """Build all components."""
    try:
        cfg = Config.from_yaml(config)
        build_root = cfg.get_setting('build_root', './build')

        # Sync all sources first
        cache_dir = cfg.get_setting('cache_dir', '.moss/cache')
        git_manager = GitManager(cache_dir)
        for comp in cfg.get_enabled_components():
            click.echo(f"Syncing {comp.name}...")
            git_manager.sync(comp)

        # Build
        builder = Builder(cfg, build_root, jobs)
        click.echo(f"Building components with {jobs} parallel jobs...")
        builder.build_all()
        click.echo("Build complete!")

    except MossBuildError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def sync(config: str):
    """Sync all component sources."""
    try:
        cfg = Config.from_yaml(config)
        cache_dir = cfg.get_setting('cache_dir', '.moss/cache')
        git_manager = GitManager(cache_dir)

        for comp in cfg.get_enabled_components():
            click.echo(f"Syncing {comp.name}...")
            path = git_manager.sync(comp)
            click.echo(f"  -> {path}")
        click.echo("Sync complete!")

    except MossBuildError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def install(config: str):
    """Install all components."""
    try:
        cfg = Config.from_yaml(config)
        install_root = cfg.get_setting('install_root', './dist')

        installer = Installer(cfg, install_root)
        click.echo(f"Installing to {install_root}...")
        installer.install_all()
        click.echo("Install complete!")

    except MossBuildError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def list(config: str):
    """List all components."""
    try:
        cfg = Config.from_yaml(config)
        order = cfg.get_build_order()

        click.echo(f"Components ({len(order)}):")
        for i, comp in enumerate(order, 1):
            status = "enabled" if comp.enabled else "disabled"
            deps = [d.get('name') for d in comp.dependencies]
            deps_str = f" (deps: {', '.join(deps)})" if deps else ""
            click.echo(f"  {i}. {comp.name} [{status}]{deps_str}")

    except MossBuildError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def deps(config: str):
    """Show component dependencies."""
    try:
        cfg = Config.from_yaml(config)
        order = cfg.get_build_order()

        click.echo("Dependency build order:")
        for i, comp in enumerate(order, 1):
            deps = [d.get('name') for d in comp.dependencies]
            deps_str = ', '.join(deps) if deps else "(none)"
            click.echo(f"  {i}. {comp.name}")
            click.echo(f"     depends on: {deps_str}")

    except MossBuildError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('-c', '--config', default=DEFAULT_CONFIG, help='Configuration file')
def validate(config: str):
    """Validate the configuration file."""
    try:
        cfg = Config.from_yaml(config)
        click.echo(f"Configuration valid: {config}")
        click.echo(f"  Name: {cfg.settings.get('name', 'unnamed')}")
        click.echo(f"  Components: {len(cfg.components)}")
        click.echo(f"  Enabled: {len(cfg.get_enabled_components())}")

        # Validate dependency graph
        order = cfg.get_build_order()
        click.echo(f"  Dependency order: {[c.name for c in order]}")
        click.echo("Validation passed!")

    except MossBuildError as e:
        click.echo(f"Validation failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def clean():
    """Clean build artifacts."""
    build_root = Path('./build')
    install_root = Path('./dist')

    if build_root.exists():
        import shutil
        shutil.rmtree(build_root)
        click.echo(f"Removed {build_root}")
    else:
        click.echo("No build directory to clean")

    if install_root.exists():
        import shutil
        shutil.rmtree(install_root)
        click.echo(f"Removed {install_root}")
    else:
        click.echo("No install directory to clean")


if __name__ == '__main__':
    cli()
