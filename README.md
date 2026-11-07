# Chess AI

A chess game in Python for playing against classic game-tree search algorithms, from plain minimax through alpha-beta and an enhanced negamax to Monte Carlo tree search. You can see how strong each one is: every AI has an estimated Elo rating, and while it plays, a side panel shows what it is thinking.

You can play against any AI, watch two AIs play each other, or play another person on the same computer.

## Getting started

You need Python 3.10 or newer.

```
git clone https://github.com/SaadBenatti/Chess.git
cd Chess
pip install -r requirements.txt
python main.py
```

## How to play

1. In the menu, choose a player for **White** and for **Black**: a human or any of the AIs.
2. Choose a **difficulty**, then click **Start**.
3. Click a piece to see its legal moves, then click the square to move it to. When a pawn promotes, choose the new piece from the picker.

If you play Black against an AI, the board turns so your pieces are at the bottom.

| Key | Action |
| --- | --- |
| H | Hint: draws a suggested move as a green arrow |
| U | Undo your last move (and the AI's reply) |
| R | Restart with the same players |
| M / Esc | Back to the menu |

**Difficulty** sets how long each AI thinks per move: 0.5 s on Easy, 2 s on Medium, 5 s on Hard. The Stockfish opponent uses its built-in strength limiter instead.

While an AI plays:
- An orange arrow marks its last move.
- The bar beside the board shows its evaluation.
- The side panel shows its search depth, positions searched, thinking time, evaluation, and the line of play it expects.

## The AIs

| AI | Technique |
| --- | --- |
| Random | Plays a random legal move. |
| Greedy | Looks one move ahead and takes whatever scores best right now. |
| Minimax | Textbook minimax: searches every move, with White maximizing the score and Black minimizing it. |
| Alpha-Beta | Minimax with alpha-beta pruning and captures-first move ordering. It finds the same moves as minimax while searching far fewer positions. |
| Negamax | Alpha-beta in negamax form, with principal-variation search, aspiration windows, null-move pruning, quiescence search, a transposition table, killer/history move ordering and check extensions. |
| MCTS | Monte Carlo tree search (UCT) with an MCTS-Solver that proves forced wins and losses, tree reuse between moves, and short playouts scored by the evaluation function. |
| Stockfish | Optional: the real engine, used as a reference opponent with a calibrated strength (see below). |

All the search AIs share one evaluation function. It scores material, piece placement, pawn structure (passed, doubled and isolated pawns), the bishop pair, rooks on open files, piece mobility and king safety, and it blends middlegame and endgame scoring as pieces come off the board.

Every AI also gets the same thinking time, so differences in strength come from the search algorithm itself. There is no opening book and no endgame table; every move is found by search.

## How strong are they?

Approximate Elo ratings by difficulty:

| AI | Easy | Medium | Hard |
| --- | --- | --- | --- |
| Random | ~100 | ~100 | ~100 |
| Greedy | ~600 | ~600 | ~600 |
| MCTS | ~575 | ~975 | ~1250 |
| Minimax | ~1050 | ~1100 | ~1100 |
| Alpha-Beta | ~1325 | ~1500 | ~1600 |
| Negamax | ~1650 | ~1850 | ~2000 |
| Stockfish (limited) | 1320 | 1800 | 2400 |

The ratings come from games against Stockfish, using its calibrated Elo limiter, and from games between the AIs, fitted with an Elo (Bradley-Terry) model. They're a yardstick for comparing the AIs, not official FIDE ratings, and the Hard ratings are less certain than the others.

What the ratings show:
- **Each step up the minimax family is worth hundreds of Elo.** Pruning and better move ordering let the same evaluation look much deeper in the same time.
- **Plain minimax barely improves with more time.** Its search tree grows so fast that even several times more time rarely buys another full move of depth.
- **MCTS is the weakest search here.** With random playouts it struggles in chess. MCTS is at its best with a learned evaluation, as in AlphaZero.

To regenerate the ratings (this takes a few hours, and an interrupted run resumes where it left off):

```
python -m chess_ai.rating run --workers 6
python -m chess_ai.rating run --workers 6 --schedule hard
python -m chess_ai.rating fit
```

## Stockfish (optional)

To play against Stockfish, or to regenerate the ratings, download it from [stockfishchess.org](https://stockfishchess.org/download/). Then either extract it into a `tools/` folder in the project, or set the `STOCKFISH_PATH` environment variable to the executable. Without Stockfish, everything else works and the Stockfish opponent is simply hidden.

## Development

```
python -m pytest                                         # run the tests
python -m chess_ai.match negamax alphabeta -n 10 --time 1   # AI-vs-AI match from the command line
```

Project layout:
- `chess_ai/agents/` holds one module per AI.
- `chess_ai/evaluation.py` is the shared evaluation function.
- `chess_ai/gui.py` is the Pygame interface.
- `chess_ai/rating.py` measures the Elo ratings.
