"""Agent interface shared by every AI player."""
from __future__ import annotations

import threading
from dataclasses import dataclass

import chess


@dataclass
class SearchStats:
    """What an agent reports about its last move; shown in the GUI side panel."""

    move: str = ""
    depth: int = 0          # deepest fully completed search depth (plies)
    nodes: int = 0          # positions visited (MCTS: iterations)
    time: float = 0.0       # seconds spent
    score: int | None = None  # centipawns from White's point of view
    note: str = ""          # agent-specific extra info (e.g. MCTS win rate)

    @property
    def nps(self) -> int:
        return int(self.nodes / self.time) if self.time > 0 else 0


class Agent:
    """An AI player. Subclasses implement :meth:`choose_move`.

    ``choose_move`` must not modify the board it is given (callers pass a copy
    anyway) and should return promptly once ``stop_event`` is set.
    """

    name = "Agent"

    def __init__(self) -> None:
        self.last_stats = SearchStats()

    def choose_move(self, board: chess.Board, stop_event: threading.Event | None = None) -> chess.Move | None:
        raise NotImplementedError

    def close(self) -> None:
        """Release external resources (engine processes)."""
