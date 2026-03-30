"""MOSS Build exceptions."""


class MossBuildError(Exception):
    """Base exception for moss-build."""
    pass


class ConfigError(MossBuildError):
    """Configuration related errors."""
    pass


class GitError(MossBuildError):
    """Git operations errors."""
    pass


class BuildError(MossBuildError):
    """Build related errors."""
    pass


class DependencyCycleError(MossBuildError):
    """Circular dependency detected."""
    pass


class ComponentNotFoundError(MossBuildError):
    """Component not found in configuration."""
    pass
