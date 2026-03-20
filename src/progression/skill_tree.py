"""SkillTree -- manages skill tree nodes, prerequisites, unlocking, and stat bonuses.

The skill tree supports multiple branches (e.g. combat, mobility) with
prerequisite chains.  Nodes cost skill points (earned one per level-up) to
unlock and provide cumulative stat bonuses that are applied at round start.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from src.progression.xp_system import XPSystem


class SkillTree:
    """Manages the player's skill tree state."""

    def __init__(self, event_bus: Any = None) -> None:
        self._nodes: Dict[str, dict] = {}
        self._unlocked: Set[str] = set()
        self._branches: List[str] = []
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, path: str) -> None:
        """Load skill tree definition from a JSON file.

        Raises ValueError if any node is missing a required ``"id"`` or
        ``"branch"`` field so corrupt data is caught early.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._branches = data.get("branches", [])
        nodes: Dict[str, dict] = {}
        for node in data.get("nodes", []):
            if "id" not in node:
                raise ValueError(f"Skill tree node missing 'id' field: {node!r}")
            if "branch" not in node:
                raise ValueError(
                    f"Skill tree node '{node['id']}' missing 'branch' field"
                )
            nodes[node["id"]] = node
        self._nodes = nodes

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

    def can_unlock(self, node_id: str,
                   xp_system: Optional["XPSystem"] = None,
                   player_level: Optional[int] = None,
                   currency: Any = None) -> bool:
        """Check whether *node_id* can be unlocked.

        Requirements:
        1. The node must exist in the tree.
        2. The node must not already be unlocked.
        3. All prerequisite nodes must be unlocked.
        4. If the node has a ``required_level``, the player must meet it.
           *player_level* takes precedence over ``xp_system.level``; when
           both are ``None``, the effective level is ``0`` so level-gated
           nodes are blocked unless a level is supplied.
        5. If *xp_system* is provided, the player must have enough skill
           points (``xp_system.skill_points >= node.cost_sp``).
        6. If *currency* is provided and the node has a ``cost_money`` key,
           the player's balance must cover that cost.
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
        if player_level is not None:
            effective_level = player_level
        elif xp_system is not None:
            effective_level = xp_system.level
        else:
            effective_level = 0
        if effective_level < required_level:
            return False
        # Skill point gating — only applied when an xp_system is provided
        if xp_system is not None:
            cost_sp = node.get("cost_sp", 1)
            if xp_system.skill_points < cost_sp:
                return False
        # Currency gating — only applied when a currency object is provided
        if currency is not None:
            cost_money = node.get("cost_money", 0)
            if cost_money > 0 and currency.balance < cost_money:
                return False
        return True

    def get_cost_sp(self, node_id: str) -> int:
        """Return the skill-point cost for unlocking *node_id*, or 0 if unknown."""
        node = self._nodes.get(node_id)
        if node is None:
            return 0
        return node.get("cost_sp", 1)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def unlock(self, node_id: str,
               xp_system: Optional["XPSystem"] = None,
               player_level: Optional[int] = None,
               currency: Any = None,
               event_bus: Any = None) -> bool:
        """Attempt to unlock *node_id*.

        If *xp_system* is provided the skill-point cost is deducted
        automatically.  If *currency* is provided and the node has a
        ``cost_money`` key, that amount is deducted from the balance.
        *player_level* is forwarded to :meth:`can_unlock` for level-gating
        without a full XPSystem.  *event_bus* overrides the instance-level
        event bus for event emission (useful in tests).

        Returns True on success, False if prerequisites are not met, the node
        is already unlocked, or the player cannot afford the cost.
        """
        if not self.can_unlock(node_id, xp_system, player_level, currency):
            return False
        node = self._nodes[node_id]
        cost_sp = node.get("cost_sp", 1)
        if xp_system is not None and cost_sp > 0:
            if not xp_system.spend_skill_point(cost_sp):
                return False
        # Deduct currency cost
        cost_money = node.get("cost_money", 0)
        if currency is not None and cost_money > 0:
            if not currency.spend(cost_money):
                return False
        self._unlocked.add(node_id)
        # Emit events using the provided bus (or fall back to instance bus)
        active_bus = event_bus if event_bus is not None else self._event_bus
        if active_bus is not None:
            active_bus.emit("skill_unlocked", node_id=node_id)
            if currency is not None and cost_money > 0:
                active_bus.emit(
                    "currency_spent",
                    amount=cost_money,
                    new_balance=currency.balance,
                )
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

    def get_node_display(self, node_id: str,
                         xp_system: Optional["XPSystem"] = None) -> Optional[dict]:
        """Return a display-ready dict for a single node."""
        node = self._nodes.get(node_id)
        if node is None:
            return None
        return {
            "id": node["id"],
            "name": node.get("name", node["id"]),
            "branch": node.get("branch", ""),
            "description": node.get("description", ""),
            "cost_sp": node.get("cost_sp", 1),
            "unlocked": node_id in self._unlocked,
            "available": self.can_unlock(node_id, xp_system),
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
