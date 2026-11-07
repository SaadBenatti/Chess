"""Optional Stockfish opponent through python-chess's UCI engine support.

Stockfish is looked up in ``STOCKFISH_PATH``, then in the gitignored
``tools/`` folder, then on PATH. If none is found, :func:`find_stockfish`
returns ``None`` and the GUI hides this opponent.

Strength is set with ``UCI_LimitStrength`` / ``UCI_Elo``, Stockfish's own
calibrated Elo limiter (1320-3190). Those Stockfish players are also the
fixed anchors of the rating list in ``chess_ai/rating.py``.
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

import chess
import chess.engine

from ..evaluation import MATE
from .base import Agent, SearchStats

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
MIN_ELO, MAX_ELO = 1320, 3190


def find_stockfish() -> str | None:
    path = os.environ.get("STOCKFISH_PATH")
    if path and os.path.isfile(path):
        return path
    for candidate in sorted(TOOLS_DIR.glob("stockfish*/**/stockfish*.exe")) + sorted(TOOLS_DIR.glob("stockfish*/**/stockfish")):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("stockfish")


class StockfishAgent(Agent):
    name = "Stockfish"

    def __init__(self, time_limit: float = 1.0, elo: int = 1800, path: str | None = None) -> None:
        super().__init__()
        self.time_limit = time_limit
        self.elo = max(MIN_ELO, min(MAX_ELO, elo))
        self.path = path or find_stockfish()
        if self.path is None:
            raise RuntimeError("Stockfish not found; set STOCKFISH_PATH or put it in tools/")
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.Lock()

    def _get_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
            self._engine.configure({"UCI_LimitStrength": True, "UCI_Elo": self.elo, "Threads": 1, "Hash": 16})
        return self._engine

    def choose_move(self, board, stop_event=None):
        if board.is_game_over():
            return None
        start = time.perf_counter()
        with self._lock:
            result = self._get_engine().play(
                board, chess.engine.Limit(time=self.time_limit), info=chess.engine.INFO_SCORE | chess.engine.INFO_PV
            )
        score = result.info.get("score")
        pv = result.info.get("pv", [])
        line, replay = [], board.copy(stack=False)
        for move in pv[:8]:
            if move not in replay.legal_moves:
                break
            line.append(replay.san(move))
            replay.push(move)
        self.last_stats = SearchStats(
            move=board.san(result.move) if result.move else "",
            depth=result.info.get("depth", 0),
            nodes=result.info.get("nodes", 0),
            time=time.perf_counter() - start,
            score=score.white().score(mate_score=MATE) if score else None,
            note=f"limited to Elo {self.elo}",
            pv=line,
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
