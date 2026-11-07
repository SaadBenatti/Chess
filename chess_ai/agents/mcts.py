"""Monte Carlo Tree Search (UCT) with an MCTS-Solver.

Each iteration has four phases:

1. selection - walk down the tree choosing the child with the best UCB1 score;
2. expansion - add one untried move as a new child (mating moves first);
3. simulation - play a short semi-random game (a "playout") from there;
4. backpropagation - add the result to every node on the path.

Results are numbers in [0, 1] stored from the point of view of the player who
made the move into that node, and flipped (``1 - result``) at each level on
the way up, so every node maximises for the side that chose it.

Full random games take hundreds of moves and mostly end in meaningless draws,
so playouts stop after ``rollout_depth`` plies and the position is scored by
squashing the static evaluation into a win probability.

**MCTS-Solver.** Averages alone never become certain, so plain MCTS struggles
to finish games: when far ahead every move looks "99% winning". The solver
also propagates *proven* results: a checkmate is a proven win for the player
who delivered it; a node is a proven loss for whoever moved into it if the
opponent has any proven winning reply; and it is a proven win if every reply
is a proven loss. Proven wins are played immediately and proven losses are
avoided, so forced mates are found and converted.

**Tree reuse.** After our move and the opponent's reply, the matching
grandchild of the previous root becomes the new root, keeping its statistics.
"""
from __future__ import annotations

import math
import random
import threading
import time

import chess

from ..evaluation import MATE, evaluate_white, mvv_lva
from .base import Agent, SearchStats, san_line

UNKNOWN, WIN, LOSS = 0, 1, -1  # proven status for the player who moved into the node


class Node:
    __slots__ = ("move", "parent", "children", "untried", "visits", "value", "proven")

    def __init__(self, move: chess.Move | None, parent: Node | None) -> None:
        self.move = move
        self.parent = parent
        self.children: list[Node] = []
        self.untried: list[chess.Move] | None = None  # filled lazily on first expansion
        self.visits = 0
        self.value = 0.0  # sum of results for the player who moved into this node
        self.proven = UNKNOWN


def _win_probability(white_cp: int, side: chess.Color) -> float:
    """Map a centipawn score to an expected result in [0, 1] for ``side``."""
    cp = white_cp if side == chess.WHITE else -white_cp
    return 1.0 / (1.0 + 10 ** (-cp / 400))


def _mating_moves_first(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    """Reorder so checkmating moves are expanded first (they are popped from the end)."""
    mates = []
    for move in moves:
        if board.gives_check(move):
            board.push(move)
            if board.is_checkmate():
                mates.append(move)
            board.pop()
    if not mates:
        return moves
    return [m for m in moves if m not in mates] + mates


class MCTSAgent(Agent):
    name = "MCTS"

    def __init__(
        self,
        time_limit: float = 2.0,
        max_iterations: int | None = None,
        exploration: float = 1.4,
        rollout_depth: int = 16,
        seed: int | None = None,
        reuse_tree: bool = True,
    ) -> None:
        super().__init__()
        self.time_limit = time_limit
        self.max_iterations = max_iterations
        self.exploration = exploration
        self.rollout_depth = rollout_depth
        self.rng = random.Random(seed)
        self.reuse_tree = reuse_tree
        self._last_root: Node | None = None
        self._last_fen: str | None = None

    # -- tree reuse --------------------------------------------------------
    def _reused_root(self, board: chess.Board) -> Node | None:
        if not self.reuse_tree or self._last_root is None or self._last_fen is None:
            return None
        target = board.fen()
        prev = chess.Board(self._last_fen)
        old_root = self._last_root
        self._last_root, self._last_fen = None, None  # an old tree is reused at most once
        for child in old_root.children:
            prev.push(child.move)
            for grandchild in child.children:
                prev.push(grandchild.move)
                match = prev.fen() == target
                prev.pop()
                if match:
                    grandchild.parent = None  # detach so backpropagation stops here
                    if not grandchild.children:
                        # A leaf may have been marked terminal for the old path
                        # (e.g. as a repetition); expand it afresh.
                        grandchild.untried = None
                        grandchild.proven = UNKNOWN
                    return grandchild
            prev.pop()
        return None

    # -- search ------------------------------------------------------------
    def choose_move(self, board: chess.Board, stop_event: threading.Event | None = None) -> chess.Move | None:
        board = board.copy()
        if board.is_game_over():
            return None
        start = time.perf_counter()
        deadline = start + self.time_limit

        root = self._reused_root(board) or Node(None, None)
        reused_visits = root.visits
        if root.untried is None:
            root.untried = _mating_moves_first(board, list(board.legal_moves))
        iterations = 0
        max_depth = 0

        while root.proven == UNKNOWN:
            if self.max_iterations is not None and iterations >= self.max_iterations:
                break
            if (iterations & 15) == 0 and iterations > 0:
                if time.perf_counter() >= deadline or (stop_event is not None and stop_event.is_set()):
                    break

            node = root
            pushed = 0
            # 1. Selection (proven nodes are treated as leaves)
            while node.proven == UNKNOWN and not node.untried and node.children:
                node = self._select_child(node)
                board.push(node.move)
                pushed += 1
            # 2. Expansion
            if node.proven == UNKNOWN:
                if node.untried is None:
                    # A repeated position is treated as a drawn leaf, so a winning
                    # MCTS does not drift into threefold repetition.
                    terminal = board.is_game_over() or board.is_repetition(2)
                    node.untried = [] if terminal else _mating_moves_first(board, list(board.legal_moves))
                if node.untried:
                    move = node.untried.pop()
                    board.push(move)
                    pushed += 1
                    child = Node(move, node)
                    node.children.append(child)
                    node = child
                    if board.is_checkmate():
                        child.proven = WIN
                        child.untried = []
            max_depth = max(max_depth, pushed)
            # 3. Simulation: result for the player who moved into `node`
            if node.proven != UNKNOWN:
                result = 1.0 if node.proven == WIN else 0.0
            else:
                result = self._rollout(board, not board.turn)
            # 4. Backpropagation (with solver)
            self._backpropagate(node, result)
            for _ in range(pushed):
                board.pop()
            iterations += 1

        if not root.children:  # e.g. max_iterations=0
            return self.rng.choice(list(board.legal_moves))
        best = self._final_choice(root)
        # Keep the root for next time; its grandchildren are matched by position.
        self._last_root, self._last_fen = root, board.fen()

        self.last_stats = self._stats(board, root, best, iterations, max_depth, reused_visits, start)
        return best.move

    def _backpropagate(self, node: Node, result: float) -> None:
        while node is not None:
            node.visits += 1
            node.value += result
            parent = node.parent
            if parent is not None and node.proven != UNKNOWN and parent.proven == UNKNOWN:
                if node.proven == WIN:
                    parent.proven = LOSS  # the side to move at parent has a winning reply
                elif not parent.untried and all(c.proven == LOSS for c in parent.children):
                    parent.proven = WIN  # every reply loses for the side to move at parent
            result = 1.0 - result
            node = parent

    def _select_child(self, node: Node) -> Node:
        for child in node.children:
            if child.proven == WIN:
                return child
        candidates = [c for c in node.children if c.proven != LOSS] or node.children
        log_n = math.log(node.visits)
        c = self.exploration
        return max(candidates, key=lambda ch: ch.value / ch.visits + c * math.sqrt(log_n / ch.visits))

    def _final_choice(self, root: Node) -> Node:
        wins = [c for c in root.children if c.proven == WIN]
        if wins:
            return max(wins, key=lambda c: c.visits)
        safe = [c for c in root.children if c.proven != LOSS] or root.children
        return max(safe, key=lambda c: c.visits)

    def _stats(self, board, root, best, iterations, max_depth, reused_visits, start) -> SearchStats:
        if best.proven == WIN:
            note = "proven win"
            cp_side = MATE - 1
        elif best.proven == LOSS:
            note = "proven loss"
            cp_side = -(MATE - 1)
        else:
            win_rate = best.value / best.visits
            p = min(max(win_rate, 1e-4), 1 - 1e-4)
            cp_side = int(-400 * math.log10(1 / p - 1))
            note = f"win {win_rate:.0%}, {best.visits} visits"
        if reused_visits:
            note += f", reused {reused_visits}"
        # Principal variation: follow the most visited children.
        line, node = [], root
        while node.children and len(line) < 8:
            node = max(node.children, key=lambda c: c.visits)
            line.append(node.move)
        return SearchStats(
            move=board.san(best.move),
            depth=max_depth,
            nodes=iterations,
            time=time.perf_counter() - start,
            score=cp_side if board.turn == chess.WHITE else -cp_side,
            note=note,
            pv=san_line(board, line) if line and line[0] == best.move else [board.san(best.move)],
        )

    def _rollout(self, board: chess.Board, side: chess.Color) -> float:
        """Short playout; returns the expected result for ``side``."""
        if board.move_stack and board.is_repetition(2) and not board.is_checkmate():
            return 0.5
        pushed = 0
        result: float | None = None
        for _ in range(self.rollout_depth):
            moves = list(board.legal_moves)
            if not moves:
                break
            if board.is_insufficient_material():
                result = 0.5
                break
            # Light heuristic: half the time take the best capture if there is one.
            captures = [m for m in moves if board.is_capture(m)]
            if captures and self.rng.random() < 0.5:
                move = max(captures, key=lambda m: mvv_lva(board, m))
            else:
                move = self.rng.choice(moves)
            board.push(move)
            pushed += 1

        if result is None:
            if board.is_checkmate():
                result = 1.0 if board.turn != side else 0.0
            elif board.is_stalemate() or board.is_insufficient_material() or board.is_repetition(3):
                result = 0.5
            else:
                result = _win_probability(evaluate_white(board), side)
        for _ in range(pushed):
            board.pop()
        return result
