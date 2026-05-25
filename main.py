"""
main.py — entry point for Limbic Journey.

Run with:
    python main.py
or:
    python -m main
"""
from src.game import Game


def main() -> None:
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
