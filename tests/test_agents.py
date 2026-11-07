import chess
import pytest

from chess_ai.agents import AGENTS, available_agents, create_agent
from chess_ai.agents.alphabeta import AlphaBetaAgent
from chess_ai.agents.minimax import MinimaxAgent
from chess_ai.agents.stockfish import find_stockfish
from tests.test_evaluation import random_positions

MINIMAX_FAMILY = ["minimax", "alphabeta", "negamax"]

MATE_IN_ONE = [
    ("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4", "h5f7"),  # scholar's mate
    ("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "a1a8"),  # back rank
    ("rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2", "d8h4"),  # fool's mate
]

# Two rooks against a lone king: mate in 2, no mate in 1.
MATE_IN_TWO = ["7k/8/8/8/8/8/R7/1R4K1 w - - 0 1"]


def is_forced_mate_in_two(board: chess.Board, move: chess.Move) -> bool:
    board = board.copy()
    board.push(move)
    if board.is_checkmate():
        return True
    for reply in board.legal_moves:
        board.push(reply)
        mates = False
        for follow in board.legal_moves:
            board.push(follow)
            mates = board.is_checkmate()
            board.pop()
            if mates:
                break
        board.pop()
        if not mates:
            return False
    return True


@pytest.mark.parametrize("key", MINIMAX_FAMILY + ["mcts", "greedy"])
@pytest.mark.parametrize("fen,expected", MATE_IN_ONE)
def test_finds_mate_in_one(key, fen, expected):
    agent = create_agent(key, time_limit=1.0, seed=1)
    assert agent.choose_move(chess.Board(fen)).uci() == expected


@pytest.mark.parametrize("key", ["alphabeta", "negamax"])
@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("fen", MATE_IN_TWO)
def test_finds_mate_in_two(key, fen, mirror):
    board = chess.Board(fen)
    if mirror:  # same puzzle with Black to move
        board = board.mirror()
    agent = create_agent(key, time_limit=5.0, seed=1)
    move = agent.choose_move(board)
    assert is_forced_mate_in_two(board, move)
    assert agent.last_stats.score is not None and abs(agent.last_stats.score) > 90_000


@pytest.mark.parametrize("key", MINIMAX_FAMILY)
def test_takes_free_queen(key):
    board = chess.Board("4k3/8/8/8/3q4/5N2/8/4K3 w - - 0 1")
    assert create_agent(key, time_limit=1.0, seed=1).choose_move(board).uci() == "f3d4"


@pytest.mark.parametrize("key", MINIMAX_FAMILY + ["mcts"])
def test_does_not_hang_queen(key):
    # White queen on e4 is attacked by the d5 pawn.
    board = chess.Board("4k3/8/8/3p4/4Q3/8/8/4K3 w - - 0 1")
    move = create_agent(key, time_limit=1.0, seed=1).choose_move(board)
    board.push(move)
    queen = board.pieces(chess.QUEEN, chess.WHITE).pop()
    assert not any(m.to_square == queen for m in board.legal_moves), move


def test_alphabeta_matches_minimax_with_fewer_nodes():
    for board in random_positions(5, seed=3, plies=12):
        if board.is_game_over():
            continue
        plain = MinimaxAgent(time_limit=60, max_depth=3, seed=0)
        pruned = AlphaBetaAgent(time_limit=60, max_depth=3, seed=0)
        plain.choose_move(board)
        pruned.choose_move(board)
        assert plain.last_stats.depth == pruned.last_stats.depth == 3
        assert plain.last_stats.score == pruned.last_stats.score, board.fen()
        assert pruned.last_stats.nodes < plain.last_stats.nodes


@pytest.mark.parametrize("key", [k for k in AGENTS if k != "stockfish"])
def test_returns_legal_moves(key):
    agent = create_agent(key, time_limit=0.05, seed=2)
    for board in random_positions(20, seed=5):
        if board.is_game_over():
            continue
        fen = board.fen()
        move = agent.choose_move(board)
        assert board.fen() == fen, "agent must not modify the caller's board"
        assert move in board.legal_moves


@pytest.mark.parametrize("key", [k for k in AGENTS if k != "stockfish"])
def test_game_over_returns_none(key):
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")  # fool's mate
    assert board.is_checkmate()
    assert create_agent(key, time_limit=0.1).choose_move(board) is None


@pytest.mark.skipif(find_stockfish() is None, reason="Stockfish not installed")
def test_stockfish_plays():
    assert "stockfish" in available_agents()
    agent = create_agent("stockfish", time_limit=0.1, skill_level=1)
    try:
        board = chess.Board()
        assert agent.choose_move(board) in board.legal_moves
    finally:
        agent.close()
