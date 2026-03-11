"""Surface utility helpers."""
import pygame


def blur_surface(surface: pygame.Surface, radius: int) -> pygame.Surface:
    """Return a blurred copy of *surface* using a cheap box-blur approximation.

    The original surface is not modified.  The returned surface has the same
    dimensions as the input.
    """
    w, h = surface.get_size()
    scale = max(1, radius)
    small_w = max(1, w // scale)
    small_h = max(1, h // scale)
    small = pygame.transform.smoothscale(surface, (small_w, small_h))
    return pygame.transform.smoothscale(small, (w, h))
