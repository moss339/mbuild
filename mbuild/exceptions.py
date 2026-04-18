"""MBuild exceptions."""


class MBuildError(Exception):
    """Base exception for mbuild."""
    pass


class ConfigError(MBuildError):
    """Configuration related errors."""
    pass


class GitError(MBuildError):
    """Git operations errors."""
    pass


class BuildError(MBuildError):
    """Build related errors."""
    pass


class InstallError(MBuildError):
    """Install related errors."""
    pass


class DependencyCycleError(MBuildError):
    """Circular dependency detected."""
    pass


class ComponentNotFoundError(MBuildError):
    """Component not found in configuration."""
    pass


class DeployError(MBuildError):
    """Deployment related errors."""
    pass


class CrossCompileError(MBuildError):
    """Cross-compilation related errors."""
    pass