# importing required librarys
import pygame
import chess
import math
import random


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

def update(scrn,board):
    '''
    updates the screen basis the board class
    '''
    # Blit the chessboard image
    scrn.blit(chessboard_image, (0, 0))

    for i in range(64):
        piece = board.piece_at(i)
        if piece == None:
            pass
        else:
            scrn.blit(pieces[str(piece)],((i%8)*100,700-(i//8)*100))
    
    for i in range(7):
        i=i+1
        pygame.draw.line(scrn,WHITE,(0,i*100),(800,i*100))
        pygame.draw.line(scrn,WHITE,(i*100,0),(i*100,800))

    pygame.display.flip()


def main(BOARD):

    '''
    for human vs human game
    '''
    #make background black
    scrn.fill(GREY)
    #name window
    pygame.display.set_caption('Chess')
    
    #variable to be used later
    index_moves = []

    status = True
    while (status):
        #update screen
        update(scrn,BOARD)

        for event in pygame.event.get():
     
            # if event object type is QUIT
            # then quitting the pygame
            # and program both.
            if event.type == pygame.QUIT:
                status = False

            # if mouse clicked
            if event.type == pygame.MOUSEBUTTONDOWN:
                #remove previous highlights
                scrn.fill(BLACK)
                #get position of mouse
                pos = pygame.mouse.get_pos()

                #find which square was clicked and index of it
                square = (math.floor(pos[0]/100),math.floor(pos[1]/100))
                index = (7-square[1])*8+(square[0])
                
                # if we are moving a piece
                if index in index_moves: 
                    
                    move = moves[index_moves.index(index)]
                    
                    BOARD.push(move)

                    #reset index and moves
                    index=None
                    index_moves = []
                    
                    
                # show possible moves
                else:
                    #check the square that is clicked
                    piece = BOARD.piece_at(index)
                    #if empty pass
                    if piece == None:
                        
                        pass
                    else:
                        
                        #figure out what moves this piece can make
                        all_moves = list(BOARD.legal_moves)
                        moves = []
                        for m in all_moves:
                            if m.from_square == index:
                    
                                moves.append(m)
                                t = m.to_square
                                TX1 = 100*(t%8)
                                TY1 = 100*(7-t//8)
                                #highlight squares it can move to
                                pygame.draw.rect(scrn,BLUE,pygame.Rect(TX1,TY1,100,100),5)
                        
                        index_moves = [a.to_square for a in moves]
     
    # deactivates the pygame library
        if BOARD.outcome() != None:
            print(BOARD.outcome())
            status = False
            print(BOARD)
    pygame.quit()

def main_one_agent(BOARD,agent,agent_color):
    
    '''
    for agent vs human game
    color is True = White agent
    color is False = Black agent
    '''
    
    #make background black
    scrn.fill(BLACK)
    #name window
    pygame.display.set_caption('Chess')
    
    #variable to be used later
    index_moves = []

    status = True
    while (status):
        #update screen
        update(scrn,BOARD)
        
     
        if BOARD.turn==agent_color:
            BOARD.push(agent(BOARD))
            scrn.fill(BLACK)

        else:

            for event in pygame.event.get():
         
                # if event object type is QUIT
                # then quitting the pygame
                # and program both.
                if event.type == pygame.QUIT:
                    status = False

                # if mouse clicked
                if event.type == pygame.MOUSEBUTTONDOWN:
                    #reset previous screen from clicks
                    scrn.fill(BLACK)
                    #get position of mouse
                    pos = pygame.mouse.get_pos()

                    #find which square was clicked and index of it
                    square = (math.floor(pos[0]/100),math.floor(pos[1]/100))
                    index = (7-square[1])*8+(square[0])
                    
                    # if we have already highlighted moves and are making a move
                    if index in index_moves: 
                        
                        move = moves[index_moves.index(index)]
                        #print(BOARD)
                        #print(move)
                        BOARD.push(move)
                        index=None
                        index_moves = []
                        
                    # show possible moves
                    else:
                        
                        piece = BOARD.piece_at(index)
                        
                        if piece == None:
                            
                            pass
                        else:

                            all_moves = list(BOARD.legal_moves)
                            moves = []
                            for m in all_moves:
                                if m.from_square == index:
                                    
                                    moves.append(m)

                                    t = m.to_square

                                    TX1 = 100*(t%8)
                                    TY1 = 100*(7-t//8)

                                    
                                    pygame.draw.rect(scrn,BLUE,pygame.Rect(TX1,TY1,100,100),5)
                            #print(moves)
                            index_moves = [a.to_square for a in moves]
     
    # deactivates the pygame library
        if BOARD.outcome() != None:
            print(BOARD.outcome())
            status = False
            print(BOARD)
    pygame.quit()

def main_two_agent(BOARD,agent1,agent_color1,agent2):
    '''
    for agent vs agent game
    
    '''
  
    #make background black
    scrn.fill(BLACK)
    #name window
    pygame.display.set_caption('Chess')
    
    #variable to be used later

    status = True
    while (status):
        #update screen
        update(scrn,BOARD)
        
        if BOARD.turn==agent_color1:
            BOARD.push(agent1(BOARD))

        else:
            BOARD.push(agent2(BOARD))

        scrn.fill(BLACK)
            
        for event in pygame.event.get():
     
            # if event object type is QUIT
            # then quitting the pygame
            # and program both.
            if event.type == pygame.QUIT:
                status = False
     
    # deactivates the pygame library
        if BOARD.outcome() != None:
            print(BOARD.outcome())
            status = False
            print(BOARD)
    pygame.quit()


def minimax(board, depth, alpha, beta, maximizing_player):
    if depth == 0 or board.is_game_over():
        return evaluate_board(board)

    legal_moves = list(board.legal_moves)
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

def evaluate_board(board):
    # Basic evaluation function
    if board.is_checkmate():
        if board.turn:
            return -9999
        else:
            return 9999
    elif board.is_stalemate():
        return 0
    elif board.is_insufficient_material():
        return 0
    else:
        return sum(piece_value[piece.symbol()] for piece in board.piece_map().values())

piece_value = {
    'p': -1, 'n': -3, 'b': -3, 'r': -5, 'q': -9, 'k': 0,
    'P': 1, 'N': 3, 'B': 3, 'R': 5, 'Q': 9, 'K': 0
}

def minimax_agent(board):
    best_move = None
    best_value = float('-inf')
    alpha = float('-inf')
    beta = float('inf')
    for move in board.legal_moves:
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

def select(node):
    while node.children:
        node = max(node.children, key=lambda n: ucb1(n, node.visits))
    return node

def ucb1(node, parent_visits):
    if node.visits == 0:
        return float('inf')
    return node.wins / node.visits + math.sqrt(2 * math.log(parent_visits) / node.visits)

def expand(node):
    legal_moves = list(node.board.legal_moves)
    for move in legal_moves:
        new_board = node.board.copy()
        new_board.push(move)
        node.children.append(Node(new_board, node))

def simulate(board):
    while not board.is_game_over():
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            break
        move = random.choice(legal_moves)
        board.push(move)
    if board.is_checkmate():
        return 1 if not board.turn else -1
    return 0

def backpropagate(node, result):
    while node:
        node.visits += 1
        node.wins += result
        node = node.parent

def mcts(board, iterations):
    root = Node(board)
    for _ in range(iterations):
        node = select(root)
        if not node.board.is_game_over():
            expand(node)
            node = random.choice(node.children)
        result = simulate(node.board.copy())
        backpropagate(node, result)
    return max(root.children, key=lambda n: n.visits).board.peek()

def mcts_agent(board):
    return mcts(board, 100)  # Adjust the number of iterations as needed
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