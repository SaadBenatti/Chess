"""Static position evaluation shared by every search agent.

Scores are in centipawns (100 = one pawn). The evaluation is *tapered*: a
middlegame score and an endgame score are computed separately and blended by
how much material is left (``phase``), so e.g. the king hides in the
middlegame but walks to the centre in the endgame.

Terms: material, piece-square tables, passed / doubled / isolated pawns,
bishop pair, rooks on open files, piece mobility and a king pawn shield.

Piece-square tables are written the way a human reads a board from White's
side: the first row is rank 8, the last row is rank 1. python-chess numbers
squares from a1 = 0, so a White piece on ``sq`` uses index ``sq ^ 56``
(vertical mirror) and a Black piece uses ``sq`` directly.
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
_EG_VALUES = {**PIECE_VALUES, chess.PAWN: 120}

# fmt: off
_PAWN_MG = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
]
_PAWN_EG = [
     0,  0,  0,  0,  0,  0,  0,  0,
    60, 60, 60, 60, 60, 60, 60, 60,
    40, 40, 40, 40, 40, 40, 40, 40,
    25, 25, 25, 25, 25, 25, 25, 25,
    15, 15, 15, 15, 15, 15, 15, 15,
     5,  5,  5,  5,  5,  5,  5,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
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
_KING_MG = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20,
]
_KING_EG = [
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

PST_MG = {chess.PAWN: _PAWN_MG, chess.KNIGHT: _KNIGHT, chess.BISHOP: _BISHOP,
          chess.ROOK: _ROOK, chess.QUEEN: _QUEEN, chess.KING: _KING_MG}
PST_EG = {**PST_MG, chess.PAWN: _PAWN_EG, chess.KING: _KING_EG}

# Game phase: 24 with all pieces on the board, 0 with only kings and pawns.
_PHASE = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}
MAX_PHASE = 24

# Passed pawn bonus by rank counted from the pawn's own side (index 1 = home rank).
_PASSED_MG = [0, 5, 5, 10, 20, 35, 60, 0]
_PASSED_EG = [0, 10, 15, 25, 45, 75, 120, 0]
_DOUBLED = (-10, -20)   # (mg, eg) per extra pawn on a file
_ISOLATED = (-10, -15)  # per pawn with no friendly pawn on adjacent files
_BISHOP_PAIR = (30, 50)
_ROOK_OPEN = (25, 10)
_ROOK_HALF_OPEN = (12, 5)
_SHIELD = 12            # mg bonus per pawn directly in front of a castled king
# Mobility: (mg, eg) per attacked square not occupied by own pieces, centred
# on a typical count so the term is roughly zero on average.
_MOBILITY = {
    chess.KNIGHT: (4, 4, 4),
    chess.BISHOP: (4, 5, 6),
    chess.ROOK: (2, 4, 7),
    chess.QUEEN: (1, 2, 13),
}

# Precomputed bitboard masks.
_FILES = list(chess.BB_FILES)
_ADJACENT_FILES = [(_FILES[f - 1] if f > 0 else 0) | (_FILES[f + 1] if f < 7 else 0) for f in range(8)]


def _passed_masks(color: chess.Color) -> list[int]:
    masks = []
    for sq in chess.SQUARES:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        ahead = range(r + 1, 8) if color == chess.WHITE else range(0, r)
        front = 0
        for rank in ahead:
            front |= chess.BB_RANKS[rank]
        masks.append(front & (_FILES[f] | _ADJACENT_FILES[f]))
    return masks


_PASSED_MASK = {chess.WHITE: _passed_masks(chess.WHITE), chess.BLACK: _passed_masks(chess.BLACK)}


def _side_score(board: chess.Board, color: chess.Color) -> tuple[int, int, int]:
    """(middlegame, endgame, phase) contribution of one side."""
    own = board.occupied_co[color]
    flip = 56 if color == chess.WHITE else 0
    my_pawns = board.pawns & own
    their_pawns = board.pawns & board.occupied_co[not color]
    mg = eg = phase = 0

    for pt in chess.PIECE_TYPES:
        mask = board.pieces_mask(pt, color)
        if not mask:
            continue
        pst_mg, pst_eg = PST_MG[pt], PST_EG[pt]
        val_mg, val_eg = PIECE_VALUES[pt], _EG_VALUES[pt]
        mob = _MOBILITY.get(pt)
        count = 0
        for sq in chess.scan_forward(mask):
            count += 1
            idx = sq ^ flip
            mg += val_mg + pst_mg[idx]
            eg += val_eg + pst_eg[idx]
            if mob is not None:
                n = chess.popcount(board.attacks_mask(sq) & ~own) - mob[2]
                mg += mob[0] * n
                eg += mob[1] * n
            if pt == chess.PAWN:
                f = sq & 7
                if not (_PASSED_MASK[color][sq] & their_pawns):
                    rel_rank = (sq >> 3) if color == chess.WHITE else 7 - (sq >> 3)
                    mg += _PASSED_MG[rel_rank]
                    eg += _PASSED_EG[rel_rank]
                if not (_ADJACENT_FILES[f] & my_pawns):
                    mg += _ISOLATED[0]
                    eg += _ISOLATED[1]
            elif pt == chess.ROOK:
                file_mask = _FILES[sq & 7]
                if not (file_mask & board.pawns):
                    mg += _ROOK_OPEN[0]
                    eg += _ROOK_OPEN[1]
                elif not (file_mask & my_pawns):
                    mg += _ROOK_HALF_OPEN[0]
                    eg += _ROOK_HALF_OPEN[1]
        phase += _PHASE.get(pt, 0) * count
        if pt == chess.BISHOP and count >= 2:
            mg += _BISHOP_PAIR[0]
            eg += _BISHOP_PAIR[1]

    for f in range(8):
        n = chess.popcount(my_pawns & _FILES[f])
        if n > 1:
            mg += _DOUBLED[0] * (n - 1)
            eg += _DOUBLED[1] * (n - 1)

    # Pawn shield: own pawns on the three squares in front of a king on its back two ranks.
    king = board.king(color)
    if king is not None:
        rel_rank = (king >> 3) if color == chess.WHITE else 7 - (king >> 3)
        if rel_rank <= 1:
            f = king & 7
            front_rank = (king >> 3) + (1 if color == chess.WHITE else -1)
            shield = chess.BB_RANKS[front_rank] & (_FILES[f] | _ADJACENT_FILES[f])
            mg += _SHIELD * chess.popcount(shield & my_pawns)

    return mg, eg, phase


def evaluate_white(board: chess.Board) -> int:
    """Static evaluation from White's point of view (positive = good for White).

    Does not detect checkmate/stalemate; search code handles terminal nodes.
    """
    w_mg, w_eg, w_phase = _side_score(board, chess.WHITE)
    b_mg, b_eg, b_phase = _side_score(board, chess.BLACK)
    phase = min(w_phase + b_phase, MAX_PHASE)
    mg, eg = w_mg - b_mg, w_eg - b_eg
    # int() truncates toward zero, keeping the score exactly antisymmetric.
    return int((mg * phase + eg * (MAX_PHASE - phase)) / MAX_PHASE)


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
    """Human readable score from White's point of view, e.g. '+1.25' or '+M3'."""
    if white_cp is None:
        return "-"
    if abs(white_cp) >= MATE_THRESHOLD:
        plies = MATE - abs(white_cp)
        moves = (plies + 1) // 2
        return f"{'+' if white_cp > 0 else '-'}M{moves}"
    return f"{white_cp / 100:+.2f}"
