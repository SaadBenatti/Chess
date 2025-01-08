# importing required librarys
import pygame
import chess
import math
import random
import numpy as np
from collections import defaultdict


#initialise display

# Set the size of the window to match the image size
X = 800
Y = 800
scrn = pygame.display.set_mode((X, Y))
pygame.init()
# Load the chessboard image directly with Pygame
chessboard_image = pygame.image.load('board.png')

#basic colours
WHITE = (255, 255, 255)
GREY = (128, 128, 128)
YELLOW = (204, 204, 0)
BLUE = (50, 255, 255)
BLACK = (0, 0, 0)

#initialise chess board
b = chess.Board()

#load piece images
pieces = {'p': pygame.image.load('b_pawn.png').convert_alpha(),
          'n': pygame.image.load('b_knight.png').convert_alpha(),
          'b': pygame.image.load('b_bishop.png').convert_alpha(),
          'r': pygame.image.load('b_rook.png').convert_alpha(),
          'q': pygame.image.load('b_queen.png').convert_alpha(),
          'k': pygame.image.load('b_king.png').convert_alpha(),
          'P': pygame.image.load('w_pawn.png').convert_alpha(),
          'N': pygame.image.load('w_knight.png').convert_alpha(),
          'B': pygame.image.load('w_bishop.png').convert_alpha(),
          'R': pygame.image.load('w_rook.png').convert_alpha(),
          'Q': pygame.image.load('w_queen.png').convert_alpha(),
          'K': pygame.image.load('w_king.png').convert_alpha(),
          
          }

def update(scrn, board, highlight_squares=[]):
    '''
    updates the screen basis the board class
    '''
    scrn.blit(chessboard_image, (0, 0))
    for i in range(64):
        piece = board.piece_at(i)
        if piece:
            scrn.blit(pieces[str(piece)], ((i % 8) * 100, 700 - (i // 8) * 100))
    for i in range(7):
        i += 1
        pygame.draw.line(scrn, WHITE, (0, i * 100), (800, i * 100))
        pygame.draw.line(scrn, WHITE, (i * 100, 0), (i * 100, 800))
    for square in highlight_squares:
        TX1 = 100 * (square % 8)
        TY1 = 100 * (7 - square // 8)
        pygame.draw.rect(scrn, BLUE, pygame.Rect(TX1, TY1, 100, 100), 5)
    pygame.display.flip()


def main(BOARD):
    '''
    for human vs human game
    '''
    scrn.fill(GREY)
    pygame.display.set_caption('Chess')
    index_moves = []
    status = True
    while status:
        update(scrn, BOARD, index_moves)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                status = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = pygame.mouse.get_pos()
                square = (math.floor(pos[0] / 100), math.floor(pos[1] / 100))
                index = (7 - square[1]) * 8 + square[0]
                if index in index_moves:
                    move = moves[index_moves.index(index)]
                    BOARD.push(move)
                    index_moves = []
                else:
                    piece = BOARD.piece_at(index)
                    if piece:
                        all_moves = list(BOARD.legal_moves)
                        moves = [m for m in all_moves if m.from_square == index]
                        index_moves = [m.to_square for m in moves]
        if BOARD.outcome():
            print(BOARD.outcome())
            status = False
            print(BOARD)
    pygame.quit()

def main_one_agent(BOARD, agent, agent_color):
    scrn.fill(BLACK)
    pygame.display.set_caption('Chess')
    index_moves = []
    status = True
    while status:
        update(scrn, BOARD, index_moves)
        if BOARD.turn == agent_color:
            BOARD.push(agent(BOARD))
            index_moves = []
        else:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    status = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    square = (math.floor(pos[0] / 100), math.floor(pos[1] / 100))
                    index = (7 - square[1]) * 8 + square[0]
                    if index in index_moves:
                        move = moves[index_moves.index(index)]
                        BOARD.push(move)
                        index_moves = []
                    else:
                        piece = BOARD.piece_at(index)
                        if piece:
                            all_moves = list(BOARD.legal_moves)
                            moves = [m for m in all_moves if m.from_square == index]
                            index_moves = [m.to_square for m in moves]
        if BOARD.outcome():
            print(BOARD.outcome())
            status = False
            print(BOARD)
    pygame.quit()

def main_two_agent(BOARD, agent1, agent_color1, agent2):
    scrn.fill(BLACK)
    pygame.display.set_caption('Chess')
    status = True
    while status:
        update(scrn, BOARD)
        if BOARD.turn == agent_color1:
            BOARD.push(agent1(BOARD))
        else:
            BOARD.push(agent2(BOARD))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                status = False
        if BOARD.outcome():
            print(BOARD.outcome())
            status = False
            print(BOARD)
    pygame.quit()
    
# Transposition table for caching evaluations
transposition_table = {}


def order_moves(board, moves):
    """
    Orders moves to improve alpha-beta pruning.
    Prioritize captures and checks.
    """
    def move_value(move):
        if board.is_capture(move):
            return 10  # High priority for captures
        if board.gives_check(move):
            return 5  # Medium priority for checks
        return 0  # Low priority otherwise

    return sorted(moves, key=move_value, reverse=True)

def minimax(board, depth, alpha, beta, maximizing_player):
    if depth == 0 or board.is_game_over():
        return enhanced_evaluate_board(board)
    
    legal_moves = order_moves(board, list(board.legal_moves))
    if maximizing_player:
        max_eval = float('-inf')
        for move in legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = float('inf')
        for move in legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha:
                break
        return min_eval
    
def enhanced_evaluate_board(board):
    """
    Improved evaluation function that considers positional and strategic factors.
    """
    if board.is_checkmate():
        return -9999 if board.turn else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    
    score = 0
    for square, piece in board.piece_map().items():
        value = piece_value[piece.symbol()]
        position_bonus = piece_square_tables[piece.symbol()][square]
        score += value + position_bonus
    return score

piece_value = {
    'p': 1, 'n': 3, 'b': 3.25, 'r': 5, 'q': 9, 'k': 0,
    'P': -1, 'N': -3, 'B': -3.25, 'R': -5, 'Q': -9, 'K': 0
}

piece_square_tables = {
    'P': [
        0, 0, 0, 0, 0, 0, 0, 0,
        5, 5, 5, 5, 5, 5, 5, 5,
        1, 1, 2, 3, 3, 2, 1, 1,
        0.5, 0.5, 1, 2.5, 2.5, 1, 0.5, 0.5,
        0, 0, 0, 2, 2, 0, 0, 0,
        0.5, -0.5, -1, 0, 0, -1, -0.5, 0.5,
        0.5, 1, 1, -2, -2, 1, 1, 0.5,
        0, 0, 0, 0, 0, 0, 0, 0
    ],
    'N': [
        -5, -4, -3, -3, -3, -3, -4, -5,
        -4, -2, 0, 0, 0, 0, -2, -4,
        -3, 0, 1, 1.5, 1.5, 1, 0, -3,
        -3, 0.5, 1.5, 2, 2, 1.5, 0.5, -3,
        -3, 0, 1.5, 2, 2, 1.5, 0, -3,
        -3, 0.5, 1, 1.5, 1.5, 1, 0.5, -3,
        -4, -2, 0, 0.5, 0.5, 0, -2, -4,
        -5, -4, -3, -3, -3, -3, -4, -5
    ],
    'B': [
        -2, -1, -1, -1, -1, -1, -1, -2,
        -1, 0, 0, 0, 0, 0, 0, -1,
        -1, 0, 0.5, 1, 1, 0.5, 0, -1,
        -1, 0.5, 0.5, 1, 1, 0.5, 0.5, -1,
        -1, 0, 1, 1, 1, 1, 0, -1,
        -1, 1, 1, 1, 1, 1, 1, -1,
        -1, 0.5, 0, 0, 0, 0, 0.5, -1,
        -2, -1, -1, -1, -1, -1, -1, -2
    ],
    'R': [
        0, 0, 0, 0, 0, 0, 0, 0,
        0.5, 1, 1, 1, 1, 1, 1, 0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        0, 0, 0, 0.5, 0.5, 0, 0, 0
    ],
    'Q': [
        -2, -1, -1, -0.5, -0.5, -1, -1, -2,
        -1, 0, 0, 0, 0, 0, 0, -1,
        -1, 0, 0.5, 0.5, 0.5, 0.5, 0, -1,
        -0.5, 0, 0.5, 0.5, 0.5, 0.5, 0, -0.5,
        0, 0, 0.5, 0.5, 0.5, 0.5, 0, -0.5,
        -1, 0.5, 0.5, 0.5, 0.5, 0.5, 0, -1,
        -1, 0, 0.5, 0, 0, 0, 0, -1,
        -2, -1, -1, -0.5, -0.5, -1, -1, -2
    ],
    'K': [
        -3, -4, -4, -5, -5, -4, -4, -3,
        -3, -4, -4, -5, -5, -4, -4, -3,
        -3, -4, -4, -5, -5, -4, -4, -3,
        -3, -4, -4, -5, -5, -4, -4, -3,
        -2, -3, -3, -4, -4, -3, -3, -2,
        -1, -2, -2, -2, -2, -2, -2, -1,
        2, 2, 0, 0, 0, 0, 2, 2,
        2, 3, 1, 0, 0, 1, 3, 2
    ],
    'p': [-x for x in reversed([
        0, 0, 0, 0, 0, 0, 0, 0,
        5, 5, 5, 5, 5, 5, 5, 5,
        1, 1, 2, 3, 3, 2, 1, 1,
        0.5, 0.5, 1, 2.5, 2.5, 1, 0.5, 0.5,
        0, 0, 0, 2, 2, 0, 0, 0,
        0.5, -0.5, -1, 0, 0, -1, -0.5, 0.5,
        0.5, 1, 1, -2, -2, 1, 1, 0.5,
        0, 0, 0, 0, 0, 0, 0, 0
    ])],
    'n': [-x for x in reversed([
        -5, -4, -3, -3, -3, -3, -4, -5,
        -4, -2, 0, 0, 0, 0, -2, -4,
        -3, 0, 1, 1.5, 1.5, 1, 0, -3,
        -3, 0.5, 1.5, 2, 2, 1.5, 0.5, -3,
        -3, 0, 1.5, 2, 2, 1.5, 0, -3,
        -3, 0.5, 1, 1.5, 1.5, 1, 0.5, -3,
        -4, -2, 0, 0.5, 0.5, 0, -2, -4,
        -5, -4, -3, -3, -3, -3, -4, -5
    ])],
    'b': [-x for x in reversed([
        -2, -1, -1, -1, -1, -1, -1, -2,
        -1, 0, 0, 0, 0, 0, 0, -1,
        -1, 0, 0.5, 1, 1, 0.5, 0, -1,
        -1, 0.5, 0.5, 1, 1, 0.5, 0.5, -1,
        -1, 0, 1, 1, 1, 1, 0, -1,
        -1, 1, 1, 1, 1, 1, 1, -1,
        -1, 0.5, 0, 0, 0, 0, 0.5, -1,
        -2, -1, -1, -1, -1, -1, -1, -2
    ])],
    'r': [-x for x in reversed([
        0, 0, 0, 0, 0, 0, 0, 0,
        0.5, 1, 1, 1, 1, 1, 1, 0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        -0.5, 0, 0, 0, 0, 0, 0, -0.5,
        0, 0, 0, 0.5, 0.5, 0, 0, 0
    ])],
    'q': [-x for x in reversed([
        -2, -1, -1, -0.5, -0.5, -1, -1, -2,
        -1, 0, 0, 0, 0, 0, 0, -1,
        -1, 0, 0.5, 0.5, 0.5, 0.5, 0, -1,
        -0.5, 0, 0.5, 0.5, 0.5, 0.5, 0, -0.5,
        0, 0, 0.5, 0.5, 0.5, 0.5, 0, -0.5,
        -1, 0.5, 0.5, 0.5, 0.5, 0.5, 0, -1,
        -1, 0, 0.5, 0, 0, 0, 0, -1,
        -2, -1, -1, -0.5, -0.5, -1, -1, -2
    ])],
    'k': [-x for x in reversed([
        -3, -4, -4, -5, -5, -4, -4, -3,
        -3, -4, -4, -5, -5, -4, -4, -3,
        -3, -4, -4, -5, -5, -4, -4, -3,
        -3, -4, -4, -5, -5, -4, -4, -3,
        -2, -3, -3, -4, -4, -3, -3, -2,
        -1, -2, -2, -2, -2, -2, -2, -1,
        2, 2, 0, 0, 0, 0, 2, 2,
        2, 3, 1, 0, 0, 1, 3, 2
    ])]
}


def minimax_agent(board):
    best_move = None
    best_value = float('-inf')
    alpha = float('-inf')
    beta = float('inf')
    for move in order_moves(board, list(board.legal_moves)):
        board.push(move)
        board_value = minimax(board, 3, alpha, beta, False)
        board.pop()
        if board_value > best_value:
            best_value = board_value
            best_move = move
    return best_move


class Node:
    def __init__(self, board, parent=None):
        self.board = board
        self.parent = parent
        self.children = []
        self.visits = 0
        self.wins = 0

def select(node, exploration_constant=1.41):
    """
    Selects the child node with the highest UCB1 value.
    """
    while node.children:
        node = max(node.children, key=lambda n: ucb1(n, node.visits, exploration_constant))
    return node

def ucb1(node, parent_visits, exploration_constant):
    """
    Calculates the Upper Confidence Bound (UCB1) score.
    """
    if node.visits == 0:
        return float('inf')
    exploitation = node.wins / node.visits
    exploration = exploration_constant * math.sqrt(math.log(parent_visits) / node.visits)
    return exploitation + exploration

def expand(node):
    """
    Expands the node by creating child nodes for all legal moves.
    """
    legal_moves = list(node.board.legal_moves)
    for move in legal_moves:
        new_board = node.board.copy()
        new_board.push(move)
        node.children.append(Node(new_board, node))

def simulate(board):
    """
    Simulates a game from the current board state using heuristic evaluation.
    """
    while not board.is_game_over():
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            break
        move = random.choice(legal_moves)
        board.push(move)
    
    if board.is_checkmate():
        return 1 if not board.turn else -1
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    return heuristic_evaluate_board(board)

def heuristic_evaluate_board(board):
    """
    Evaluates the board using a simple heuristic (material balance).
    """
    if board.is_checkmate():
        return 1 if not board.turn else -1
    elif board.is_stalemate() or board.is_insufficient_material():
        return 0
    return sum(piece_value[piece.symbol()] for piece in board.piece_map().values())

def backpropagate(node, result):
    """
    Propagates the result of a simulation back up the tree.
    """
    while node:
        node.visits += 1
        node.wins += result
        node = node.parent

def mcts(board, iterations, exploration_constant=1.41):
    """
    Performs Monte Carlo Tree Search on the given board state.
    """
    root = Node(board)
    for _ in range(iterations):
        # Selection
        node = select(root, exploration_constant)
        
        # Expansion
        if not node.board.is_game_over() and not node.children:
            expand(node)
        
        # Simulation
        if node.children:
            node = random.choice(node.children)
        result = simulate(node.board.copy())
        
        # Backpropagation
        backpropagate(node, result)
    
    # Return the move leading to the most visited child node
    best_child = max(root.children, key=lambda n: n.visits)
    return best_child.board.peek()

def mcts_agent(board):
    """
    MCTS agent wrapper for gameplay.
    """
    return mcts(board, iterations=1000, exploration_constant=1.41)
# Menu functions
def draw_menu(scrn):
    scrn.fill(BLACK)
    font = pygame.font.Font(None, 74)
    text1 = font.render('1. Minimax AI', True, WHITE)
    text2 = font.render('2. MCTS AI', True, WHITE)
    text3 = font.render('3. AI vs AI', True, WHITE)
    text4 = font.render('4. User vs User', True, WHITE)
    scrn.blit(text1, (200, 200))
    scrn.blit(text2, (200, 300))
    scrn.blit(text3, (200, 400))
    scrn.blit(text4, (200, 500))
    pygame.display.flip()

def main_menu():
    menu = True
    while menu:
        draw_menu(scrn)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_1:
                    return 'minimax'
                elif event.key == pygame.K_2:
                    return 'mcts'
                elif event.key == pygame.K_3:
                    return 'ai_vs_ai'
                elif event.key == pygame.K_4:
                    return 'user_vs_user'

if __name__ == "__main__":
    game_mode = main_menu()
    
    if game_mode == 'ai_vs_ai':
        main_two_agent(b, minimax_agent, True, mcts_agent)
    elif game_mode == 'user_vs_user':
        main(b)
    elif game_mode == 'minimax':
        main_one_agent(b, minimax_agent, False)
    elif game_mode == 'mcts':
        main_one_agent(b, mcts_agent, False)