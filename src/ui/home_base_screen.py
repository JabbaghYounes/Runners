"""HomeBaseScreen — facility card grid for the Home Base hub."""
from __future__ import annotations
from typing import Optional

import pygame

from src.ui.widgets import (
    ACCENT_AMBER, ACCENT_CYAN, BG_DEEP, TEXT_PRIMARY, TEXT_SECONDARY,
    ConfirmDialog, FacilityCard,
)


class HomeBaseScreen:
    """Renders all facility upgrade cards and drives the upgrade UX.

    Args:
        home_base: The live HomeBase progression model (not a copy).
        currency: The live Currency object.
        screen_rect: The pygame.Rect area this screen occupies.
    """

    def __init__(self, home_base, currency, screen_rect) -> None:
        self._home_base = home_base
        self._currency = currency
        self._screen_rect = screen_rect
        self._cards: list[FacilityCard] = []
        self._confirm_dialog: Optional[ConfirmDialog] = None
        self._build_cards()

    # ------------------------------------------------------------------
    # Card management
    # ------------------------------------------------------------------

    def _build_cards(self) -> None:
        """Create one FacilityCard per facility, laid out horizontally."""
        ids = self._home_base.facility_ids
        card_w, card_h = 180, 220
        gap = 24
        total_w = len(ids) * card_w + (len(ids) - 1) * gap
        start_x = self._screen_rect.centerx - total_w // 2
        card_y = self._screen_rect.y + 30

        self._cards = []
        for i, fid in enumerate(ids):
            display = self._home_base.get_facility_display(fid)
            cost = display["cost"]
            can_afford = (cost is not None and self._currency.balance >= cost)
            card_rect = pygame.Rect(start_x + i * (card_w + gap), card_y, card_w, card_h)
            card = FacilityCard(
                facility_id=fid,
                name=display["name"],
                level=display["level"],
                max_level=display["max_level"],
                upgrade_cost=cost,
                bonus_description=display["bonus_description"],
                can_afford=can_afford,
                on_upgrade=self._on_upgrade_requested,
                rect=card_rect,
            )
            self._cards.append(card)

    def update_cards(self) -> None:
        """Refresh all cards from live home_base state.

        Call this after any upgrade to keep the UI in sync.
        """
        for card in self._cards:
            display = self._home_base.get_facility_display(card.facility_id)
            cost = display["cost"]
            can_afford = (cost is not None and self._currency.balance >= cost)
            card.update(
                level=display["level"],
                upgrade_cost=cost,
                bonus_description=display["bonus_description"],
                can_afford=can_afford,
            )

    # ------------------------------------------------------------------
    # Upgrade flow
    # ------------------------------------------------------------------

    def _on_upgrade_requested(self, facility_id: str) -> None:
        """Show confirm dialog before executing the upgrade."""
        display = self._home_base.get_facility_display(facility_id)
        cost = display["cost"]
        if cost is None:
            return
        next_level = display["level"] + 1
        title = f"UPGRADE {display['name']}"
        body = f"Upgrade to Level {next_level} for ${cost:,}?"

        def on_confirm():
            self._home_base.upgrade(facility_id, self._currency)
            self.update_cards()
            self._confirm_dialog = None

        def on_cancel():
            self._confirm_dialog = None

        self._confirm_dialog = ConfirmDialog(
            title=title,
            body=body,
            confirm_label="UPGRADE",
            cancel_label="CANCEL",
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )

    # ------------------------------------------------------------------
    # Event / update / render
    # ------------------------------------------------------------------

    def handle_events(self, events: list) -> None:
        """Dispatch events. ConfirmDialog blocks card interaction when open."""
        for event in events:
            if self._confirm_dialog is not None:
                # Modal is open — only feed events to the dialog
                self._confirm_dialog.handle_event(event)
            else:
                for card in self._cards:
                    card.handle_event(event)

    def update(self, dt: float) -> None:
        pass

    def render(self, surface) -> None:
        """Render facility cards, then any active confirm dialog on top."""
        for card in self._cards:
            card.render(surface)
        if self._confirm_dialog is not None:
            self._confirm_dialog.render(surface)
