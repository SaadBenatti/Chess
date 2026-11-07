"""Optional Stockfish opponent through python-chess's UCI engine support.

Stockfish is found via the ``STOCKFISH_PATH`` environment variable or on PATH.
If it is not installed, :func:`find_stockfish` returns ``None`` and the GUI
hides this opponent.
"""
from __future__ import annotations

import os
import shutil
import threading
import time

import chess
import chess.engine

from ..evaluation import MATE
from .base import Agent, SearchStats


def find_stockfish() -> str | None:
    path = os.environ.get("STOCKFISH_PATH")
    if path and os.path.isfile(path):
        return path
    return shutil.which("stockfish")


class StockfishAgent(Agent):
    name = "Stockfish"

    def __init__(self, time_limit: float = 1.0, skill_level: int = 5, path: str | None = None, **_ignored) -> None:
        super().__init__()
        self.time_limit = time_limit
        self.skill_level = skill_level
        self.path = path or find_stockfish()
        if self.path is None:
            raise RuntimeError("Stockfish not found; set STOCKFISH_PATH or add it to PATH")
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.Lock()

    def _get_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
            self._engine.configure({"Skill Level": self.skill_level})
        return self._engine

    def choose_move(self, board, stop_event=None):
        if board.is_game_over():
            return None
        start = time.perf_counter()
        with self._lock:
            result = self._get_engine().play(
                board, chess.engine.Limit(time=self.time_limit), info=chess.engine.INFO_SCORE | chess.engine.INFO_BASIC
            )
        score = result.info.get("score")
        self.last_stats = SearchStats(
            move=board.san(result.move) if result.move else "",
            depth=result.info.get("depth", 0),
            nodes=result.info.get("nodes", 0),
            time=time.perf_counter() - start,
            score=score.white().score(mate_score=MATE) if score else None,
            note=f"skill {self.skill_level}",
        )
        return result.move

    def close(self) -> None:
        with self._lock:
            if self._engine is not None:
                try:
                    self._engine.quit()
                except chess.engine.EngineError:
                    pass
                self._engine = None
