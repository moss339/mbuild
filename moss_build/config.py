"""MOSS Build configuration parsing."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import yaml
from pathlib import Path

from .exceptions import ConfigError, ComponentNotFoundError


@dataclass
class Component:
    """A single component in the build system."""
    name: str
    repository: Dict[str, Any]  # url, branch, commit
    local_path: str
    build: Dict[str, Any]       # type, language, cmake_options
    dependencies: List[Dict]    # list of {name, local_path}
    install: Dict[str, Any]     # artifacts
    enabled: bool = True


@dataclass
class Config:
    """MOSS Build configuration."""
    settings: Dict[str, Any]
    components: List[Component] = field(default_factory=list)
    _components_map: Dict[str, Component] = field(default_factory=dict, init=False)

    def __post_init__(self):
        self._components_map = {c.name: c for c in self.components}

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Config":
        """Parse configuration from YAML file."""
        path = Path(yaml_path)
        if not path.exists():
            raise ConfigError(f"Configuration file not found: {yaml_path}")

        with open(path, 'r') as f:
            data = yaml.safe_load(f)

        if not data:
            raise ConfigError(f"Empty configuration file: {yaml_path}")

        components = []
        for comp_data in data.get('components', []):
            repo = comp_data.get('repository', {})
            components.append(Component(
                name=comp_data['name'],
                repository={
                    'url': repo.get('url', ''),
                    'branch': repo.get('branch', 'main'),
                    'commit': repo.get('commit'),
                },
                local_path=comp_data.get('local_path', comp_data['name']),
                build=comp_data.get('build', {}),
                dependencies=comp_data.get('dependencies', []),
                install=comp_data.get('install', {}),
                enabled=comp_data.get('enabled', True),
            ))

        return cls(
            settings=data.get('settings', {}),
            components=components,
        )

    def get_component(self, name: str) -> Component:
        """Get a component by name."""
        if name not in self._components_map:
            raise ComponentNotFoundError(f"Component not found: {name}")
        return self._components_map[name]

    def get_enabled_components(self) -> List[Component]:
        """Get all enabled components."""
        return [c for c in self.components if c.enabled]

    def get_build_order(self) -> List[Component]:
        """Get components in topological build order."""
        from .deps import topological_sort
        return topological_sort(self.get_enabled_components())

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)
