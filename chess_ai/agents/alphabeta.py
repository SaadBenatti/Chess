"""Minimax with alpha-beta pruning.

Same max/min structure and evaluation as :mod:`minimax`, plus two additions:

* alpha-beta cutoffs: stop searching a node's remaining moves once it is
  proven the opponent would never allow this line;
* simple move ordering (previous best move, then captures) so cutoffs happen
  early.

It returns exactly the same scores as plain minimax at a given depth but
visits far fewer nodes, so it reaches deeper in the same time.
"""
from __future__ import annotations

import chess

from ..evaluation import is_draw_by_rule, mvv_lva
from .minimax import leaf_score_white, mated_score_white
from .search_base import INF, IterativeDeepeningAgent


class AlphaBetaAgent(IterativeDeepeningAgent):
    name = "Alpha-Beta"

    def ordered_moves(self, board: chess.Board, first: chess.Move | None = None) -> list[chess.Move]:
        moves = self.shuffled_moves(board)
        moves.sort(key=lambda m: mvv_lva(board, m), reverse=True)  # stable: ties stay shuffled
        if first is not None and first in moves:
            moves.remove(first)
            moves.insert(0, first)
        return moves

    def search_root(self, board, depth, prev_best):
        maximizing = board.turn == chess.WHITE
        alpha, beta = -INF, INF
        best = -INF if maximizing else INF
        best_moves: list[chess.Move] = []
        for move in self.ordered_moves(board, prev_best):
            board.push(move)
            score = self._alphabeta(board, depth - 1, 1, alpha, beta, not maximizing)
            board.pop()
            if (score > best) if maximizing else (score < best):
                best, best_moves = score, [move]
            elif score == best:
                best_moves.append(move)
            # Keep the window one point wider than the best score so moves that
            # tie with it get an exact score (for random tie-breaking) instead
            # of being cut off.
            if maximizing:
                alpha = best - 1
            else:
                beta = best + 1
        return self.rng.choice(best_moves), best

    def _alphabeta(self, board: chess.Board, depth: int, ply: int, alpha: int, beta: int, maximizing: bool) -> int:
        self.tick()
        if is_draw_by_rule(board):
            return 0
        if depth == 0:
            return leaf_score_white(board, ply)
        moves = self.ordered_moves(board)
        if not moves:
            return mated_score_white(board, ply) if board.is_check() else 0

        if maximizing:
            best = -INF
            for move in moves:
                board.push(move)
                best = max(best, self._alphabeta(board, depth - 1, ply + 1, alpha, beta, False))
                board.pop()
                alpha = max(alpha, best)
                if alpha >= beta:
                    break  # beta cutoff: Black will avoid this line
        else:
            best = INF
            for move in moves:
                board.push(move)
                best = min(best, self._alphabeta(board, depth - 1, ply + 1, alpha, beta, True))
                board.pop()
                beta = min(beta, best)
                if alpha >= beta:
                    break  # alpha cutoff: White will avoid this line
        return best
