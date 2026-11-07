"""Static position evaluation shared by every search agent.

Scores are in centipawns (100 = one pawn). Piece-square tables are written the
way a human reads a board from White's side: the first row is rank 8, the last
row is rank 1. python-chess numbers squares from a1 = 0, so a White piece on
``sq`` uses index ``sq ^ 56`` (vertical mirror) and a Black piece uses ``sq``
directly - Black's "own" view of the board is the mirror image of White's.
"""
import chess

MATE = 100_000
MATE_THRESHOLD = MATE - 1_000  # any |score| above this is a forced mate

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# fmt: off
_PAWN = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
]
_KNIGHT = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]
_BISHOP = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
]
_ROOK = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
]
_QUEEN = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
]
_KING_MIDDLE = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20,
]
_KING_END = [
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50,
]
# fmt: on

PST = {
    chess.PAWN: _PAWN,
    chess.KNIGHT: _KNIGHT,
    chess.BISHOP: _BISHOP,
    chess.ROOK: _ROOK,
    chess.QUEEN: _QUEEN,
    chess.KING: _KING_MIDDLE,
}

# Total non-pawn material at or below which kings should centralise.
_ENDGAME_MATERIAL = 2 * (PIECE_VALUES[chess.ROOK] + PIECE_VALUES[chess.BISHOP])


def _non_pawn_material(board: chess.Board) -> int:
    total = 0
    for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += PIECE_VALUES[pt] * chess.popcount(board.pieces_mask(pt, chess.WHITE) | board.pieces_mask(pt, chess.BLACK))
    return total


def evaluate_white(board: chess.Board) -> int:
    """Static evaluation from White's point of view (positive = good for White).

    Does not detect checkmate/stalemate; search code handles terminal nodes.
    """
    endgame = _non_pawn_material(board) <= _ENDGAME_MATERIAL
    score = 0
    for pt in chess.PIECE_TYPES:
        table = _KING_END if (pt == chess.KING and endgame) else PST[pt]
        value = PIECE_VALUES[pt]
        for sq in chess.scan_forward(board.pieces_mask(pt, chess.WHITE)):
            score += value + table[sq ^ 56]
        for sq in chess.scan_forward(board.pieces_mask(pt, chess.BLACK)):
            score -= value + table[sq]
    return score


def evaluate(board: chess.Board) -> int:
    """Static evaluation from the side to move's point of view (for negamax)."""
    score = evaluate_white(board)
    return score if board.turn == chess.WHITE else -score


def is_draw_by_rule(board: chess.Board) -> bool:
    """Draws a search should score as 0.

    Any repetition of an earlier position counts (not just threefold): if a
    line repeats, neither side can make progress with it, so treating it as a
    draw stops a winning engine from shuffling pieces back and forth.
    """
    return (
        board.is_insufficient_material()
        or board.halfmove_clock >= 100
        or board.is_repetition(2)
    )


def mvv_lva(board: chess.Board, move: chess.Move) -> int:
    """Most-valuable-victim / least-valuable-attacker ordering key (higher first)."""
    if board.is_en_passant(move):
        victim = chess.PAWN
    else:
        victim = board.piece_type_at(move.to_square)
    attacker = board.piece_type_at(move.from_square)
    score = 0
    if victim:
        score += 10 * PIECE_VALUES[victim] - PIECE_VALUES[attacker or chess.PAWN] // 10 + 10_000
    if move.promotion:
        score += PIECE_VALUES[move.promotion]
    return score


def format_score(white_cp: int | None) -> str:
    """Human readable score from White's point of view, e.g. '+1.25' or 'M3'."""
    if white_cp is None:
        return "-"
    if abs(white_cp) >= MATE_THRESHOLD:
        plies = MATE - abs(white_cp)
        moves = (plies + 1) // 2
        return f"{'+' if white_cp > 0 else '-'}M{moves}"
    return f"{white_cp / 100:+.2f}"
