"""Dependency resolution with topological sort."""

from typing import List, Dict, Set, Optional
from .config import Component
from .exceptions import DependencyCycleError


def topological_sort(components: List[Component]) -> List[Component]:
    """
    Sort components by dependency order using Kahn's algorithm.

    Returns components in build order (dependencies first).
    Raises DependencyCycleError if circular dependency detected.
    """
    # Build adjacency list and in-degree count
    adj: Dict[str, List[str]] = {c.name: [] for c in components}
    in_degree: Dict[str, int] = {c.name: 0 for c in components}
    comp_map: Dict[str, Component] = {c.name: c for c in components}

    # For each component, add edges from dependencies to dependents
    for comp in components:
        local_deps = comp.dependencies.get('local', [])
        for dep_name in local_deps:
            if dep_name in comp_map:
                adj[dep_name].append(comp.name)
                in_degree[comp.name] += 1

    # Find all nodes with no incoming edges
    queue: List[str] = [name for name, degree in in_degree.items() if degree == 0]
    result: List[Component] = []

    while queue:
        # Sort for deterministic output
        queue.sort()
        node = queue.pop(0)
        result.append(comp_map[node])

        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Check for cycles
    if len(result) != len(components):
        # Find nodes not in result (part of cycle)
        remaining = set(comp_map.keys()) - {c.name for c in result}
        cycle_components = [comp_map[n].name for n in remaining]
        raise DependencyCycleError(
            f"Circular dependency detected involving: {', '.join(cycle_components)}"
        )

    return result
