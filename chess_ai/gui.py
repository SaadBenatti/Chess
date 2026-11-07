"""Pygame front end: menu, board, side panel with live search statistics.

AI players think on a background thread so the window stays responsive. Only
one AI thread runs at a time; results are tagged with a "generation" number
so a move computed before an undo/restart is discarded.
"""
from __future__ import annotations

import queue
import threading
import time
import traceback
from pathlib import Path

import chess
import pygame

from .agents import AGENTS, DIFFICULTIES, Agent, SearchStats, available_agents, create_agent
from .evaluation import format_score

SQ = 100
BOARD_PX = 8 * SQ
PANEL_W = 340
WIDTH, HEIGHT = BOARD_PX + PANEL_W, BOARD_PX
FPS = 60
ASSETS = Path(__file__).resolve().parent.parent / "assets"

# colours
BG = (30, 32, 36)
PANEL_BG = (40, 43, 48)
TEXT = (230, 230, 230)
MUTED = (150, 155, 165)
ACCENT = (70, 140, 230)
BUTTON = (60, 64, 72)
BUTTON_SEL = (70, 140, 230)
LAST_MOVE = (230, 200, 40, 110)
CHECK = (220, 40, 40, 140)
SELECTED = (50, 160, 255)
TARGET = (40, 40, 40, 90)
LABEL = (90, 90, 90)

PROMOTION_ORDER = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
HUMAN = "human"


def _player_name(key: str) -> str:
    return "Human" if key == HUMAN else AGENTS[key][0]


class Button:
    def __init__(self, rect: pygame.Rect, label: str, value: str) -> None:
        self.rect = rect
        self.label = label
        self.value = value

    def draw(self, surf: pygame.Surface, font: pygame.font.Font, selected: bool) -> None:
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        colour = BUTTON_SEL if selected else (tuple(min(c + 15, 255) for c in BUTTON) if hover else BUTTON)
        pygame.draw.rect(surf, colour, self.rect, border_radius=8)
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
        self.board_img = pygame.image.load(ASSETS / "board.png").convert()
        self.pieces = {}
        for symbol in "pnbrqkPNBRQK":
            prefix = "w" if symbol.isupper() else "b"
            name = chess.piece_name(chess.Piece.from_symbol(symbol).piece_type)
            self.pieces[symbol] = pygame.image.load(ASSETS / f"{prefix}_{name}.png").convert_alpha()

        # menu choices
        self.choice = {chess.WHITE: HUMAN, chess.BLACK: "negamax"}
        self.difficulty = "Medium"
        self.state = "menu"
        self._build_menu()

        # game state (set by start_game)
        self.board = chess.Board()
        self.agents: dict[chess.Color, Agent | None] = {chess.WHITE: None, chess.BLACK: None}
        self.stats: dict[chess.Color, SearchStats | None] = {chess.WHITE: None, chess.BLACK: None}
        self.flipped = False
        self.selected: chess.Square | None = None
        self.targets: list[chess.Move] = []
        self.promotion: list[chess.Move] = []
        self.outcome: chess.Outcome | None = None
        self.san_history: list[str] = []
        self.error = ""

        # AI thread bookkeeping
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
        for color, x in ((chess.WHITE, WIDTH // 2 - 330), (chess.BLACK, WIDTH // 2 + 30)):
            for i, key in enumerate(options):
                rect = pygame.Rect(x, 170 + i * 52, 300, 44)
                self.menu_buttons.append((color, Button(rect, _player_name(key), key)))
        self.diff_buttons = []
        for i, name in enumerate(DIFFICULTIES):
            rect = pygame.Rect(WIDTH // 2 - 255 + i * 175, 640, 160, 44)
            self.diff_buttons.append(Button(rect, name, name))
        self.start_button = Button(pygame.Rect(WIDTH // 2 - 120, 715, 240, 54), "Start", "start")

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
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 60)))
        sub = self.font_small.render("Pick a player for each side, a difficulty (thinking time), then Start.", True, MUTED)
        self.screen.blit(sub, sub.get_rect(center=(WIDTH // 2, 105)))
        for color, x in ((chess.WHITE, WIDTH // 2 - 330), (chess.BLACK, WIDTH // 2 + 30)):
            head = self.font.render("White" if color else "Black", True, TEXT)
            self.screen.blit(head, head.get_rect(center=(x + 150, 145)))
        for color, button in self.menu_buttons:
            button.draw(self.screen, self.font, self.choice[color] == button.value)
        label = self.font_small.render("Difficulty", True, MUTED)
        self.screen.blit(label, label.get_rect(center=(WIDTH // 2, 620)))
        for button in self.diff_buttons:
            button.draw(self.screen, self.font, self.difficulty == button.value)
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
        time_limit, skill = DIFFICULTIES[self.difficulty]
        for color in chess.COLORS:
            key = self.choice[color]
            self.agents[color] = None if key == HUMAN else create_agent(key, time_limit=time_limit, skill_level=skill)
        self.board = chess.Board()
        self.stats = {chess.WHITE: None, chess.BLACK: None}
        # Show the board from the human's side; White's side otherwise.
        self.flipped = self.agents[chess.WHITE] is not None and self.agents[chess.BLACK] is None
        self.error = ""
        self._after_board_change()
        self.state = "game"

    def _after_board_change(self) -> None:
        self.selected = None
        self.targets = []
        self.promotion = []
        self.outcome = self.board.outcome(claim_draw=True)
        replay = chess.Board()
        self.san_history = []
        for move in self.board.move_stack:
            self.san_history.append(replay.san(move))
            replay.push(move)

    def _push(self, move: chess.Move) -> None:
        self.board.push(move)
        self._after_board_change()

    # ------------------------------------------------------------- AI thread
    def _cancel_ai(self) -> None:
        """Invalidate any running search; its result will be ignored."""
        self.generation += 1
        self.ai_stop.set()
        self.ai_busy = False

    def _maybe_start_ai(self) -> None:
        if self.state != "game" or self.outcome is not None or self.ai_busy:
            return
        agent = self.agents[self.board.turn]
        if agent is None:
            return
        if self.ai_thread is not None and self.ai_thread.is_alive():
            return  # previous (cancelled) search still unwinding
        self.ai_stop = threading.Event()
        gen, stop, board = self.generation, self.ai_stop, self.board.copy()

        def work() -> None:
            try:
                move = agent.choose_move(board, stop)
                self.results.put((gen, move, agent.last_stats, None))
            except Exception:  # surface errors in the panel instead of killing the thread silently
                self.results.put((gen, None, None, traceback.format_exc()))

        self.ai_busy = True
        self.ai_started = time.perf_counter()
        self.ai_thread = threading.Thread(target=work, daemon=True)
        self.ai_thread.start()

    def _collect_ai_result(self) -> None:
        while not self.results.empty():
            gen, move, stats, err = self.results.get()
            if gen != self.generation:
                continue
            self.ai_busy = False
            if err:
                print(err)
                self.error = err.strip().splitlines()[-1]
                continue
            if move is not None and move in self.board.legal_moves:
                self.stats[self.board.turn] = stats
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
    def _draw_board(self) -> None:
        self.screen.blit(self.board_img, (0, 0))
        overlay = pygame.Surface((BOARD_PX, BOARD_PX), pygame.SRCALPHA)
        if self.board.move_stack:
            last = self.board.peek()
            for sq in (last.from_square, last.to_square):
                overlay.fill(LAST_MOVE, pygame.Rect(*self._square_xy(sq), SQ, SQ))
        if self.board.is_check():
            king = self.board.king(self.board.turn)
            if king is not None:
                overlay.fill(CHECK, pygame.Rect(*self._square_xy(king), SQ, SQ))
        self.screen.blit(overlay, (0, 0))

        for sq, piece in self.board.piece_map().items():
            self.screen.blit(self.pieces[piece.symbol()], self._square_xy(sq))

        # coordinates on the edge squares
        for i in range(8):
            file_char = chess.FILE_NAMES[7 - i if self.flipped else i]
            rank_char = chess.RANK_NAMES[i if self.flipped else 7 - i]
            self.screen.blit(self.font_small.render(file_char, True, LABEL), (i * SQ + SQ - 14, BOARD_PX - 20))
            self.screen.blit(self.font_small.render(rank_char, True, LABEL), (6, i * SQ + 6))

        if self.selected is not None:
            pygame.draw.rect(self.screen, SELECTED, pygame.Rect(*self._square_xy(self.selected), SQ, SQ), 5)
        dots = pygame.Surface((BOARD_PX, BOARD_PX), pygame.SRCALPHA)
        for move in self.targets:
            x, y = self._square_xy(move.to_square)
            centre = (x + SQ // 2, y + SQ // 2)
            if self.board.is_capture(move):
                pygame.draw.circle(dots, TARGET, centre, SQ // 2 - 4, 7)
            else:
                pygame.draw.circle(dots, TARGET, centre, 14)
        self.screen.blit(dots, (0, 0))

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

    def _text(self, text: str, x: int, y: int, font=None, colour=TEXT) -> int:
        font = font or self.font_small
        self.screen.blit(font.render(text, True, colour), (x, y))
        return y + font.get_linesize()

    def _draw_player(self, color: chess.Color, y: int) -> int:
        x = BOARD_PX + 20
        agent = self.agents[color]
        name = "Human" if agent is None else agent.name
        to_move = self.board.turn == color and self.outcome is None
        marker = "> " if to_move else "   "
        y = self._text(f"{marker}{'White' if color else 'Black'}: {name}", x, y, self.font, ACCENT if to_move else TEXT)
        if to_move and agent is not None and self.ai_busy:
            y = self._text(f"thinking... {time.perf_counter() - self.ai_started:.1f}s", x + 18, y, colour=MUTED)
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
        return y + 14

    def _draw_panel(self) -> None:
        pygame.draw.rect(self.screen, PANEL_BG, pygame.Rect(BOARD_PX, 0, PANEL_W, HEIGHT))
        x = BOARD_PX + 20
        y = 20
        top, bottom = (chess.BLACK, chess.WHITE) if not self.flipped else (chess.WHITE, chess.BLACK)
        y = self._draw_player(top, y)
        y = self._draw_player(bottom, y)
        y = self._text(f"Difficulty: {self.difficulty}", x, y, colour=MUTED) + 10

        y = self._text("Moves", x, y, self.font)
        pairs = [
            f"{i // 2 + 1}. {self.san_history[i]} {self.san_history[i + 1] if i + 1 < len(self.san_history) else ''}"
            for i in range(0, len(self.san_history), 2)
        ]
        max_rows = max(1, (HEIGHT - 70 - y) // self.font_small.get_linesize())
        for line in pairs[-max_rows:]:
            y = self._text(line, x, y)

        if self.error:
            self._text(f"AI error: {self.error[:34]}", x, HEIGHT - 60, colour=(240, 110, 110))
        self._text("U undo   R restart   M menu", x, HEIGHT - 32, colour=MUTED)

    # ------------------------------------------------------------- main loop
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
                    if self.state == "menu":
                        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            self.start_game()
                        elif event.key == pygame.K_ESCAPE:
                            running = False
                    else:
                        if event.key == pygame.K_u:
                            self._undo()
                        elif event.key == pygame.K_r:
                            self.start_game()
                        elif event.key in (pygame.K_m, pygame.K_ESCAPE):
                            self._close_agents()
                            self.state = "menu"

            if self.state == "game":
                self._collect_ai_result()
                self._maybe_start_ai()
                self._draw_board()
                self._draw_panel()
            else:
                self._draw_menu()
            pygame.display.flip()
            self.clock.tick(FPS)

        self._close_agents()
        pygame.quit()


def main() -> None:
    ChessGUI().run()
