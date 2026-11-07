"""Registry of selectable AI players."""
from __future__ import annotations

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

# Difficulty -> (seconds per move for search agents, Stockfish skill level 0-20)
DIFFICULTIES: dict[str, tuple[float, int]] = {
    "Easy": (0.5, 1),
    "Medium": (2.0, 5),
    "Hard": (5.0, 10),
}


def available_agents() -> list[str]:
    """Agent keys usable on this machine (Stockfish only if installed)."""
    return [k for k in AGENTS if k != "stockfish" or find_stockfish()]


def create_agent(key: str, time_limit: float = 2.0, skill_level: int = 5, seed: int | None = None) -> Agent:
    _, cls = AGENTS[key]
    if cls is StockfishAgent:
        return StockfishAgent(time_limit=time_limit, skill_level=skill_level)
    if cls in (RandomAgent, GreedyAgent):
        return cls(seed=seed)
    return cls(time_limit=time_limit, seed=seed)


__all__ = [
    "AGENTS",
    "DIFFICULTIES",
    "Agent",
    "SearchStats",
    "available_agents",
    "create_agent",
]
