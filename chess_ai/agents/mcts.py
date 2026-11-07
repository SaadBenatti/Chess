"""Monte Carlo Tree Search (UCT).

Each iteration has four phases:

1. selection - walk down the tree choosing the child with the best UCB1 score;
2. expansion - add one untried move as a new child;
3. simulation - play a short semi-random game (a "playout") from there;
4. backpropagation - add the result to every node on the path.

Results are numbers in [0, 1] stored from the point of view of the player who
made the move into that node, and flipped (``1 - result``) at each level on
the way up, so every node maximises for the side that chose it.

Full random games take hundreds of moves and mostly end in meaningless draws,
so playouts stop after ``rollout_depth`` plies and the position is scored by
squashing the static evaluation into a win probability.
"""
from __future__ import annotations

import math
import random
import threading
import time

import chess

from ..evaluation import evaluate_white, mvv_lva
from .base import Agent, SearchStats


class Node:
    __slots__ = ("move", "parent", "children", "untried", "visits", "value")

    def __init__(self, move: chess.Move | None, parent: Node | None) -> None:
        self.move = move
        self.parent = parent
        self.children: list[Node] = []
        self.untried: list[chess.Move] | None = None  # filled lazily on first expansion
        self.visits = 0
        self.value = 0.0  # sum of results for the player who moved into this node


def _win_probability(white_cp: int, side: chess.Color) -> float:
    """Map a centipawn score to an expected result in [0, 1] for ``side``."""
    cp = white_cp if side == chess.WHITE else -white_cp
    return 1.0 / (1.0 + 10 ** (-cp / 400))


class MCTSAgent(Agent):
    name = "MCTS"

    def __init__(
        self,
        time_limit: float = 2.0,
        max_iterations: int | None = None,
        exploration: float = 1.4,
        rollout_depth: int = 16,
        seed: int | None = None,
    ) -> None:
        super().__init__()
        self.time_limit = time_limit
        self.max_iterations = max_iterations
        self.exploration = exploration
        self.rollout_depth = rollout_depth
        self.rng = random.Random(seed)

    def choose_move(self, board: chess.Board, stop_event: threading.Event | None = None) -> chess.Move | None:
        board = board.copy()
        if board.is_game_over():
            return None
        start = time.perf_counter()
        deadline = start + self.time_limit

        root = Node(None, None)
        root.untried = list(board.legal_moves)
        self.rng.shuffle(root.untried)
        iterations = 0
        max_depth = 0

        while True:
            if self.max_iterations is not None and iterations >= self.max_iterations:
                break
            if (iterations & 15) == 0 and iterations > 0:
                if time.perf_counter() >= deadline or (stop_event is not None and stop_event.is_set()):
                    break

            node = root
            pushed = 0
            # 1. Selection
            while not node.untried and node.children:
                node = self._select_child(node)
                board.push(node.move)
                pushed += 1
            # 2. Expansion
            if node.untried is None:
                # A repeated position is treated as a drawn leaf, so a winning
                # MCTS does not drift into threefold repetition.
                terminal = board.is_game_over() or board.is_repetition(2)
                node.untried = [] if terminal else list(board.legal_moves)
                self.rng.shuffle(node.untried)
            if node.untried:
                move = node.untried.pop()
                board.push(move)
                pushed += 1
                child = Node(move, node)
                node.children.append(child)
                node = child
            max_depth = max(max_depth, pushed)
            # 3. Simulation: result for the player who moved into `node`
            result = self._rollout(board, not board.turn)
            # 4. Backpropagation
            while node is not None:
                node.visits += 1
                node.value += result
                result = 1.0 - result
                node = node.parent
            for _ in range(pushed):
                board.pop()
            iterations += 1

        if not root.children:  # e.g. max_iterations=0
            return self.rng.choice(list(board.legal_moves))
        best = max(root.children, key=lambda c: c.visits)
        win_rate = best.value / best.visits
        # Convert the win rate back to an approximate centipawn score for display.
        p = min(max(win_rate, 1e-4), 1 - 1e-4)
        cp_side = int(-400 * math.log10(1 / p - 1))
        self.last_stats = SearchStats(
            move=board.san(best.move),
            depth=max_depth,
            nodes=iterations,
            time=time.perf_counter() - start,
            score=cp_side if board.turn == chess.WHITE else -cp_side,
            note=f"win {win_rate:.0%}, {best.visits} visits",
        )
        return best.move

    def _select_child(self, node: Node) -> Node:
        log_n = math.log(node.visits)
        c = self.exploration
        return max(
            node.children,
            key=lambda ch: ch.value / ch.visits + c * math.sqrt(log_n / ch.visits),
        )

    def _rollout(self, board: chess.Board, side: chess.Color) -> float:
        """Short playout; returns the expected result for ``side``."""
        pushed = 0
        result: float | None = None
        if board.move_stack and board.is_repetition(2) and not board.is_checkmate():
            return 0.5
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
