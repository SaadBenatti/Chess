"""Baseline agents: random moves and one-ply greedy."""
from __future__ import annotations

import random
import threading
import time

import chess

from ..evaluation import MATE, evaluate, is_draw_by_rule
from .base import Agent, SearchStats


class RandomAgent(Agent):
    """Plays a uniformly random legal move. Useful as a sanity baseline."""

    name = "Random"

    def __init__(self, seed: int | None = None, **_ignored) -> None:
        super().__init__()
        self.rng = random.Random(seed)

    def choose_move(self, board, stop_event=None):
        moves = list(board.legal_moves)
        if not moves:
            return None
        move = self.rng.choice(moves)
        self.last_stats = SearchStats(move=board.san(move), depth=0, nodes=0)
        return move


class GreedyAgent(Agent):
    """Looks one move ahead and plays whatever scores best right now.

    It grabs material and delivers mate-in-one, but ignores the reply, so it
    happily walks into recaptures.
    """

    name = "Greedy"

    def __init__(self, seed: int | None = None, **_ignored) -> None:
        super().__init__()
        self.rng = random.Random(seed)

    def choose_move(self, board: chess.Board, stop_event: threading.Event | None = None):
        board = board.copy()
        start = time.perf_counter()
        best, best_moves = None, []
        for move in board.legal_moves:
            board.push(move)
            if board.is_checkmate():
                score = MATE - 1  # mate in one ply
            elif board.is_stalemate() or is_draw_by_rule(board):
                score = 0
            else:
                score = -evaluate(board)  # evaluate() is for the opponent, now to move
            board.pop()
            if best is None or score > best:
                best, best_moves = score, [move]
            elif score == best:
                best_moves.append(move)
        if not best_moves:
            return None
        move = self.rng.choice(best_moves)
        self.last_stats = SearchStats(
            move=board.san(move),
            depth=1,
            nodes=board.legal_moves.count(),
            time=time.perf_counter() - start,
            score=best if board.turn == chess.WHITE else -best,
        )
        return move
