import pygame
import chess
import math

#initialise display
X = 800
Y = 800
scrn = pygame.display.set_mode((X, Y))
pygame.init()


#basic colours
WHITE = (255, 255, 255)
GREY = (128, 128, 128)
YELLOW = (204, 204, 0)
BLUE = (50, 255, 255)
BLACK = (0, 0, 0)

#initialise chess board
b = chess.Board()


#load piece images
pieces = {  'K' : pygame.image.load('images/wk.png').convert_alpha(),
            'k' : pygame.image.load('images/bk.png').convert_alpha(),
            'N' : pygame.image.load('images/wn.png').convert_alpha(),
            'n' : pygame.image.load('images/bn.png').convert_alpha(),
            'R' : pygame.image.load('images/wr.png').convert_alpha(),
            'r' : pygame.image.load('images/br.png').convert_alpha(),
            'Q' : pygame.image.load('images/wq.png').convert_alpha(),
            'q' : pygame.image.load('images/bq.png').convert_alpha(),
            'B' : pygame.image.load('images/wb.png').convert_alpha(),
            'b' : pygame.image.load('images/bb.png').convert_alpha(),
            'P' : pygame.image.load('images/wp.png').convert_alpha(),
            'p' : pygame.image.load('images/bp.png').convert_alpha()
         }



def update(scrn, board):
    '''
    updates the screen basis the board class
    '''

    for i in range(64):
        piece = board.piece_at(i)
        if piece == None:
            pass
        else:
            scrn.blit(pieces[str(piece)], ((i % 8) * 100, 700 - (i // 8) * 100))

    for i in range(7):
        i = i + 1
        pygame.draw.line(scrn, WHITE, (0, i * 100), (800, i * 100))
        pygame.draw.line(scrn, WHITE, (i * 100, 0), (i * 100, 800))

    pygame.display.flip()


def main(BOARD):
    '''
    for human vs human game
    '''
    # make background black
    scrn.fill(GREY)
    # name window
    pygame.display.set_caption('Chess')

    # variable to be used later
    index_moves = []

    status = True
    while (status):
        # update screen
        update(scrn, BOARD)

        for event in pygame.event.get():

            # if event object type is QUIT
            # then quitting the pygame
            # and program both.
            if event.type == pygame.QUIT:
                status = False

            # if mouse clicked
            if event.type == pygame.MOUSEBUTTONDOWN:
                # remove previous highlights
                scrn.fill(GREY)
                # get position of mouse
                pos = pygame.mouse.get_pos()

                # find which square was clicked and index of it
                square = (math.floor(pos[0] / 100), math.floor(pos[1] / 100))
                index = (7 - square[1]) * 8 + (square[0])

                # if we are moving a piece
                if index in index_moves:

                    move = moves[index_moves.index(index)]

                    BOARD.push(move)

                    # reset index and moves
                    index = None
                    index_moves = []


                # show possible moves
                else:
                    # check the square that is clicked
                    piece = BOARD.piece_at(index)
                    # if empty pass
                    if piece == None:

                        pass
                    else:

                        # figure out what moves this piece can make
                        all_moves = list(BOARD.legal_moves)
                        moves = []
                        for m in all_moves:
                            if m.from_square == index:
                                moves.append(m)

                                t = m.to_square

                                TX1 = 100 * (t % 8)
                                TY1 = 100 * (7 - t // 8)

                                # highlight squares it can move to
                                pygame.draw.rect(scrn, BLUE, pygame.Rect(TX1, TY1, 100, 100), 5)

                        index_moves = [a.to_square for a in moves]

        # deactivates the pygame library
        if BOARD.outcome() != None:
            print(BOARD.outcome())
            status = False
            print(BOARD)
    pygame.quit()


def main_one_agent(BOARD, agent, agent_color):
    '''
    for ai vs human game
    color is True = White ai
    color is False = Black ai
    '''

    # make background black
    scrn.fill(GREY)
    # name window
    pygame.display.set_caption('Chess')

    # variable to be used later
    index_moves = []

    status = True
    while (status):
        # update screen
        update(scrn, BOARD)

        if BOARD.turn == agent_color:
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
                    # reset previous screen from clicks
                    scrn.fill(BLACK)
                    # get position of mouse
                    pos = pygame.mouse.get_pos()

                    # find which square was clicked and index of it
                    square = (math.floor(pos[0] / 100), math.floor(pos[1] / 100))
                    index = (7 - square[1]) * 8 + (square[0])

                    # if we have already highlighted moves and are making a move
                    if index in index_moves:

                        move = moves[index_moves.index(index)]
                        # print(BOARD)
                        # print(move)
                        BOARD.push(move)
                        index = None
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

                                    TX1 = 100 * (t % 8)
                                    TY1 = 100 * (7 - t // 8)

                                    pygame.draw.rect(scrn, BLUE, pygame.Rect(TX1, TY1, 100, 100), 5)
                            # print(moves)
                            index_moves = [a.to_square for a in moves]

        # deactivates the pygame library
        if BOARD.outcome() != None:
            print(BOARD.outcome())
            status = False
            print(BOARD)
    pygame.quit()


def main_two_agent(BOARD, agent1, agent_color1, agent2):
    '''
    for ai vs ai game
    '''

    # make background black
    scrn.fill(GREY)
    # name window
    pygame.display.set_caption('Chess')

    # variable to be used later

    status = True
    while (status):
        # update screen
        update(scrn, BOARD)

        if BOARD.turn == agent_color1:
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


# ai= most_value_agent(b)

# main_one_agent(b,ai,False)