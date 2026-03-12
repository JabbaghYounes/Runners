"""SkillTree -- manages skill tree nodes, prerequisites, unlocking, and stat bonuses.

The skill tree supports multiple branches (e.g. combat, mobility) with
prerequisite chains.  Nodes cost in-game currency to unlock and provide
cumulative stat bonuses that are applied at round start.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional

from src.progression.currency import Currency


class SkillTree:
    """Manages the player's skill tree state."""

    def __init__(self) -> None:
        self._nodes: Dict[str, dict] = {}
        self._unlocked: Set[str] = set()
        self._branches: List[str] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, path: str) -> None:
        """Load skill tree definition from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._branches = data.get("branches", [])
        for node in data.get("nodes", []):
            self._nodes[node["id"]] = node

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def node_ids(self) -> List[str]:
        """Return all node ids in definition order."""
        return list(self._nodes.keys())

    @property
    def branches(self) -> List[str]:
        """Return branch names defined in the skill tree data."""
        return list(self._branches)

    @property
    def unlocked_ids(self) -> Set[str]:
        """Return set of currently unlocked node ids."""
        return set(self._unlocked)

    def get_node(self, node_id: str) -> Optional[dict]:
        """Return the full node dict for *node_id*, or None."""
        return self._nodes.get(node_id)

    def get_branch_nodes(self, branch: str) -> List[dict]:
        """Return all nodes belonging to *branch*, in definition order."""
        return [n for n in self._nodes.values() if n.get("branch") == branch]

    def is_unlocked(self, node_id: str) -> bool:
        """Return True if the node has been unlocked."""
        return node_id in self._unlocked

    def can_unlock(self, node_id: str, currency: Optional[Currency] = None,
                   player_level: Optional[int] = None) -> bool:
        """Check whether *node_id* can be unlocked.

        Requirements:
        1. The node must exist in the tree.
        2. The node must not already be unlocked.
        3. All prerequisite nodes must be unlocked.
        4. If the node has a ``required_level``, the player must meet it.
           When *player_level* is ``None``, it defaults to ``0`` so that
           level-gated nodes are blocked unless a level is explicitly provided.
        5. If *currency* is provided, the player must be able to afford the cost.
        """
        node = self._nodes.get(node_id)
        if node is None:
            return False
        if node_id in self._unlocked:
            return False
        if not all(req in self._unlocked for req in node.get("requires", [])):
            return False
        # Level gating
        required_level = node.get("required_level", 0)
        effective_level = player_level if player_level is not None else 0
        if effective_level < required_level:
            return False
        if currency is not None:
            cost = node.get("cost_money", 0)
            if currency.balance < cost:
                return False
        return True

    def get_cost(self, node_id: str) -> int:
        """Return the money cost for unlocking *node_id*, or 0 if unknown."""
        node = self._nodes.get(node_id)
        if node is None:
            return 0
        return node.get("cost_money", 0)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def unlock(self, node_id: str, currency: Optional[Currency] = None,
               player_level: Optional[int] = None) -> bool:
        """Attempt to unlock *node_id*.

        If *currency* is provided the cost is deducted automatically.
        Returns True on success, False if prerequisites are not met, the
        node is already unlocked, or the player cannot afford the cost.
        """
        if not self.can_unlock(node_id, currency, player_level=player_level):
            return False
        node = self._nodes[node_id]
        cost = node.get("cost_money", 0)
        if currency is not None and cost > 0:
            if not currency.spend(cost):
                return False
        self._unlocked.add(node_id)
        return True

    # ------------------------------------------------------------------
    # Stat bonuses
    # ------------------------------------------------------------------

    def get_stat_bonuses(self) -> Dict[str, float]:
        """Aggregate stat bonuses from all unlocked nodes.

        Bonuses of the same key are summed.
        """
        bonuses: Dict[str, float] = {}
        for node_id in self._unlocked:
            node = self._nodes.get(node_id, {})
            for k, v in node.get("stat_bonus", {}).items():
                bonuses[k] = bonuses.get(k, 0.0) + v
        return bonuses

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def get_node_display(self, node_id: str) -> Optional[dict]:
        """Return a display-ready dict for a single node."""
        node = self._nodes.get(node_id)
        if node is None:
            return None
        return {
            "id": node["id"],
            "name": node.get("name", node["id"]),
            "branch": node.get("branch", ""),
            "description": node.get("description", ""),
            "cost": node.get("cost_money", 0),
            "unlocked": node_id in self._unlocked,
            "available": self.can_unlock(node_id),
            "requires": node.get("requires", []),
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def load_state(self, data: dict) -> None:
        """Restore unlocked nodes from save data.

        Accepts both ``{'unlocked': [...]}`` and
        ``{'unlocked_nodes': [...]}`` for compatibility with SaveManager.
        """
        unlocked = data.get("unlocked", data.get("unlocked_nodes", []))
        self._unlocked = set(unlocked)

    def to_save_dict(self) -> dict:
        """Return a dict suitable for JSON serialisation."""
        return {"unlocked": sorted(self._unlocked)}
