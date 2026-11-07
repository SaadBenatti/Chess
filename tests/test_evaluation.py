import random

import chess

from chess_ai.evaluation import MATE, PIECE_VALUES, evaluate, evaluate_white, format_score


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


def test_passed_pawn_bonus():
    # f7 stops the e5 pawn (and is itself stopped); a7 lets e5 run.
    stopped = evaluate_white(chess.Board("4k3/5p2/8/4P3/8/8/8/4K3 w - - 0 1"))
    passed = evaluate_white(chess.Board("4k3/p7/8/4P3/8/8/8/4K3 w - - 0 1"))
    assert passed - stopped >= 20


def test_doubled_and_isolated_pawns_penalised():
    healthy = evaluate_white(chess.Board("4k3/8/8/8/8/8/3PP3/4K3 w - - 0 1"))
    doubled = evaluate_white(chess.Board("4k3/8/8/8/8/4P3/4P3/4K3 w - - 0 1"))
    assert healthy > doubled


def test_bishop_pair_bonus():
    pair = evaluate_white(chess.Board("4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1"))
    knight_bishop = evaluate_white(chess.Board("4k3/8/8/8/8/8/8/2B1KN2 w - - 0 1"))
    assert pair - knight_bishop > PIECE_VALUES[chess.BISHOP] - PIECE_VALUES[chess.KNIGHT]


def test_rook_prefers_open_file():
    open_file = evaluate_white(chess.Board("4k3/pppp1ppp/8/8/8/8/PPPP1PPP/4RK2 w - - 0 1"))
    closed_file = evaluate_white(chess.Board("4k3/pppp1ppp/8/8/8/8/PPPP1PPP/3R1K2 w - - 0 1"))
    assert open_file > closed_file


def test_king_shield():
    # Identical except which three pawns stand on rank 2; their PST values are
    # equal, so the only difference is the shield in front of the g1 king.
    sheltered = evaluate_white(chess.Board("1n2k1n1/8/8/8/8/8/5PPP/1N4K1 w - - 0 1"))
    exposed = evaluate_white(chess.Board("1n2k1n1/8/8/8/8/8/PPP5/1N4K1 w - - 0 1"))
    assert sheltered > exposed


def test_rating_fit_recovers_known_gap():
    from chess_ai.rating import fit

    # 150 wins, 50 losses against a 1500 anchor => 75% => about +191 Elo.
    games = [{"white": "x", "black": "sf1500", "result": "1-0"}] * 150
    games += [{"white": "x", "black": "sf1500", "result": "0-1"}] * 50
    elo, ci, n = fit(games)["x"]
    assert abs(elo - 1691) < 5
    assert n == 200 and 0 < ci < 100


def test_format_score():
    assert format_score(125) == "+1.25"
    assert format_score(MATE - 1) == "+M1"
    assert format_score(-(MATE - 3)) == "-M2"
