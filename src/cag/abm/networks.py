"""CAG-specific inputs for GABM's generic network utilities."""
from __future__ import annotations

__version__ = "0.9.1"
__author__ = ["Climate-Action-GABM contributors"]
__copyright__ = "Copyright (c) 2026 GABM contributors, University of Leeds"

from typing import Any, Dict, Iterable, Sequence

import networkx as nx

from gabm.abm.networks import (
    NETWORK_TYPES,
    build_network as _build_network,
    compute_diagnostics as _compute_diagnostics,
)


DEFAULT_HOMOPHILY_ATTRIBUTES = (
    "ukge2019_vote_id",
    "brexit_vote_id",
    "region_id",
)


def build_network(
    network_type: str,
    agents: Sequence[Any],
    params: Dict[str, Any] | None = None,
    seed: int = 42,
) -> nx.Graph:
    """Build a CAG peer network through GABM's generic graph API.

    Political-exposure grouping and the default survey attributes remain
    application-owned; graph algorithms and seeded edge generation live in
    ``gabm.abm.networks``.
    """
    params = dict(params or {})
    if network_type not in NETWORK_TYPES:
        raise ValueError(
            f"Unknown network_type {network_type!r}; "
            f"valid options: {NETWORK_TYPES}"
        )

    agents = list(agents)
    if not agents:
        raise ValueError("Cannot build a network with zero agents.")

    block_membership = None
    similarity_inputs = None
    node_ids = [agent.id for agent in agents]
    builder_params = params

    if network_type == "stochastic_block":
        block_0, block_1, swing = [], [], []
        for agent in agents:
            exposure = getattr(agent, "political_exposure", None)
            if exposure == "A-only":
                block_0.append(agent)
            elif exposure == "B-only":
                block_1.append(agent)
            else:
                swing.append(agent)

        for index, agent in enumerate(swing):
            (block_0 if index % 2 == 0 else block_1).append(agent)

        ordered_agents = block_0 + block_1
        node_ids = [agent.id for agent in ordered_agents]
        block_membership = (
            [0] * len(block_0) + [1] * len(block_1)
        )

    elif network_type == "homophily_weighted":
        attributes = list(
            params.get("attributes") or DEFAULT_HOMOPHILY_ATTRIBUTES
        )
        similarity_inputs = [
            [getattr(agent, attribute, None) for attribute in attributes]
            for agent in agents
        ]
        builder_params = {
            key: value for key, value in params.items() if key != "attributes"
        }

    return _build_network(
        network_type,
        node_ids,
        params=builder_params,
        seed=seed,
        block_membership=block_membership,
        block_order=(0, 1) if network_type == "stochastic_block" else None,
        similarity_inputs=similarity_inputs,
    )


def compute_diagnostics(
    graph: nx.Graph,
    agents: Iterable[Any] | None = None,
    timeout_s: float | None = 30.0,
) -> Dict[str, Any]:
    """Keep the CAG-facing diagnostics API while delegating graph metrics."""
    exposure_by_node = {}
    if agents is not None:
        for agent in agents:
            exposure = getattr(agent, "political_exposure", None)
            if exposure is not None and agent.id in graph:
                exposure_by_node[agent.id] = exposure
    return _compute_diagnostics(
        graph,
        node_attributes={"political_exposure": exposure_by_node},
        timeout_s=timeout_s,
    )
