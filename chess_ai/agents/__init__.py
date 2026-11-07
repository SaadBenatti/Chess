"""Registry of selectable AI players."""
from __future__ import annotations

from dataclasses import dataclass

from .alphabeta import AlphaBetaAgent
from .base import Agent, SearchStats
from .mcts import MCTSAgent
from .minimax import MinimaxAgent
from .negamax import NegamaxAgent
from .simple import GreedyAgent, RandomAgent
from .stockfish import StockfishAgent, find_stockfish

# key -> (display name, class). Order is the order shown in the menu.
AGENTS: dict[str, tuple[str, type[Agent]]] = {
    "random": ("Random", RandomAgent),
    "greedy": ("Greedy", GreedyAgent),
    "minimax": ("Minimax", MinimaxAgent),
    "alphabeta": ("Alpha-Beta", AlphaBetaAgent),
    "negamax": ("Negamax", NegamaxAgent),
    "mcts": ("MCTS", MCTSAgent),
    "stockfish": ("Stockfish", StockfishAgent),
}


@dataclass(frozen=True)
class Difficulty:
    time_limit: float     # seconds per move for the search agents
    stockfish_elo: int    # UCI_Elo for the Stockfish opponent


DIFFICULTIES: dict[str, Difficulty] = {
    "Easy": Difficulty(0.5, 1320),
    "Medium": Difficulty(2.0, 1800),
    "Hard": Difficulty(5.0, 2400),
}


def available_agents() -> list[str]:
    """Agent keys usable on this machine (Stockfish only if installed)."""
    return [k for k in AGENTS if k != "stockfish" or find_stockfish()]


def create_agent(key: str, time_limit: float = 2.0, seed: int | None = None, stockfish_elo: int = 1800) -> Agent:
    cls = AGENTS[key][1]
    if cls is StockfishAgent:
        return StockfishAgent(time_limit=time_limit, elo=stockfish_elo)
    if cls in (RandomAgent, GreedyAgent):
        return cls(seed=seed)
    return cls(time_limit=time_limit, seed=seed)


def create_for_difficulty(key: str, difficulty: str, seed: int | None = None) -> Agent:
    d = DIFFICULTIES[difficulty]
    # Stockfish's strength comes from its Elo limiter; give it a short, fixed think time.
    time_limit = 0.5 if key == "stockfish" else d.time_limit
    return create_agent(key, time_limit=time_limit, seed=seed, stockfish_elo=d.stockfish_elo)


__all__ = [
    "AGENTS",
    "DIFFICULTIES",
    "Agent",
    "Difficulty",
    "SearchStats",
    "available_agents",
    "create_agent",
    "create_for_difficulty",
]
