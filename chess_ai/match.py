"""Headless AI-vs-AI matches for measuring relative strength.

Usage::

    python -m chess_ai.match negamax alphabeta -n 10 --time 1
    python -m chess_ai.match mcts random -n 10

Games are played in pairs from the same short random opening with colours
swapped, so neither agent benefits from a lucky opening. Threefold repetition
and the fifty-move rule end a game as a draw; games longer than ``--max-plies``
are adjudicated by the static evaluation.
"""
from __future__ import annotations

import argparse
import random
from collections import Counter

import chess

from .agents import AGENTS, create_agent
from .evaluation import evaluate_white

ADJUDICATE_MARGIN = 300  # centipawns needed to win an over-long game


def random_opening(rng: random.Random, plies: int) -> list[chess.Move]:
    board = chess.Board()
    moves = []
    for _ in range(plies):
        move = rng.choice(list(board.legal_moves))
        board.push(move)
        moves.append(move)
    return moves


def play_game(white, black, opening: list[chess.Move], max_plies: int = 300) -> tuple[str, str, chess.Board]:
    """Return (result '1-0'/'0-1'/'1/2-1/2', reason, final board)."""
    board = chess.Board()
    for move in opening:
        board.push(move)
    players = {chess.WHITE: white, chess.BLACK: black}
    while True:
        outcome = board.outcome(claim_draw=True)
        if outcome is not None:
            return outcome.result(), outcome.termination.name.lower(), board
        if board.ply() >= max_plies:
            score = evaluate_white(board)
            if score > ADJUDICATE_MARGIN:
                return "1-0", f"adjudicated ({score:+d}cp)", board
            if score < -ADJUDICATE_MARGIN:
                return "0-1", f"adjudicated ({score:+d}cp)", board
            return "1/2-1/2", f"adjudicated ({score:+d}cp)", board
        move = players[board.turn].choose_move(board)
        board.push(move)


def run_match(key_a: str, key_b: str, games: int, time_limit: float, opening_plies: int, seed: int,
              max_plies: int = 300, verbose: bool = True) -> dict[str, float]:
    rng = random.Random(seed)
    agent_a = create_agent(key_a, time_limit=time_limit, seed=rng.randrange(2**31))
    agent_b = create_agent(key_b, time_limit=time_limit, seed=rng.randrange(2**31))
    points = {key_a: 0.0, key_b: 0.0}
    if key_a == key_b:
        points = {f"{key_a} (A)": 0.0, f"{key_b} (B)": 0.0}
    name_a, name_b = list(points)
    reasons: Counter[str] = Counter()
    opening: list[chess.Move] = []
    try:
        for i in range(games):
            if i % 2 == 0:
                opening = random_opening(rng, opening_plies)
            a_is_white = i % 2 == 0
            white, black = (agent_a, agent_b) if a_is_white else (agent_b, agent_a)
            w_name, b_name = (name_a, name_b) if a_is_white else (name_b, name_a)
            result, reason, board = play_game(white, black, opening, max_plies)
            if result == "1-0":
                points[w_name] += 1
            elif result == "0-1":
                points[b_name] += 1
            else:
                points[w_name] += 0.5
                points[b_name] += 0.5
            reasons[reason.split(" ")[0]] += 1
            if verbose:
                final = evaluate_white(board)
                print(f"game {i + 1:>2}: {w_name} (W) vs {b_name} (B): {result:<7} "
                      f"{reason}, {board.ply()} plies, final eval {final:+d}cp", flush=True)
    finally:
        agent_a.close()
        agent_b.close()
    if verbose:
        print(f"\n{name_a} {points[name_a]:g} - {points[name_b]:g} {name_b}")
        print("endings:", dict(reasons))
    return points


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("agent_a", choices=list(AGENTS))
    parser.add_argument("agent_b", choices=list(AGENTS))
    parser.add_argument("-n", "--games", type=int, default=10)
    parser.add_argument("--time", type=float, default=1.0, help="seconds per move for search agents")
    parser.add_argument("--opening-plies", type=int, default=2, help="random plies before the agents take over")
    parser.add_argument("--max-plies", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    run_match(args.agent_a, args.agent_b, args.games, args.time, args.opening_plies, args.seed, args.max_plies)


if __name__ == "__main__":
    main()
