"""Plain minimax: the textbook algorithm with no pruning.

White is the maximizing player and Black the minimizing player; scores are
always from White's point of view. Every legal move at every node is searched,
so the tree grows by roughly 35x per ply - this is the baseline the other
minimax variants are measured against.
"""
from __future__ import annotations

import chess

from ..evaluation import MATE, evaluate_white, is_draw_by_rule
from .search_base import INF, IterativeDeepeningAgent


def mated_score_white(board: chess.Board, ply: int) -> int:
    """Score (White's view) when the side to move is checkmated at ``ply``.

    Mates found sooner (smaller ply) score higher, so the engine prefers the
    fastest mate and the slowest loss.
    """
    return -(MATE - ply) if board.turn == chess.WHITE else MATE - ply


def leaf_score_white(board: chess.Board, ply: int) -> int:
    """Score a depth-0 node, detecting checkmate and stalemate."""
    if not any(board.legal_moves):
        return mated_score_white(board, ply) if board.is_check() else 0
    return evaluate_white(board)


class MinimaxAgent(IterativeDeepeningAgent):
    name = "Minimax"

    def search_root(self, board, depth, prev_best):
        maximizing = board.turn == chess.WHITE
        best = -INF if maximizing else INF
        best_moves: list[chess.Move] = []
        for move in self.shuffled_moves(board):
            board.push(move)
            score = self._minimax(board, depth - 1, 1, not maximizing)
            board.pop()
            if (score > best) if maximizing else (score < best):
                best, best_moves = score, [move]
            elif score == best:
                best_moves.append(move)
        return self.rng.choice(best_moves), best

    def _minimax(self, board: chess.Board, depth: int, ply: int, maximizing: bool) -> int:
        self.tick()
        if is_draw_by_rule(board):
            return 0
        if depth == 0:
            return leaf_score_white(board, ply)
        moves = list(board.legal_moves)
        if not moves:
            return mated_score_white(board, ply) if board.is_check() else 0

        if maximizing:
            best = -INF
            for move in moves:
                board.push(move)
                best = max(best, self._minimax(board, depth - 1, ply + 1, False))
                board.pop()
        else:
            best = INF
            for move in moves:
                board.push(move)
                best = min(best, self._minimax(board, depth - 1, ply + 1, True))
                board.pop()
        return best
