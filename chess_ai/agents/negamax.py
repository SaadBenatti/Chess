"""Negamax with alpha-beta and the standard engine enhancements.

Negamax is minimax written once instead of twice: a position's value for the
side to move is the negation of its best child's value for the opponent
(``max(a, b) == -min(-a, -b)``). On top of alpha-beta this agent adds:

* quiescence search: at depth 0, keep searching captures until the position is
  quiet, so it does not stop counting in the middle of an exchange (the
  "horizon effect");
* a transposition table keyed by Zobrist hash, which remembers results for
  positions reached through different move orders;
* move ordering: transposition-table move, then captures by MVV-LVA, then
  killer moves (quiet moves that caused a cutoff at the same ply);
* check extension: positions in check are searched one ply deeper.
"""
from __future__ import annotations

import chess
import chess.polyglot

from ..evaluation import MATE, MATE_THRESHOLD, evaluate, is_draw_by_rule, mvv_lva
from .search_base import INF, IterativeDeepeningAgent

EXACT, LOWER, UPPER = 0, 1, 2
TT_MAX_ENTRIES = 1_000_000
MAX_QUIESCENCE_PLY = 64


def _to_tt(score: int, ply: int) -> int:
    """Store mate scores relative to the node, not the root."""
    if score >= MATE_THRESHOLD:
        return score + ply
    if score <= -MATE_THRESHOLD:
        return score - ply
    return score


def _from_tt(score: int, ply: int) -> int:
    if score >= MATE_THRESHOLD:
        return score - ply
    if score <= -MATE_THRESHOLD:
        return score + ply
    return score


class NegamaxAgent(IterativeDeepeningAgent):
    name = "Negamax"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tt: dict[int, tuple[int, int, int, chess.Move | None]] = {}
        self.killers: list[list[chess.Move | None]] = []

    def new_search(self) -> None:
        if len(self.tt) > TT_MAX_ENTRIES:
            self.tt.clear()
        self.killers = [[None, None] for _ in range(128)]

    # -- move ordering -----------------------------------------------------
    def _ordered(self, board: chess.Board, tt_move: chess.Move | None, ply: int) -> list[chess.Move]:
        killers = self.killers[ply] if ply < len(self.killers) else (None, None)

        def key(move: chess.Move) -> int:
            if move == tt_move:
                return 1_000_000
            score = mvv_lva(board, move)
            if score:
                return score
            if move == killers[0]:
                return 9_000
            if move == killers[1]:
                return 8_000
            return 0

        moves = self.shuffled_moves(board)
        moves.sort(key=key, reverse=True)
        return moves

    def _store_killer(self, move: chess.Move, ply: int) -> None:
        if ply < len(self.killers) and self.killers[ply][0] != move:
            self.killers[ply][1] = self.killers[ply][0]
            self.killers[ply][0] = move

    # -- search ------------------------------------------------------------
    def search_root(self, board, depth, prev_best):
        alpha, beta = -INF, INF
        best = -INF
        best_moves: list[chess.Move] = []
        for move in self._ordered(board, prev_best, 0):
            board.push(move)
            score = -self._negamax(board, depth - 1, -beta, -alpha, 1)
            board.pop()
            if score > best:
                best, best_moves = score, [move]
            elif score == best:
                best_moves.append(move)
            alpha = best - 1  # keep ties exact for random tie-breaking
        white_score = best if board.turn == chess.WHITE else -best
        return self.rng.choice(best_moves), white_score

    def _negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.tick()
        if is_draw_by_rule(board):
            return 0

        in_check = board.is_check()
        if in_check:
            depth += 1  # check extension

        key = chess.polyglot.zobrist_hash(board)
        entry = self.tt.get(key)
        tt_move = None
        if entry is not None:
            e_depth, e_score, e_flag, tt_move = entry
            if e_depth >= depth:
                e_score = _from_tt(e_score, ply)
                if e_flag == EXACT:
                    return e_score
                if e_flag == LOWER and e_score >= beta:
                    return e_score
                if e_flag == UPPER and e_score <= alpha:
                    return e_score

        if depth <= 0:
            return self._quiescence(board, alpha, beta, ply)

        moves = self._ordered(board, tt_move, ply)
        if not moves:
            return -(MATE - ply) if in_check else 0

        alpha_orig = alpha
        best, best_move = -INF, None
        for move in moves:
            board.push(move)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score > best:
                best, best_move = score, move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                if not board.is_capture(move):
                    self._store_killer(move, ply)
                break

        flag = UPPER if best <= alpha_orig else LOWER if best >= beta else EXACT
        self.tt[key] = (depth, _to_tt(best, ply), flag, best_move)
        return best

    def _quiescence(self, board: chess.Board, alpha: int, beta: int, ply: int) -> int:
        self.tick()
        if board.is_check():
            # Must answer the check: search every evasion, no "stand pat".
            moves = list(board.legal_moves)
            if not moves:
                return -(MATE - ply)
            best = -INF
        else:
            stand_pat = evaluate(board)
            if stand_pat >= beta or ply >= MAX_QUIESCENCE_PLY:
                return stand_pat
            alpha = max(alpha, stand_pat)
            best = stand_pat
            moves = [m for m in board.generate_legal_captures()]
            moves += [m for m in board.legal_moves if m.promotion == chess.QUEEN and not board.is_capture(m)]
        moves.sort(key=lambda m: mvv_lva(board, m), reverse=True)

        for move in moves:
            board.push(move)
            score = -self._quiescence(board, -beta, -alpha, ply + 1)
            board.pop()
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        return best
