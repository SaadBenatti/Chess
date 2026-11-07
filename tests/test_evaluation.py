import random

import chess

from chess_ai.evaluation import evaluate, evaluate_white, format_score, MATE


def random_positions(n: int, seed: int = 0, plies: int = 30) -> list[chess.Board]:
    rng = random.Random(seed)
    boards = []
    while len(boards) < n:
        board = chess.Board()
        for _ in range(rng.randrange(1, plies)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        boards.append(board)
    return boards


def test_start_position_is_balanced():
    assert evaluate_white(chess.Board()) == 0


def test_colour_flip_symmetry():
    # Mirroring the board and swapping colours must negate the score.
    for board in random_positions(50):
        assert evaluate_white(board) == -evaluate_white(board.mirror()), board.fen()


def test_side_to_move_perspective():
    board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert evaluate(board) > 0
    board.turn = chess.BLACK
    assert evaluate(board) < 0


def test_material_ordering():
    def extra(piece: str) -> int:
        return evaluate_white(chess.Board(f"4k3/8/8/8/3{piece}4/8/8/4K3 w - - 0 1"))

    assert extra("Q") > extra("R") > extra("B") > extra("P") > 0
    assert extra("N") > extra("P")


def test_white_pawns_prefer_advancing():
    home = evaluate_white(chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"))
    advanced = evaluate_white(chess.Board("4k3/4P3/8/8/8/8/8/4K3 w - - 0 1"))
    assert advanced > home


def test_format_score():
    assert format_score(125) == "+1.25"
    assert format_score(MATE - 1) == "+M1"
    assert format_score(-(MATE - 3)) == "-M2"
