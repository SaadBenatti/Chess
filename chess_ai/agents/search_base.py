"""Iterative-deepening driver shared by the minimax family.

Every minimax-style agent gets the same time budget per move and searches
depth 1, 2, 3, ... until time runs out, keeping the result of the deepest
*completed* depth. Because the budget is equal, the depth each agent reaches
(and the node counts in the side panel) shows how efficient its search is.
"""
from __future__ import annotations

import random
import threading
import time

import chess

from ..evaluation import MATE_THRESHOLD
from .base import Agent, SearchStats, san_line

INF = 10**9


class SearchTimeout(Exception):
    """Raised inside the search when the time budget is spent."""


class IterativeDeepeningAgent(Agent):
    """Base class: subclasses implement :meth:`search_root`."""

    def __init__(self, time_limit: float = 2.0, max_depth: int = 64, seed: int | None = None) -> None:
        super().__init__()
        self.time_limit = time_limit
        self.max_depth = max_depth
        self.rng = random.Random(seed)
        self.nodes = 0
        self._deadline = 0.0
        self._stop: threading.Event | None = None
        self._can_abort = False
        self.last_pv: list[chess.Move] = []  # subclasses may fill this in search_root

    # -- hooks -------------------------------------------------------------
    def search_root(self, board: chess.Board, depth: int, prev_best: chess.Move | None) -> tuple[chess.Move, int]:
        """Search to ``depth`` and return (best move, score from White's view)."""
        raise NotImplementedError

    def new_search(self) -> None:
        """Called once per move before iterative deepening starts."""

    # -- helpers for subclasses -------------------------------------------
    def tick(self) -> None:
        """Count a node and abort if time is up (checked every 512 nodes)."""
        self.nodes += 1
        if self._can_abort and (self.nodes & 511) == 0:
            if time.perf_counter() >= self._deadline or (self._stop is not None and self._stop.is_set()):
                raise SearchTimeout

    def shuffled_moves(self, board: chess.Board) -> list[chess.Move]:
        """Legal moves in random order, so equal moves are not always picked the same way."""
        moves = list(board.legal_moves)
        self.rng.shuffle(moves)
        return moves

    # -- driver ------------------------------------------------------------
    def choose_move(self, board: chess.Board, stop_event: threading.Event | None = None) -> chess.Move | None:
        board = board.copy()  # keep the move stack so repetitions are detected
        if board.is_game_over():
            return None
        start = time.perf_counter()
        self._deadline = start + self.time_limit
        self._stop = stop_event
        self.nodes = 0
        self.new_search()

        best_move: chess.Move | None = None
        best_score: int | None = None
        best_pv: list[chess.Move] = []
        completed = 0
        for depth in range(1, self.max_depth + 1):
            # Depth 1 always finishes so there is always a sensible move.
            self._can_abort = depth > 1
            try:
                # Fresh copy per depth: a timeout leaves pushed moves behind.
                self.last_pv = []
                move, score = self.search_root(board.copy(), depth, best_move)
            except SearchTimeout:
                break
            best_move, best_score, completed = move, score, depth
            best_pv = self.last_pv or [move]
            if abs(score) >= MATE_THRESHOLD:
                break  # forced mate found; deeper search will not change it
            if time.perf_counter() >= self._deadline or (stop_event is not None and stop_event.is_set()):
                break

        self.last_stats = SearchStats(
            move=board.san(best_move) if best_move else "",
            depth=completed,
            nodes=self.nodes,
            time=time.perf_counter() - start,
            score=best_score,
            pv=san_line(board, best_pv),
        )
        return best_move
