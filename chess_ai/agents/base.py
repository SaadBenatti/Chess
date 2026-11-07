"""Agent interface shared by every AI player."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

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
    pv: list[str] = field(default_factory=list)  # expected line in SAN, starting with `move`

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


def san_line(board: chess.Board, moves: list[chess.Move]) -> list[str]:
    """Convert a list of moves played from ``board`` into SAN strings."""
    board = board.copy(stack=False)
    line = []
    for move in moves:
        if move not in board.legal_moves:
            break
        line.append(board.san(move))
        board.push(move)
    return line
