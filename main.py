"""
main.py — entry point for Limbic Journey.

─── STANDALONE (Windows / macOS / Linux) ────────────────────────────────────
To run locally:
    python main.py

The original synchronous entry point is preserved below (commented out).
Uncomment that block and comment out the async block if you ever need to
revert to running without asyncio (e.g. for profiling or debugging).

─── WEB BUILD (Pygbag / Chromebook / any browser) ────────────────────────────
To build:
    pip install pygbag
    python -m pygbag --build main.py
Output lands in  build/web/  → deploy that folder to GitHub Pages.
The Chromebook (or any device) then just opens the GitHub Pages URL in Chrome.
No Python, no install needed on the viewing device.

The async entry point below works for BOTH standalone and web — asyncio.sleep(0)
yields to the browser each frame on the web, and is essentially free on desktop.
────────────────────────────────────────────────────────────────────────────────
"""

# ── Original standalone entry point (kept for reference) ─────────────────────
# from src.game import Game
#
# def main() -> None:
#     game = Game()
#     game.run()          # synchronous, blocks until window closes
#
# if __name__ == "__main__":
#     main()
# ─────────────────────────────────────────────────────────────────────────────

# ── Async entry point — works for both desktop and Pygbag web build ───────────
# Pygbag requires:
#   1. main() must be declared async
#   2. asyncio.run(main()) must be called at module level (not inside __main__)
#   3. game loop must call await asyncio.sleep(0) each frame (see game.py)
import asyncio
from src.game import Game


async def main() -> None:
    game = Game()
    await game.run_async()


asyncio.run(main())
# ─────────────────────────────────────────────────────────────────────────────
