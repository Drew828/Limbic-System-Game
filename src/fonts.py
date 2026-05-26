# =============================================================================
# fonts.py
# Lazy-initialised font cache.  Import get_font() anywhere after pygame.init().
# Never create Font objects at module level — they crash before pygame.init().
#
# Web / Pygbag note:
#   In WebAssembly (Pygbag) system fonts are unavailable.  We detect the
#   platform and fall back to pygame's bundled default font so all text still
#   renders correctly.  Bold/italic hints are honoured on desktop but silently
#   ignored on the web — the game is fully playable either way.
# =============================================================================

import sys
import pygame
from src.constants import FS_TITLE, FS_HEADING, FS_BODY, FS_LABEL, FS_SMALL, FS_MONO

_cache: dict = {}

# True when running inside Pygbag's WebAssembly environment
_IS_WEB = sys.platform == "emscripten"

# Preferred system font stacks (desktop only)
_SANS  = "segoe ui,calibri,arial,helvetica,freesans"
_SERIF = "georgia,times new roman,serif"
_MONO  = "consolas,courier new,lucida console,monospace"


def get_font(size: int = FS_BODY, bold: bool = False, italic: bool = False,
             family: str = "sans") -> pygame.font.Font:
    """Return a cached pygame Font for (size, bold, italic, family)."""
    key = (size, bold, italic, family)
    if key not in _cache:
        if _IS_WEB:
            # WebAssembly: system fonts unavailable — use pygame's bundled font.
            # Bold/italic are ignored here; the game still looks fine in a browser.
            _cache[key] = pygame.font.Font(pygame.font.get_default_font(), size)
        else:
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
