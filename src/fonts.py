# =============================================================================
# fonts.py
# Lazy-initialised font cache.  Import get_font() anywhere after pygame.init().
# Never create Font objects at module level — they crash before pygame.init().
# =============================================================================

import pygame
from src.constants import FS_TITLE, FS_HEADING, FS_BODY, FS_LABEL, FS_SMALL, FS_MONO

_cache: dict = {}

# Preferred system font stacks
_SANS  = "segoe ui,calibri,arial,helvetica,freesans"
_SERIF = "georgia,times new roman,serif"
_MONO  = "consolas,courier new,lucida console,monospace"


def get_font(size: int = FS_BODY, bold: bool = False, italic: bool = False,
             family: str = "sans") -> pygame.font.Font:
    """Return a cached pygame Font for (size, bold, italic, family)."""
    key = (size, bold, italic, family)
    if key not in _cache:
        stack = {"sans": _SANS, "serif": _SERIF, "mono": _MONO}.get(family, _SANS)
        _cache[key] = pygame.font.SysFont(stack, size, bold=bold, italic=italic)
    return _cache[key]


# Convenience aliases
def font_title()   -> pygame.font.Font: return get_font(FS_TITLE,   bold=True)
def font_heading() -> pygame.font.Font: return get_font(FS_HEADING, bold=True)
def font_body()    -> pygame.font.Font: return get_font(FS_BODY)
def font_label()   -> pygame.font.Font: return get_font(FS_LABEL)
def font_small()   -> pygame.font.Font: return get_font(FS_SMALL)
def font_mono()    -> pygame.font.Font: return get_font(FS_MONO, family="mono")
