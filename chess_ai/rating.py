"""Estimate Elo ratings for every AI at every difficulty.

Method
------
1. Play a fixed schedule of games between our agents and Stockfish limited
   with ``UCI_Elo`` (its own calibrated strength limiter). Games run in
   parallel worker processes; each finished game is appended to
   ``ratings/results.jsonl`` so an interrupted run can be resumed.
2. Fit a Bradley-Terry (Elo) model to all results by maximum likelihood with
   the Stockfish players fixed at their UCI_Elo values. Agents too weak to
   play Stockfish (random, greedy, ...) are rated by chaining through games
   against agents that are. One virtual draw per pairing keeps 100% / 0%
   scores finite (as BayesElo does).
3. "Hard" (5 s/move) is extrapolated: Easy (0.5 s) and Medium (2 s) are two
   doublings of thinking time apart, which gives the Elo gained per doubling;
   Hard is log2(5/2) = 1.32 doublings above Medium.

The ratings are relative to Stockfish's UCI_Elo scale at fast time controls -
a useful yardstick, not an official FIDE rating.

Usage::

    python -m chess_ai.rating run --workers 6     # play (or resume) the schedule
    python -m chess_ai.rating fit                 # fit and write chess_ai/ratings.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .agents import DIFFICULTIES, create_agent

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "ratings" / "results.jsonl"
RATINGS_JSON = Path(__file__).resolve().parent / "ratings.json"

STOCKFISH_TIME = 0.5  # seconds per move for anchor games (strength comes from UCI_Elo)
TIME_SCALED = ["minimax", "alphabeta", "negamax", "mcts"]  # strength depends on thinking time
FIXED = ["random", "greedy"]  # same strength at every difficulty

# (player A, player B, games). Players are "agent@Difficulty" or "sf<elo>".
SCHEDULE: list[tuple[str, str, int]] = [
    # bottom of the ladder
    ("random", "greedy", 8),
    ("greedy", "minimax@Easy", 12),
    ("greedy", "mcts@Easy", 12),
    # each technique against itself with more time
    ("minimax@Easy", "minimax@Medium", 12),
    ("alphabeta@Easy", "alphabeta@Medium", 12),
    ("negamax@Easy", "negamax@Medium", 12),
    ("mcts@Easy", "mcts@Medium", 12),
    # neighbours at the same difficulty
    ("minimax@Easy", "alphabeta@Easy", 12),
    ("alphabeta@Easy", "negamax@Easy", 12),
    ("mcts@Easy", "minimax@Easy", 12),
    ("mcts@Easy", "alphabeta@Easy", 12),
    ("minimax@Medium", "alphabeta@Medium", 12),
    ("alphabeta@Medium", "negamax@Medium", 12),
    ("mcts@Medium", "alphabeta@Medium", 12),
    # Stockfish anchors
    ("alphabeta@Easy", "sf1320", 12),
    ("negamax@Easy", "sf1320", 16),
    ("minimax@Medium", "sf1320", 12),
    ("alphabeta@Medium", "sf1320", 16),
    ("negamax@Medium", "sf1320", 16),
    ("negamax@Medium", "sf1600", 16),
    ("mcts@Medium", "sf1320", 12),
]

# Quick Hard check (~10 min on 6 workers, games capped at HARD_MAX_PLIES).
# Too few games to rate Hard on their own, so they update the extrapolated
# estimate as a Bayesian prior instead (see fit_hard).
HARD_SCHEDULE: list[tuple[str, str, int]] = [
    ("negamax@Hard", "negamax@Medium", 2),
    ("negamax@Hard", "sf2000", 2),
    ("alphabeta@Hard", "alphabeta@Medium", 3),
    ("mcts@Hard", "mcts@Medium", 3),
    ("minimax@Hard", "minimax@Medium", 2),
]
HARD_MAX_PLIES = 100
SCHEDULES = {"main": (SCHEDULE, 300), "hard": (HARD_SCHEDULE, HARD_MAX_PLIES)}


def is_anchor(player: str) -> bool:
    return player.startswith("sf")


def anchor_elo(player: str) -> int:
    return int(player[2:])


def make_player(player: str, seed: int):
    if is_anchor(player):
        return create_agent("stockfish", time_limit=STOCKFISH_TIME, stockfish_elo=anchor_elo(player))
    key, _, difficulty = player.partition("@")
    time_limit = DIFFICULTIES[difficulty].time_limit if difficulty else 1.0
    return create_agent(key, time_limit=time_limit, seed=seed)


# --------------------------------------------------------------------- play
def play_one(a: str, b: str, game_index: int, max_plies: int = 300) -> dict:
    """Play game ``game_index`` of pairing (a, b); runs in a worker process."""
    from .match import play_game, random_opening

    rng = random.Random(f"{a}|{b}|{game_index // 2}")
    opening = random_opening(rng, 2)
    a_white = game_index % 2 == 0
    pa, pb = make_player(a, seed=game_index), make_player(b, seed=game_index + 1000)
    start = time.time()
    try:
        white, black = (pa, pb) if a_white else (pb, pa)
        result, reason, board = play_game(white, black, opening, max_plies)
    finally:
        pa.close()
        pb.close()
    return {
        "a": a, "b": b, "game": game_index,
        "white": a if a_white else b, "black": b if a_white else a,
        "result": result, "reason": reason, "plies": board.ply(),
        "seconds": round(time.time() - start, 1),
    }


def load_results() -> list[dict]:
    if not RESULTS.exists():
        return []
    with RESULTS.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def run(workers: int, schedule: str = "main") -> None:
    pairings, max_plies = SCHEDULES[schedule]
    RESULTS.parent.mkdir(exist_ok=True)
    done = {(r["a"], r["b"], r["game"]) for r in load_results()}
    tasks = [(a, b, g) for a, b, n in pairings for g in range(n) if (a, b, g) not in done]
    # Longest games first so the pool finishes evenly.
    weight = {"Hard": 3, "Medium": 1}
    tasks.sort(key=lambda t: sum(w for d, w in weight.items() if d in t[0] + t[1]), reverse=True)
    print(f"{len(done)} games already played, {len(tasks)} to go, {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool, RESULTS.open("a") as out:
        futures = {pool.submit(play_one, *t, max_plies): t for t in tasks}
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"[{i}/{len(tasks)}] {rec['white']} - {rec['black']}: {rec['result']} "
                  f"({rec['reason']}, {rec['plies']} plies, {rec['seconds']}s)", flush=True)


# ---------------------------------------------------------------------- fit
def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400))


def fit(results: list[dict], iterations: int = 5000) -> dict[str, tuple[float, float, int]]:
    """Maximum-likelihood Elo per player -> (elo, 95% interval half-width, games)."""
    score: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])  # (a, b) -> [points for a, games]
    games = defaultdict(int)
    for r in results:
        a, b = r["white"], r["black"]
        s = {"1-0": 1.0, "0-1": 0.0}.get(r["result"], 0.5)
        key = (a, b) if a < b else (b, a)
        pts = s if key[0] == a else 1 - s
        score[key][0] += pts
        score[key][1] += 1
        games[a] += 1
        games[b] += 1
    for key in score:  # one virtual draw per pairing
        score[key][0] += 0.5
        score[key][1] += 1

    players = sorted(games)
    rating = {p: float(anchor_elo(p)) if is_anchor(p) else 1200.0 for p in players}
    free = [p for p in players if not is_anchor(p)]
    k = math.log(10) / 400
    # Newton-style coordinate updates on the log-likelihood.
    for _ in range(iterations):
        biggest = 0.0
        for p in free:
            grad = hess = 0.0
            for (a, b), (pts, n) in score.items():
                if p not in (a, b):
                    continue
                other = b if p == a else a
                mine = pts if p == a else n - pts
                e = _expected(rating[p], rating[other])
                grad += k * (mine - n * e)
                hess += k * k * n * e * (1 - e)
            step = grad / hess if hess > 0 else 0.0
            step = max(-200.0, min(200.0, step))
            rating[p] += step
            biggest = max(biggest, abs(step))
        if biggest < 0.01:
            break

    out = {}
    for p in players:
        if is_anchor(p):
            out[p] = (rating[p], 0.0, games[p])
            continue
        info = 0.0
        for (a, b), (pts, n) in score.items():
            if p in (a, b):
                other = b if p == a else a
                e = _expected(rating[p], rating[other])
                info += k * k * n * e * (1 - e)
        half_width = 1.96 / math.sqrt(info) if info > 0 else float("inf")
        out[p] = (rating[p], half_width, games[p])
    return out


def fit_hard(results: list[dict], fitted: dict, player: str, prior_mean: float, prior_sd: float):
    """MAP rating for a Hard player: Gaussian prior (the extrapolation) times
    the likelihood of its few games, with opponents fixed at their fitted Elo.
    Returns (elo, 95% half-width, games) or None if it has no games."""
    games = [r for r in results if player in (r["white"], r["black"])]
    if not games:
        return None
    k = math.log(10) / 400
    rating = prior_mean
    hess = 1 / prior_sd**2
    for _ in range(100):
        grad = -(rating - prior_mean) / prior_sd**2
        hess = 1 / prior_sd**2
        for g in games:
            other = g["black"] if g["white"] == player else g["white"]
            opp = anchor_elo(other) if is_anchor(other) else fitted[other][0]
            s = {"1-0": 1.0, "0-1": 0.0}.get(g["result"], 0.5)
            mine = s if g["white"] == player else 1 - s
            e = _expected(rating, opp)
            grad += k * (mine - e)
            hess += k * k * e * (1 - e)
        step = grad / hess
        rating += step
        if abs(step) < 0.01:
            break
    return rating, 1.96 / math.sqrt(hess), len(games)


def build_table(fitted: dict[str, tuple[float, float, int]], total_games: int,
                results: list[dict] | None = None) -> dict:
    agents: dict[str, dict] = {}
    for key in FIXED:
        if key in fitted:
            elo, ci, n = fitted[key]
            agents[key] = {d: {"elo": round(elo), "ci": round(ci), "games": n, "estimated": False} for d in DIFFICULTIES}
    for key in TIME_SCALED:
        easy, medium = fitted.get(f"{key}@Easy"), fitted.get(f"{key}@Medium")
        if not easy or not medium:
            continue
        per_doubling = (medium[0] - easy[0]) / 2
        hard_doublings = math.log2(DIFFICULTIES["Hard"].time_limit / DIFFICULTIES["Medium"].time_limit)
        hard_elo, hard_ci, hard_games = medium[0] + per_doubling * hard_doublings, medium[1] * 1.5, 0
        measured = fit_hard(results or [], fitted, f"{key}@Hard", hard_elo, hard_ci / 1.96)
        if measured is not None:
            hard_elo, hard_ci, hard_games = measured
        agents[key] = {
            "Easy": {"elo": round(easy[0]), "ci": round(easy[1]), "games": easy[2], "estimated": False},
            "Medium": {"elo": round(medium[0]), "ci": round(medium[1]), "games": medium[2], "estimated": False},
            # Still marked estimated: a handful of games refine the extrapolation.
            "Hard": {"elo": round(hard_elo), "ci": round(hard_ci), "games": hard_games, "estimated": True},
        }
    agents["stockfish"] = {
        d: {"elo": DIFFICULTIES[d].stockfish_elo, "ci": 0, "games": 0, "estimated": False} for d in DIFFICULTIES
    }
    return {
        "scale": "Stockfish UCI_Elo anchors at fast time control (not FIDE)",
        "generated": time.strftime("%Y-%m-%d"),
        "total_games": total_games,
        "agents": agents,
    }


def load_ratings() -> dict:
    """Ratings table for the GUI; empty if not generated yet."""
    try:
        return json.loads(RATINGS_JSON.read_text())
    except (OSError, ValueError):
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="play (or resume) the rating schedule")
    p_run.add_argument("--workers", type=int, default=6)
    p_run.add_argument("--schedule", choices=list(SCHEDULES), default="main")
    sub.add_parser("fit", help="fit ratings from results and write chess_ai/ratings.json")
    args = parser.parse_args()
    if args.cmd == "run":
        run(args.workers, args.schedule)
    else:
        results = load_results()
        # Hard games are too few for the joint fit; they refine the
        # extrapolated Hard estimate in build_table instead.
        main_results = [r for r in results if "@Hard" not in r["white"] + r["black"]]
        fitted = fit(main_results)
        for p, (elo, ci, n) in sorted(fitted.items(), key=lambda kv: kv[1][0]):
            print(f"{p:20} {elo:7.0f} +/- {ci:4.0f}  ({n} games)")
        table = build_table(fitted, len(results), results)
        for key, row in table["agents"].items():
            if key in TIME_SCALED and row["Hard"]["games"]:
                print(f"{key + '@Hard':20} {row['Hard']['elo']:7d} +/- {row['Hard']['ci']:4d}  "
                      f"({row['Hard']['games']} games + extrapolation prior)")
        RATINGS_JSON.write_text(json.dumps(table, indent=2) + "\n")
        print(f"wrote {RATINGS_JSON}")


if __name__ == "__main__":
    main()
