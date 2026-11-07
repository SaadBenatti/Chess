"""Negamax with alpha-beta and the standard engine enhancements.

Negamax is minimax written once instead of twice: a position's value for the
side to move is the negation of its best child's value for the opponent
(``max(a, b) == -min(-a, -b)``). On top of alpha-beta this agent adds:

* principal-variation search (PVS): the first move is searched with a full
  window, the rest with a cheap zero-width window that only proves "not
  better"; a move that surprises is re-searched properly;
* aspiration windows: each iterative-deepening pass starts with a narrow
  window around the previous score;
* null-move pruning: if passing the turn still leaves us above beta, the
  position is so good that a reduced search is enough to cut it off;
* late-move reductions (LMR): quiet moves ordered late are searched one or
  two plies shallower first, and only re-searched if they look good;
* quiescence search: at depth 0 keep searching captures until the position is
  quiet, avoiding the "horizon effect";
* a transposition table keyed by Zobrist hash, which also yields the
  principal variation shown in the GUI;
* move ordering: transposition-table move, captures by MVV-LVA, killer moves,
  then the history heuristic;
* check extension: positions in check are searched one ply deeper.
"""
from __future__ import annotations

import chess
import chess.polyglot

from ..evaluation import MATE, MATE_THRESHOLD, evaluate, is_draw_by_rule, mvv_lva
from .search_base import INF, IterativeDeepeningAgent

EXACT, LOWER, UPPER = 0, 1, 2
TT_MAX_ENTRIES = 1_000_000
MAX_PLY = 128
ASPIRATION_WINDOW = 50
NULL_MOVE_REDUCTION = 2

# Move ordering tiers (higher is searched first).
_TT_MOVE = 1 << 30
_CAPTURE = 1 << 24
_KILLER_1 = 1 << 21
_KILLER_2 = (1 << 21) - 1
_HISTORY_CAP = (1 << 20)


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
    # Feature switches (used to measure what each enhancement is worth).
    # LMR is off: at the depths pure Python reaches (4-6 plies) it cost
    # strength - 5/12 with it vs 9/12 without, against the round-1 engine.
    use_aspiration = True
    use_null_move = True
    use_lmr = False

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tt: dict[int, tuple[int, int, int, chess.Move | None]] = {}
        self.killers: list[list[chess.Move | None]] = []
        self.history: list[list[int]] = []
        self._root_score: int | None = None

    def new_search(self) -> None:
        if len(self.tt) > TT_MAX_ENTRIES:
            self.tt.clear()
        self.killers = [[None, None] for _ in range(MAX_PLY)]
        self.history = [[0] * 64 for _ in range(64)]
        self._root_score = None

    # -- move ordering -----------------------------------------------------
    def _ordered(self, board: chess.Board, tt_move: chess.Move | None, ply: int) -> list[chess.Move]:
        killers = self.killers[ply] if ply < MAX_PLY else (None, None)
        history = self.history

        def key(move: chess.Move) -> int:
            if move == tt_move:
                return _TT_MOVE
            tactical = mvv_lva(board, move)
            if tactical:
                return _CAPTURE + tactical
            if move == killers[0]:
                return _KILLER_1
            if move == killers[1]:
                return _KILLER_2
            return min(history[move.from_square][move.to_square], _HISTORY_CAP)

        moves = self.shuffled_moves(board)
        moves.sort(key=key, reverse=True)
        return moves

    def _record_cutoff(self, move: chess.Move, depth: int, ply: int) -> None:
        if ply < MAX_PLY and self.killers[ply][0] != move:
            self.killers[ply][1] = self.killers[ply][0]
            self.killers[ply][0] = move
        self.history[move.from_square][move.to_square] += depth * depth

    # -- root --------------------------------------------------------------
    def search_root(self, board, depth, prev_best):
        prev = self._root_score
        if self.use_aspiration and depth >= 3 and prev is not None and abs(prev) < MATE_THRESHOLD:
            alpha, beta = prev - ASPIRATION_WINDOW, prev + ASPIRATION_WINDOW
        else:
            alpha, beta = -INF, INF
        while True:
            best, best_moves = self._root(board, depth, alpha, beta, prev_best)
            if best <= alpha:
                alpha = -INF  # failed low: widen and search again
            elif best >= beta:
                beta = INF  # failed high
            else:
                break
        self._root_score = best
        move = self.rng.choice(best_moves)
        self.last_pv = self._principal_variation(board, move, depth)
        white_score = best if board.turn == chess.WHITE else -best
        return move, white_score

    def _root(self, board, depth, alpha, beta, prev_best):
        best = -INF
        best_moves: list[chess.Move] = []
        a = alpha
        for i, move in enumerate(self._ordered(board, prev_best, 0)):
            board.push(move)
            if i == 0:
                score = -self._negamax(board, depth - 1, -beta, -a, 1)
            else:
                score = -self._negamax(board, depth - 1, -a - 1, -a, 1)
                if a < score < beta:
                    score = -self._negamax(board, depth - 1, -beta, -a, 1)
            board.pop()
            if score > best:
                best, best_moves = score, [move]
            elif score == best:
                best_moves.append(move)
            if best >= beta:
                break
            # One point below the best keeps tied moves exact for random tie-breaking.
            a = max(alpha, best - 1)
        return best, best_moves

    def _principal_variation(self, board: chess.Board, first: chess.Move, depth: int) -> list[chess.Move]:
        pv = [first]
        board = board.copy()
        board.push(first)
        seen = {chess.polyglot.zobrist_hash(board)}
        while len(pv) < depth:
            entry = self.tt.get(chess.polyglot.zobrist_hash(board))
            if entry is None or entry[3] is None or entry[3] not in board.legal_moves:
                break
            pv.append(entry[3])
            board.push(entry[3])
            key = chess.polyglot.zobrist_hash(board)
            if key in seen:
                break
            seen.add(key)
        return pv

    # -- main search -------------------------------------------------------
    def _negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int, allow_null: bool = True) -> int:
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

        if depth <= 0 or ply >= MAX_PLY - 1:
            return self._quiescence(board, alpha, beta, ply)

        pv_node = beta - alpha > 1

        # Null-move pruning. Skipped in check, in PV nodes and with only king
        # and pawns left (zugzwang positions, where passing would be best).
        if (
            self.use_null_move
            and allow_null
            and not pv_node
            and not in_check
            and depth >= 3
            and board.occupied_co[board.turn] & ~(board.pawns | board.kings)
            and evaluate(board) >= beta
        ):
            board.push(chess.Move.null())
            score = -self._negamax(board, depth - 1 - NULL_MOVE_REDUCTION, -beta, -beta + 1, ply + 1, False)
            board.pop()
            if score >= beta:
                return beta if score >= MATE_THRESHOLD else score

        moves = self._ordered(board, tt_move, ply)
        if not moves:
            return -(MATE - ply) if in_check else 0

        alpha_orig = alpha
        best, best_move = -INF, None
        for i, move in enumerate(moves):
            quiet = not move.promotion and not board.is_capture(move)
            board.push(move)
            if i == 0:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            else:
                reduction = 0
                if self.use_lmr and depth >= 3 and i >= 3 and quiet and not in_check and not board.is_check():
                    reduction = 1 if i < 8 else 2
                score = -self._negamax(board, depth - 1 - reduction, -alpha - 1, -alpha, ply + 1)
                if reduction and score > alpha:
                    score = -self._negamax(board, depth - 1, -alpha - 1, -alpha, ply + 1)
                if alpha < score < beta:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score > best:
                best, best_move = score, move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                if quiet:
                    self._record_cutoff(move, depth, ply)
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
            if stand_pat >= beta or ply >= MAX_PLY - 1:
                return stand_pat
            alpha = max(alpha, stand_pat)
            best = stand_pat
            moves = list(board.generate_legal_captures())
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
