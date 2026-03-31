"""MOSS Build configuration parsing - New Design.

Design principles:
1. moss.yaml - top-level manifest (declares components only)
2. build_options.yaml - global build options (C++ standard, flags, etc.)
3. component.yaml - component self-description (deps, build, install)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import yaml
from pathlib import Path
import os

from .exceptions import ConfigError, ComponentNotFoundError


@dataclass
class BuildOptions:
    """Global build options from build_options.yaml."""
    cxx_standard: str = "C++17"
    cxx_flags: List[str] = field(default_factory=list)
    defines: List[str] = field(default_factory=list)
    build_type: str = "Release"
    parallel_jobs: int = 8
    cmake_options: Dict[str, str] = field(default_factory=dict)
    platform_overrides: Dict[str, "BuildOptions"] = field(default_factory=dict)

    def merge(self, overrides: Dict[str, Any]) -> "BuildOptions":
        """Merge component-level overrides into global options."""
        result = BuildOptions(
            cxx_standard=overrides.get('cxx_standard', self.cxx_standard),
            cxx_flags=overrides.get('cxx_flags', self.cxx_flags.copy()),
            defines=overrides.get('defines', self.defines.copy()),
            build_type=overrides.get('build_type', self.build_type),
            parallel_jobs=overrides.get('parallel_jobs', self.parallel_jobs),
            cmake_options=overrides.get('cmake_options', self.cmake_options.copy()),
        )
        
        # Handle platform-specific overrides
        if 'platform_overrides' in overrides:
            for platform, opts in overrides['platform_overrides'].items():
                if isinstance(opts, dict):
                    result.platform_overrides[platform] = self.merge(opts)
        
        return result

    def to_cmake_args(self) -> List[str]:
        """Convert to CMake arguments."""
        args = []
        
        # C++ standard
        if self.cxx_standard:
            args.append(f'-DCMAKE_CXX_STANDARD={self.cxx_standard.replace("C++", "")}')
        
        # Build type
        args.append(f'-DCMAKE_BUILD_TYPE={self.build_type}')
        
        # CMake options
        for key, val in self.cmake_options.items():
            args.append(f'-D{key}={val}')
        
        # Defines
        for define in self.defines:
            args.append(f'-DCMAKE_CXX_FLAGS=-D{define}')
        
        # CXX flags
        if self.cxx_flags:
            flags_str = ' '.join(self.cxx_flags)
            args.append(f'-DCMAKE_CXX_FLAGS={flags_str}')
        
        return args


@dataclass
class InstallRule:
    """Install rule for a component."""
    install_type: str = "library"  # library | application
    headers: Optional[Dict[str, str]] = None  # {from: ..., to: ...}
    libraries: Optional[Dict[str, Any]] = None  # {from: ..., patterns: [...]}
    executables: Optional[Dict[str, Any]] = None
    configs: Optional[Dict[str, str]] = None
    runtime_deps: List[str] = field(default_factory=list)
    mode: int = 0o644


@dataclass
class Component:
    """A single component (from component.yaml)."""
    name: str
    description: str = ""
    
    # Source location
    source_root: str = "."  # relative to component.yaml location
    repository: Optional[Dict[str, str]] = None  # url, branch, commit
    
    # Dependencies (declared in component.yaml)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    #   local: ["mdds", "mshm"]
    #   system: ["pthread", "protobuf"]
    
    # Build config (component can inherit from global + override)
    build: Dict[str, Any] = field(default_factory=dict)
    
    # Install rules (component self-decides)
    install: Dict[str, Any] = field(default_factory=dict)
    
    enabled: bool = True
    
    # Resolved fields (populated after construction)
    _component_dir: Optional[Path] = field(default=None, repr=False)
    _build_options: Optional[BuildOptions] = field(default=None, repr=False)
    _resolved_local_deps: List[str] = field(default_factory=list, repr=False)
    
    def get_source_path(self, base_dir: Path) -> Path:
        """Get absolute source path."""
        if self.repository and self.repository.get('url'):
            # Remote component - source is in cache
            return base_dir / self.dependencies.get('_cache_path', self.name)
        else:
            # Local component
            return self._component_dir or base_dir
    
    def get_dependency_paths(self) -> Dict[str, str]:
        """Get local dependency component paths."""
        return self.dependencies.get('local', [])


@dataclass 
class MossManifest:
    """Top-level moss.yaml manifest."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    
    # Global build options file
    build_options_path: str = "./build_options.yaml"
    
    # Install settings
    install_root: str = "./dist"
    install_prefix: str = "/opt/moss"
    
    # Cache settings
    cache_dir: str = ".moss/cache"
    clone_depth: int = 1
    
    # Components list (simplified - just name + path/repository)
    components: List[Dict[str, Any]] = field(default_factory=list)
    
    # Resolved
    _components: List[Component] = field(default_factory=list, init=False)
    _build_options: BuildOptions = field(default_factory=BuildOptions, init=False)
    _manifest_dir: Optional[Path] = field(default=None, init=False, repr=False)


class Config:
    """MOSS Build configuration loader - New Design."""
    
    def __init__(self, manifest: MossManifest):
        self.manifest = manifest
        self._components_map: Dict[str, Component] = {}
    
    @classmethod
    def from_yaml(cls, yaml_path: str, find_root: bool = True) -> "Config":
        """Parse configuration from moss.yaml and component.yaml files.
        
        Args:
            yaml_path: Path to moss.yaml
            find_root: If True, search up from yaml_path for moss.yaml
        """
        yaml_path = Path(yaml_path).resolve()
        
        # Find project root (contains moss.yaml)
        if find_root:
            root_dir = cls._find_project_root(yaml_path)
        else:
            root_dir = yaml_path.parent
        
        manifest_path = root_dir / 'moss.yaml'
        if not manifest_path.exists():
            raise ConfigError(f"moss.yaml not found in {root_dir}")
        
        # Parse moss.yaml
        manifest = cls._parse_manifest(manifest_path)
        manifest._manifest_dir = root_dir
        
        # Load global build options
        build_options_path = root_dir / manifest.build_options_path
        if build_options_path.exists():
            manifest._build_options = cls._parse_build_options(build_options_path)
        else:
            manifest._build_options = BuildOptions()
        
        # Parse component.yaml for each declared component
        components = []
        for comp_decl in manifest.components:
            comp = cls._parse_component(
                comp_decl, 
                root_dir,
                manifest._build_options
            )
            components.append(comp)
        
        manifest._components = components
        
        config = cls(manifest)
        config._components_map = {c.name: c for c in components}
        
        # Resolve inter-component dependencies
        config._resolve_local_deps(root_dir)
        
        return config
    
    @classmethod
    def _find_project_root(cls, path: Path) -> Path:
        """Find project root by searching up for moss.yaml."""
        current = path.parent if path.is_file() else path
        while current != current.parent:
            if (current / 'moss.yaml').exists():
                return current
            current = current.parent
        return path.parent if path.is_file() else path
    
    @classmethod
    def _parse_manifest(cls, path: Path) -> MossManifest:
        """Parse moss.yaml manifest file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        settings = data.get('settings', {})
        
        return MossManifest(
            name=data.get('name', 'moss'),
            description=data.get('description', ''),
            version=data.get('version', '1.0.0'),
            build_options_path=settings.get('build_options', './build_options.yaml'),
            install_root=settings.get('install_root', './dist'),
            install_prefix=settings.get('install_prefix', '/opt/moss'),
            cache_dir=settings.get('cache_dir', '.moss/cache'),
            clone_depth=settings.get('clone_depth', 1),
            components=data.get('components', []),
        )
    
    @classmethod
    def _parse_build_options(cls, path: Path) -> BuildOptions:
        """Parse build_options.yaml."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f) or {}
        
        return BuildOptions(
            cxx_standard=data.get('cxx_standard', 'C++17'),
            cxx_flags=data.get('cxx_flags', []),
            defines=data.get('defines', []),
            build_type=data.get('build_type', 'Release'),
            parallel_jobs=data.get('parallel_jobs', 8),
            cmake_options=data.get('cmake_options', {}),
        )
    
    @classmethod
    def _parse_component(
        cls, 
        comp_decl: Dict[str, Any], 
        root_dir: Path,
        global_build_options: BuildOptions
    ) -> Component:
        """Parse a component from declaration + component.yaml."""
        name = comp_decl.get('name')
        if not name:
            raise ConfigError("Component declaration missing 'name'")
        
        # Determine component directory
        if 'path' in comp_decl:
            # Local path relative to root
            comp_dir = root_dir / comp_decl['path']
        elif 'repository' in comp_decl:
            # Will be cloned later
            comp_dir = root_dir / cls._get_cache_path(comp_decl)
        else:
            raise ConfigError(f"Component '{name}' must have 'path' or 'repository'")
        
        # Parse component.yaml if exists
        component_yaml = comp_dir / 'component.yaml'
        if component_yaml.exists():
            with open(component_yaml, 'r') as f:
                comp_data = yaml.safe_load(f) or {}
        else:
            comp_data = {}
        
        # Merge build options (inherit global + override)
        build_inherit = comp_data.get('build', {}).get('inherit')
        if build_inherit:
            inherit_path = comp_dir / build_inherit
            if inherit_path.exists():
                inherited = cls._parse_build_options(inherit_path)
                build_overrides = comp_data.get('build', {})
                merged_build_opts = inherited.merge(build_overrides)
            else:
                merged_build_opts = global_build_options.merge(comp_data.get('build', {}))
        else:
            merged_build_opts = global_build_options.merge(comp_data.get('build', {}))
        
        comp_data['name'] = name
        comp_data['enabled'] = comp_decl.get('enabled', True)
        
        # Repository info from declaration (takes precedence)
        if 'repository' in comp_decl:
            comp_data['repository'] = comp_decl['repository']
        
        # Create component and set resolved fields
        comp = Component(**{k: v for k, v in comp_data.items() if k in Component.__dataclass_fields__})
        comp._component_dir = comp_dir
        comp._build_options = merged_build_opts
        
        return comp
    
    @classmethod
    def _get_cache_path(cls, comp_decl: Dict[str, Any]) -> str:
        """Get cache path for a remote component."""
        repo = comp_decl.get('repository', {})
        url = repo.get('url', '')
        if url:
            # Extract repo name from URL
            return url.rstrip('/').split('/')[-1].replace('.git', '')
        return comp_decl.get('name', 'unknown')
    
    def _resolve_local_deps(self, root_dir: Path):
        """Resolve local dependency paths and store in _resolved_local_deps."""
        for comp in self.manifest._components:
            resolved_local_paths = []
            
            # Local dependencies - resolve to paths
            for dep_name in comp.dependencies.get('local', []):
                if dep_name in self._components_map:
                    dep_comp = self._components_map[dep_name]
                    resolved_local_paths.append(str(dep_comp._component_dir.relative_to(root_dir)))
            
            # Store resolved paths separately (keep original names intact)
            comp._resolved_local_deps = resolved_local_paths
    
    # ---- Public API ----
    
    def get_component(self, name: str) -> Component:
        """Get a component by name."""
        if name not in self._components_map:
            raise ComponentNotFoundError(f"Component not found: {name}")
        return self._components_map[name]
    
    def get_enabled_components(self) -> List[Component]:
        """Get all enabled components."""
        return [c for c in self.manifest._components if c.enabled]
    
    def get_build_order(self) -> List[Component]:
        """Get components in topological build order."""
        from .deps import topological_sort
        return topological_sort(self.get_enabled_components())
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a manifest setting value."""
        return getattr(self.manifest, key, default)
    
    def get_build_options(self, component: Component) -> BuildOptions:
        """Get merged build options for a component."""
        return component._build_options or self.manifest._build_options
    
    def get_cache_dir(self) -> Path:
        """Get absolute cache directory path."""
        if self.manifest._manifest_dir:
            return self.manifest._manifest_dir / self.manifest.cache_dir
        return Path(self.manifest.cache_dir)
    
    def get_build_root(self) -> Path:
        """Get absolute build directory path."""
        if self.manifest._manifest_dir:
            return self.manifest._manifest_dir / 'build'
        return Path('build')
    
    def get_install_root(self) -> Path:
        """Get absolute install directory path."""
        if self.manifest._manifest_dir:
            return self.manifest._manifest_dir / self.manifest.install_root
        return Path(self.manifest.install_root)
