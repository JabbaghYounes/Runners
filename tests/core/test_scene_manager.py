"""Unit tests for src.core.scene_manager.SceneManager.

Uses a lightweight FakeScene stub rather than real Pygame scenes so that
lifecycle tracking is precise and the tests remain fast.
"""
import pytest
import pygame

from src.core.scene_manager import SceneManager
from src.scenes.base_scene import BaseScene


# ---------------------------------------------------------------------------
# FakeScene — minimal BaseScene for tracking lifecycle calls
# ---------------------------------------------------------------------------

class FakeScene(BaseScene):
    def __init__(self, name: str = ""):
        self.name = name
        self.entered: int = 0
        self.exited: int = 0
        self.last_dt: float | None = None
        self.rendered: bool = False
        self.events_received: list = []

    def handle_events(self, events):
        self.events_received.extend(events)

    def update(self, dt):
        self.last_dt = dt

    def render(self, screen):
        self.rendered = True

    def on_enter(self):
        self.entered += 1

    def on_exit(self):
        self.exited += 1


# ---------------------------------------------------------------------------
# is_empty
# ---------------------------------------------------------------------------

def test_is_empty_on_freshly_created_manager():
    sm = SceneManager()
    assert sm.is_empty is True


def test_is_not_empty_after_push():
    sm = SceneManager()
    sm.push(FakeScene())
    assert sm.is_empty is False


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------

def test_push_calls_on_enter():
    sm = SceneManager()
    s = FakeScene()
    sm.push(s)
    assert s.entered == 1


def test_push_does_not_call_on_exit():
    sm = SceneManager()
    s = FakeScene()
    sm.push(s)
    assert s.exited == 0


def test_push_multiple_scenes_top_receives_events():
    sm = SceneManager()
    bottom = FakeScene("bottom")
    top = FakeScene("top")
    sm.push(bottom)
    sm.push(top)
    ev = pygame.event.Event(pygame.USEREVENT)
    sm.handle_events([ev])
    assert len(top.events_received) == 1
    assert len(bottom.events_received) == 0


# ---------------------------------------------------------------------------
# pop
# ---------------------------------------------------------------------------

def test_pop_calls_on_exit_on_top_scene():
    sm = SceneManager()
    s = FakeScene()
    sm.push(s)
    sm.pop()
    assert s.exited == 1


def test_pop_calls_on_enter_on_newly_revealed_scene():
    sm = SceneManager()
    bottom = FakeScene("bottom")
    top = FakeScene("top")
    sm.push(bottom)
    sm.push(top)
    assert bottom.entered == 1         # from initial push
    sm.pop()
    assert bottom.entered == 2         # revealed by pop


def test_pop_leaves_stack_empty_from_single_scene():
    sm = SceneManager()
    sm.push(FakeScene())
    sm.pop()
    assert sm.is_empty


def test_pop_on_empty_stack_does_nothing():
    sm = SceneManager()
    sm.pop()                           # Must not raise
    assert sm.is_empty


def test_pop_removes_top_scene_updates_go_to_new_top():
    sm = SceneManager()
    bottom = FakeScene("bottom")
    top = FakeScene("top")
    sm.push(bottom)
    sm.push(top)
    sm.pop()
    sm.update(0.05)
    assert bottom.last_dt == pytest.approx(0.05)
    assert top.last_dt is None


# ---------------------------------------------------------------------------
# replace
# ---------------------------------------------------------------------------

def test_replace_swaps_top_scene():
    sm = SceneManager()
    old = FakeScene("old")
    new = FakeScene("new")
    sm.push(old)
    sm.replace(new)
    sm.update(0.1)
    assert new.last_dt == pytest.approx(0.1)
    assert old.last_dt is None


def test_replace_calls_on_exit_on_old_scene():
    sm = SceneManager()
    old = FakeScene()
    sm.push(old)
    sm.replace(FakeScene())
    assert old.exited == 1


def test_replace_calls_on_enter_on_new_scene():
    sm = SceneManager()
    sm.push(FakeScene())
    new = FakeScene()
    sm.replace(new)
    assert new.entered == 1


def test_replace_on_empty_stack_still_pushes_scene():
    """replace() on an empty stack should work like push()."""
    sm = SceneManager()
    s = FakeScene()
    sm.replace(s)
    assert not sm.is_empty
    assert s.entered == 1


def test_replace_does_not_call_on_enter_on_scene_below():
    """The scene below the replaced one must NOT receive an on_enter call
    (it was already running — replace doesn't pop-then-push)."""
    sm = SceneManager()
    base = FakeScene("base")
    mid = FakeScene("mid")
    sm.push(base)
    sm.push(mid)
    sm.replace(FakeScene("top"))
    # base was not revealed; only 1 on_enter from its initial push
    assert base.entered == 1


# ---------------------------------------------------------------------------
# replace_all
# ---------------------------------------------------------------------------

def test_replace_all_leaves_only_new_scene():
    sm = SceneManager()
    for _ in range(3):
        sm.push(FakeScene())
    sole = FakeScene("sole")
    sm.replace_all(sole)
    sm.update(0.02)
    assert sole.last_dt == pytest.approx(0.02)


def test_replace_all_calls_on_exit_on_every_evicted_scene():
    sm = SceneManager()
    scenes = [FakeScene(str(i)) for i in range(4)]
    for s in scenes:
        sm.push(s)
    sm.replace_all(FakeScene("new"))
    for s in scenes:
        assert s.exited == 1, f"Scene {s.name} was not exited"


def test_replace_all_calls_on_enter_on_new_scene():
    sm = SceneManager()
    sm.push(FakeScene())
    incoming = FakeScene()
    sm.replace_all(incoming)
    assert incoming.entered == 1


# ---------------------------------------------------------------------------
# handle_events
# ---------------------------------------------------------------------------

def test_handle_events_routes_to_top_only():
    sm = SceneManager()
    a = FakeScene("a")
    b = FakeScene("b")
    sm.push(a)
    sm.push(b)
    ev = pygame.event.Event(pygame.USEREVENT)
    sm.handle_events([ev])
    assert len(b.events_received) == 1
    assert len(a.events_received) == 0


def test_handle_events_on_empty_stack_does_not_raise():
    sm = SceneManager()
    sm.handle_events([pygame.event.Event(pygame.USEREVENT)])


def test_handle_events_passes_all_events_in_batch():
    sm = SceneManager()
    s = FakeScene()
    sm.push(s)
    events = [pygame.event.Event(pygame.USEREVENT) for _ in range(5)]
    sm.handle_events(events)
    assert len(s.events_received) == 5


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def test_update_goes_to_top_only():
    sm = SceneManager()
    bottom = FakeScene()
    top = FakeScene()
    sm.push(bottom)
    sm.push(top)
    sm.update(0.016)
    assert top.last_dt == pytest.approx(0.016)
    assert bottom.last_dt is None


def test_update_on_empty_stack_does_not_raise():
    sm = SceneManager()
    sm.update(0.016)


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def test_render_calls_all_scenes_bottom_to_top(screen):
    sm = SceneManager()
    render_order: list = []

    class OrderScene(BaseScene):
        def __init__(self, tag):
            self.tag = tag
        def handle_events(self, events): pass
        def update(self, dt): pass
        def render(self, s):
            render_order.append(self.tag)

    sm.push(OrderScene("bottom"))
    sm.push(OrderScene("middle"))
    sm.push(OrderScene("top"))
    sm.render(screen)
    assert render_order == ["bottom", "middle", "top"]


def test_render_on_empty_stack_does_not_raise(screen):
    sm = SceneManager()
    sm.render(screen)


def test_render_calls_all_scenes_not_just_top(screen):
    sm = SceneManager()
    bottom = FakeScene()
    top = FakeScene()
    sm.push(bottom)
    sm.push(top)
    sm.render(screen)
    assert bottom.rendered is True
    assert top.rendered is True
