"""Pygame front end: menu, board, eval bar and a side panel with live search statistics.

AI players think on a background thread so the window stays responsive. Only
one AI thread runs at a time; results are tagged with a "generation" number
so a move computed before an undo/restart is discarded.
"""
from __future__ import annotations

import math
import queue
import threading
import time
import traceback
from pathlib import Path

import chess
import pygame

from .agents import AGENTS, DIFFICULTIES, Agent, SearchStats, available_agents, create_for_difficulty
from .agents.negamax import NegamaxAgent
from .evaluation import MATE_THRESHOLD, format_score
from .rating import load_ratings

SQ = 100
BOARD_PX = 8 * SQ
BAR_W = 28
PANEL_X = BOARD_PX + BAR_W
PANEL_W = 360
WIDTH, HEIGHT = PANEL_X + PANEL_W, BOARD_PX
FPS = 60
HINT_TIME = 1.0
ASSETS = Path(__file__).resolve().parent.parent / "assets"

# colours
BG = (30, 32, 36)
PANEL_BG = (40, 43, 48)
TEXT = (230, 230, 230)
MUTED = (150, 155, 165)
ACCENT = (70, 140, 230)
BUTTON = (60, 64, 72)
BUTTON_SEL = (70, 140, 230)
LIGHT_SQ = (240, 217, 181)
DARK_SQ = (181, 136, 99)
LAST_MOVE = (246, 226, 90, 120)
CHECK = (220, 40, 40, 150)
SELECTED = (50, 120, 230)
TARGET = (30, 30, 30, 70)
AI_ARROW = (235, 130, 30, 170)
HINT_ARROW = (40, 170, 80, 190)

PROMOTION_ORDER = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
HUMAN = "human"


def _player_name(key: str) -> str:
    return "Human" if key == HUMAN else AGENTS[key][0]


def _white_fraction(white_cp: int) -> float:
    """Share of the eval bar that is white (0.5 = equal)."""
    if white_cp >= MATE_THRESHOLD:
        return 1.0
    if white_cp <= -MATE_THRESHOLD:
        return 0.0
    return 1.0 / (1.0 + 10 ** (-white_cp / 400))


class Button:
    def __init__(self, rect: pygame.Rect, label: str, value: str) -> None:
        self.rect = rect
        self.label = label
        self.value = value

    def draw(self, surf: pygame.Surface, font: pygame.font.Font, selected: bool,
             badge: str = "", badge_font: pygame.font.Font | None = None) -> None:
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        colour = BUTTON_SEL if selected else (tuple(min(c + 15, 255) for c in BUTTON) if hover else BUTTON)
        pygame.draw.rect(surf, colour, self.rect, border_radius=8)
        if badge and badge_font is not None:
            text = font.render(self.label, True, TEXT)
            surf.blit(text, text.get_rect(midleft=(self.rect.x + 18, self.rect.centery)))
            b = badge_font.render(badge, True, TEXT if selected else MUTED)
            surf.blit(b, b.get_rect(midright=(self.rect.right - 16, self.rect.centery)))
        else:
            text = font.render(self.label, True, TEXT)
            surf.blit(text, text.get_rect(center=self.rect.center))


class ChessGUI:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Chess AI")
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.Font(None, 64)
        self.font = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 24)
        self.font_coord = pygame.font.Font(None, 22)
        self.pieces = {}
        for symbol in "pnbrqkPNBRQK":
            prefix = "w" if symbol.isupper() else "b"
            name = chess.piece_name(chess.Piece.from_symbol(symbol).piece_type)
            self.pieces[symbol] = pygame.image.load(ASSETS / f"{prefix}_{name}.png").convert_alpha()
        self.ratings = load_ratings().get("agents", {})

        # menu choices
        self.choice = {chess.WHITE: HUMAN, chess.BLACK: "negamax"}
        self.difficulty = "Medium"
        self.state = "menu"
        self._build_menu()

        # game state (set by start_game)
        self.board = chess.Board()
        self.agents: dict[chess.Color, Agent | None] = {chess.WHITE: None, chess.BLACK: None}
        self.stats: dict[chess.Color, SearchStats | None] = {chess.WHITE: None, chess.BLACK: None}
        self.eval_white: int | None = None
        self.flipped = False
        self.selected: chess.Square | None = None
        self.targets: list[chess.Move] = []
        self.promotion: list[chess.Move] = []
        self.outcome: chess.Outcome | None = None
        self.san_history: list[str] = []
        self.ai_moves: set[int] = set()  # plies played by an AI (for the arrow)
        self.hint: chess.Move | None = None
        self.hint_busy = False
        self.hint_agent: NegamaxAgent | None = None
        self.error = ""

        # background thread bookkeeping
        self.generation = 0
        self.ai_thread: threading.Thread | None = None
        self.ai_stop = threading.Event()
        self.ai_started = 0.0
        self.ai_busy = False
        self.results: queue.Queue = queue.Queue()

    # ------------------------------------------------------------------ menu
    def _build_menu(self) -> None:
        options = [HUMAN] + available_agents()
        self.menu_buttons: list[tuple[chess.Color, Button]] = []
        for color, x in ((chess.WHITE, WIDTH // 2 - 340), (chess.BLACK, WIDTH // 2 + 20)):
            for i, key in enumerate(options):
                rect = pygame.Rect(x, 165 + i * 52, 320, 44)
                self.menu_buttons.append((color, Button(rect, _player_name(key), key)))
        self.diff_buttons = []
        for i, name in enumerate(DIFFICULTIES):
            rect = pygame.Rect(WIDTH // 2 - 255 + i * 175, 640, 160, 44)
            self.diff_buttons.append(Button(rect, name, name))
        self.start_button = Button(pygame.Rect(WIDTH // 2 - 120, 718, 240, 54), "Start", "start")

    def elo_label(self, key: str, difficulty: str) -> str:
        if key == HUMAN:
            return ""
        if key == "stockfish":  # set directly by Stockfish's UCI_Elo limiter
            return f"Elo {DIFFICULTIES[difficulty].stockfish_elo}"
        entry = self.ratings.get(key, {}).get(difficulty)
        if not entry:
            return "Elo ?"
        return f"Elo {'~' if entry['estimated'] else ''}{entry['elo']}"

    def _menu_click(self, pos) -> None:
        for color, button in self.menu_buttons:
            if button.rect.collidepoint(pos):
                self.choice[color] = button.value
        for button in self.diff_buttons:
            if button.rect.collidepoint(pos):
                self.difficulty = button.value
        if self.start_button.rect.collidepoint(pos):
            self.start_game()

    def _draw_menu(self) -> None:
        self.screen.fill(BG)
        title = self.font_big.render("Chess AI", True, TEXT)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 55)))
        sub = self.font_small.render(
            "Pick a player for each side and a difficulty (thinking time). Numbers are estimated Elo.", True, MUTED)
        self.screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 100)))
        for color, x in ((chess.WHITE, WIDTH // 2 - 340), (chess.BLACK, WIDTH // 2 + 20)):
            head = self.font.render("White" if color else "Black", True, TEXT)
            self.screen.blit(head, head.get_rect(center=(x + 160, 140)))
        for color, button in self.menu_buttons:
            button.draw(self.screen, self.font, self.choice[color] == button.value,
                        self.elo_label(button.value, self.difficulty), self.font_small)
        label = self.font_small.render("Difficulty", True, MUTED)
        self.screen.blit(label, label.get_rect(center=(WIDTH // 2, 618)))
        for button in self.diff_buttons:
            button.draw(self.screen, self.font, self.difficulty == button.value)
        note = self.font_small.render("~ = extrapolated from Easy/Medium   ? = not rated yet", True, MUTED)
        self.screen.blit(note, note.get_rect(center=(WIDTH // 2, 700)))
        self.start_button.draw(self.screen, self.font, True)

    # ------------------------------------------------------------ game setup
    def _close_agents(self) -> None:
        self._cancel_ai()
        for agent in self.agents.values():
            if agent is not None:
                agent.close()
        self.agents = {chess.WHITE: None, chess.BLACK: None}

    def start_game(self) -> None:
        self._close_agents()
        for color in chess.COLORS:
            key = self.choice[color]
            self.agents[color] = None if key == HUMAN else create_for_difficulty(key, self.difficulty)
        self.board = chess.Board()
        self.stats = {chess.WHITE: None, chess.BLACK: None}
        self.eval_white = None
        self.ai_moves = set()
        # Show the board from the human's side; White's side otherwise.
        self.flipped = self.agents[chess.WHITE] is not None and self.agents[chess.BLACK] is None
        self.error = ""
        self._after_board_change()
        self.state = "game"

    def _after_board_change(self) -> None:
        self.selected = None
        self.targets = []
        self.promotion = []
        self.hint = None
        self.outcome = self.board.outcome(claim_draw=True)
        self.ai_moves = {ply for ply in self.ai_moves if ply < len(self.board.move_stack)}
        replay = chess.Board()
        self.san_history = []
        for move in self.board.move_stack:
            self.san_history.append(replay.san(move))
            replay.push(move)

    def _push(self, move: chess.Move) -> None:
        self.board.push(move)
        self._after_board_change()

    # ------------------------------------------------------- background work
    def _cancel_ai(self) -> None:
        """Invalidate any running search or hint; its result will be ignored."""
        self.generation += 1
        self.ai_stop.set()
        self.ai_busy = False
        self.hint_busy = False

    def _spawn(self, kind: str, agent: Agent) -> None:
        gen, stop, board = self.generation, self.ai_stop, self.board.copy()

        def work() -> None:
            try:
                move = agent.choose_move(board, stop)
                self.results.put((kind, gen, move, agent.last_stats, None))
            except Exception:  # surface errors in the panel instead of dying silently
                self.results.put((kind, gen, None, None, traceback.format_exc()))

        self.ai_thread = threading.Thread(target=work, daemon=True)
        self.ai_thread.start()

    def _thread_free(self) -> bool:
        return self.ai_thread is None or not self.ai_thread.is_alive()

    def _maybe_start_ai(self) -> None:
        if self.state != "game" or self.outcome is not None or self.ai_busy or self.hint_busy:
            return
        agent = self.agents[self.board.turn]
        if agent is None or not self._thread_free():
            return  # human to move, or a cancelled search still unwinding
        self.ai_stop = threading.Event()
        self.ai_busy = True
        self.ai_started = time.perf_counter()
        self._spawn("move", agent)

    def _request_hint(self) -> None:
        if (self.outcome is not None or self.agents[self.board.turn] is not None
                or self.hint_busy or self.ai_busy or not self._thread_free()):
            return
        if self.hint_agent is None:
            self.hint_agent = NegamaxAgent(time_limit=HINT_TIME)
        self.ai_stop = threading.Event()
        self.hint_busy = True
        self.ai_started = time.perf_counter()
        self._spawn("hint", self.hint_agent)

    def _collect_results(self) -> None:
        while not self.results.empty():
            kind, gen, move, stats, err = self.results.get()
            if gen != self.generation:
                continue
            if kind == "hint":
                self.hint_busy = False
                if move is not None and move in self.board.legal_moves:
                    self.hint = move
                    if stats is not None and stats.score is not None:
                        self.eval_white = stats.score
                continue
            self.ai_busy = False
            if err:
                print(err)
                self.error = err.strip().splitlines()[-1]
                continue
            if move is not None and move in self.board.legal_moves:
                self.stats[self.board.turn] = stats
                if stats is not None and stats.score is not None:
                    self.eval_white = stats.score
                self.ai_moves.add(len(self.board.move_stack))
                self._push(move)

    # ----------------------------------------------------------- human input
    def _square_at(self, pos) -> chess.Square:
        col, row = pos[0] // SQ, pos[1] // SQ
        if self.flipped:
            return chess.square(7 - col, row)
        return chess.square(col, 7 - row)

    def _square_xy(self, sq: chess.Square) -> tuple[int, int]:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        if self.flipped:
            return (7 - f) * SQ, r * SQ
        return f * SQ, (7 - r) * SQ

    def _square_rect(self, sq: chess.Square) -> pygame.Rect:
        return pygame.Rect(*self._square_xy(sq), SQ, SQ)

    def _promotion_rects(self) -> list[tuple[pygame.Rect, chess.Move]]:
        if not self.promotion:
            return []
        x, y = self._square_xy(self.promotion[0].to_square)
        step = SQ if y == 0 else -SQ  # grow away from the edge
        by_piece = {m.promotion: m for m in self.promotion}
        return [(pygame.Rect(x, y + i * step, SQ, SQ), by_piece[pt]) for i, pt in enumerate(PROMOTION_ORDER)]

    def _human_click(self, pos) -> None:
        if self.outcome is not None or self.agents[self.board.turn] is not None or pos[0] >= BOARD_PX:
            return
        if self.promotion:
            for rect, move in self._promotion_rects():
                if rect.collidepoint(pos):
                    self._push(move)
                    return
            self.promotion = []
            return
        sq = self._square_at(pos)
        candidates = [m for m in self.targets if m.to_square == sq]
        if candidates:
            if len(candidates) > 1:  # promotion: let the player choose the piece
                self.promotion = candidates
            else:
                self._push(candidates[0])
            return
        piece = self.board.piece_at(sq)
        if piece is not None and piece.color == self.board.turn and sq != self.selected:
            self.selected = sq
            self.targets = [m for m in self.board.legal_moves if m.from_square == sq]
        else:
            self.selected, self.targets = None, []

    def _undo(self) -> None:
        if all(agent is not None for agent in self.agents.values()) or not self.board.move_stack:
            return  # nothing to undo for the human in AI-vs-AI
        self._cancel_ai()
        self.board.pop()
        # Keep popping AI moves until it is a human's turn again.
        while self.board.move_stack and self.agents[self.board.turn] is not None:
            self.board.pop()
        for color in chess.COLORS:
            self.stats[color] = None
        self._after_board_change()

    # --------------------------------------------------------------- drawing
    def _draw_arrow(self, surf: pygame.Surface, move: chess.Move, colour) -> None:
        start = pygame.Vector2(self._square_rect(move.from_square).center)
        end = pygame.Vector2(self._square_rect(move.to_square).center)
        direction = end - start
        if direction.length() == 0:
            return
        direction = direction.normalize()
        normal = pygame.Vector2(-direction.y, direction.x)
        head_len, head_w, shaft_w = 30, 26, 9
        shaft_end = end - direction * head_len
        shaft = [start + normal * shaft_w / 2, shaft_end + normal * shaft_w / 2,
                 shaft_end - normal * shaft_w / 2, start - normal * shaft_w / 2]
        head = [end, shaft_end + normal * head_w / 2, shaft_end - normal * head_w / 2]
        pygame.draw.polygon(surf, colour, shaft)
        pygame.draw.polygon(surf, colour, head)

    def _draw_board(self) -> None:
        # Squares are drawn on the same exact 100 px grid used by every overlay.
        for sq in chess.SQUARES:
            light = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1
            pygame.draw.rect(self.screen, LIGHT_SQ if light else DARK_SQ, self._square_rect(sq))

        overlay = pygame.Surface((BOARD_PX, BOARD_PX), pygame.SRCALPHA)
        if self.board.move_stack:
            last = self.board.peek()
            for sq in (last.from_square, last.to_square):
                overlay.fill(LAST_MOVE, self._square_rect(sq))
        if self.board.is_check():
            king = self.board.king(self.board.turn)
            if king is not None:
                overlay.fill(CHECK, self._square_rect(king))
        self.screen.blit(overlay, (0, 0))

        # coordinates in the corner of the edge squares, in the opposite square colour
        for i in range(8):
            file_sq = chess.square(7 - i if self.flipped else i, 7 if self.flipped else 0)
            rank_sq = chess.square(7 if self.flipped else 0, i if self.flipped else 7 - i)
            for sq, text, corner in ((file_sq, chess.FILE_NAMES[chess.square_file(file_sq)], "bottomright"),
                                     (rank_sq, chess.RANK_NAMES[chess.square_rank(rank_sq)], "topleft")):
                light = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1
                label = self.font_coord.render(text, True, DARK_SQ if light else LIGHT_SQ)
                rect = self._square_rect(sq).inflate(-8, -6)
                self.screen.blit(label, label.get_rect(**{corner: getattr(rect, corner)}))

        if self.selected is not None:
            pygame.draw.rect(self.screen, SELECTED, self._square_rect(self.selected), 4)

        for sq, piece in self.board.piece_map().items():
            self.screen.blit(self.pieces[piece.symbol()], self._square_xy(sq))

        marks = pygame.Surface((BOARD_PX, BOARD_PX), pygame.SRCALPHA)
        for move in self.targets:
            centre = self._square_rect(move.to_square).center
            if self.board.is_capture(move):
                pygame.draw.circle(marks, TARGET, centre, SQ // 2 - 3, 7)
            else:
                pygame.draw.circle(marks, TARGET, centre, 15)
        ply = len(self.board.move_stack) - 1
        if ply in self.ai_moves:
            self._draw_arrow(marks, self.board.peek(), AI_ARROW)
        if self.hint is not None:
            self._draw_arrow(marks, self.hint, HINT_ARROW)
        self.screen.blit(marks, (0, 0))

        for rect, move in self._promotion_rects():
            pygame.draw.rect(self.screen, (245, 245, 245), rect)
            pygame.draw.rect(self.screen, ACCENT, rect, 3)
            symbol = chess.piece_symbol(move.promotion)
            self.screen.blit(self.pieces[symbol.upper() if self.board.turn else symbol], rect.topleft)

        if self.outcome is not None:
            shade = pygame.Surface((BOARD_PX, BOARD_PX), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 150))
            self.screen.blit(shade, (0, 0))
            reason = self.outcome.termination.name.replace("_", " ").capitalize()
            winner = {chess.WHITE: "White wins", chess.BLACK: "Black wins", None: "Draw"}[self.outcome.winner]
            for i, (text, font) in enumerate(((reason, self.font_big), (winner, self.font_big),
                                              ("R restart   U undo   M menu", self.font))):
                surf = font.render(text, True, TEXT)
                self.screen.blit(surf, surf.get_rect(center=(BOARD_PX // 2, BOARD_PX // 2 - 70 + i * 70)))

    def _draw_eval_bar(self) -> None:
        bar = pygame.Rect(BOARD_PX, 0, BAR_W, HEIGHT)
        pygame.draw.rect(self.screen, (25, 25, 25), bar)
        white = 0.5 if self.eval_white is None else _white_fraction(self.eval_white)
        white_h = int(HEIGHT * white)
        # White's share grows from White's side of the board.
        white_rect = (pygame.Rect(BOARD_PX, 0, BAR_W, white_h) if self.flipped
                      else pygame.Rect(BOARD_PX, HEIGHT - white_h, BAR_W, white_h))
        pygame.draw.rect(self.screen, (235, 235, 235), white_rect)
        pygame.draw.line(self.screen, (120, 120, 120), (BOARD_PX, HEIGHT // 2), (BOARD_PX + BAR_W, HEIGHT // 2))
        if self.eval_white is not None:
            text = format_score(self.eval_white).replace("+", "")
            label = pygame.font.Font(None, 18).render(text, True, (120, 120, 120))
            white_bottom = not self.flipped
            y = HEIGHT - 12 if (self.eval_white >= 0) == white_bottom else 12
            self.screen.blit(label, label.get_rect(center=(BOARD_PX + BAR_W // 2, y)))

    def _text(self, text: str, x: int, y: int, font=None, colour=TEXT) -> int:
        font = font or self.font_small
        self.screen.blit(font.render(text, True, colour), (x, y))
        return y + font.get_linesize()

    def _wrapped(self, text: str, x: int, y: int, width: int, colour=MUTED) -> int:
        line = ""
        for word in text.split():
            candidate = f"{line} {word}".strip()
            if self.font_small.size(candidate)[0] > width and line:
                y = self._text(line, x, y, colour=colour)
                line = word
            else:
                line = candidate
        if line:
            y = self._text(line, x, y, colour=colour)
        return y

    def _draw_player(self, color: chess.Color, y: int) -> int:
        x = PANEL_X + 20
        agent = self.agents[color]
        key = self.choice[color]
        name = "Human" if agent is None else agent.name
        elo = self.elo_label(key, self.difficulty)
        to_move = self.board.turn == color and self.outcome is None
        marker = "> " if to_move else "   "
        title = f"{marker}{'White' if color else 'Black'}: {name}" + (f"  {elo}" if elo else "")
        y = self._text(title, x, y, self.font, ACCENT if to_move else TEXT)
        if to_move and (self.ai_busy or self.hint_busy):
            what = "hint" if self.hint_busy else "thinking"
            y = self._text(f"{what}... {time.perf_counter() - self.ai_started:.1f}s", x + 18, y, colour=MUTED)
        stats = self.stats[color]
        if agent is not None and stats is not None:
            lines = [
                f"move {stats.move}   depth {stats.depth}",
                f"nodes {stats.nodes:,}  ({stats.nps:,}/s)",
                f"time {stats.time:.2f}s   eval {format_score(stats.score)}",
            ]
            if stats.note:
                lines.append(stats.note)
            for line in lines:
                y = self._text(line, x + 18, y, colour=MUTED)
            if len(stats.pv) > 1:
                y = self._wrapped("line: " + " ".join(stats.pv), x + 18, y, PANEL_W - 50)
        return y + 12

    def _draw_panel(self) -> None:
        pygame.draw.rect(self.screen, PANEL_BG, pygame.Rect(PANEL_X, 0, PANEL_W, HEIGHT))
        x = PANEL_X + 20
        y = 18
        top, bottom = (chess.WHITE, chess.BLACK) if self.flipped else (chess.BLACK, chess.WHITE)
        y = self._draw_player(top, y)
        y = self._draw_player(bottom, y)
        y = self._text(f"Difficulty: {self.difficulty}", x, y, colour=MUTED) + 8

        y = self._text("Moves", x, y, self.font)
        pairs = [
            f"{i // 2 + 1}. {self.san_history[i]} {self.san_history[i + 1] if i + 1 < len(self.san_history) else ''}"
            for i in range(0, len(self.san_history), 2)
        ]
        max_rows = max(1, (HEIGHT - 76 - y) // self.font_small.get_linesize())
        shown = pairs[-2 * max_rows:]
        half = math.ceil(len(shown) / 2) if len(shown) > max_rows else len(shown)
        for i, line in enumerate(shown[:half]):  # two columns when the list gets long
            self._text(line, x, y + i * self.font_small.get_linesize())
            if half + i < len(shown):
                self._text(shown[half + i], x + 160, y + i * self.font_small.get_linesize())

        if self.error:
            self._text(f"AI error: {self.error[:36]}", x, HEIGHT - 58, colour=(240, 110, 110))
        self._text("H hint   U undo   R restart   M menu", x, HEIGHT - 30, colour=MUTED)

    # ------------------------------------------------------------- main loop
    def handle_key(self, key: int) -> bool:
        """Process a key press; returns False to quit."""
        if self.state == "menu":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start_game()
            elif key == pygame.K_ESCAPE:
                return False
            return True
        if key == pygame.K_u:
            self._undo()
        elif key == pygame.K_h:
            self._request_hint()
        elif key == pygame.K_r:
            self.start_game()
        elif key in (pygame.K_m, pygame.K_ESCAPE):
            self._close_agents()
            self.state = "menu"
        return True

    def frame(self) -> None:
        if self.state == "game":
            self._collect_results()
            self._maybe_start_ai()
            self._draw_board()
            self._draw_eval_bar()
            self._draw_panel()
        else:
            self._draw_menu()
        pygame.display.flip()

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == "menu":
                        self._menu_click(event.pos)
                    else:
                        self._human_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    running = self.handle_key(event.key)
            self.frame()
            self.clock.tick(FPS)

        self._close_agents()
        pygame.quit()


def main() -> None:
    ChessGUI().run()
