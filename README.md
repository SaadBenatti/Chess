# Chess AI

A chess game in Python where you can play against different AI search techniques, such as minimax, alpha-beta pruning, negamax and Monte Carlo tree search. You can also watch two AIs play each other, or play another person on the same computer.

## Running

```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

In the menu, pick a player for White and a player for Black (a human or one of the AIs), choose a difficulty, then click **Start**. When you play Black against an AI, the board is shown from Black's side.

| Key | Action |
| --- | --- |
| Click | Select a piece, then click a target square. For a promotion, click the piece you want. |
| U | Undo your last move, and the AI's reply to it |
| R | Restart with the same players |
| M / Esc | Back to the menu |

The difficulty sets how long each AI thinks per move: 0.5 s on Easy, 2 s on Medium, 5 s on Hard. The side panel shows each AI's last search: the depth it reached, the number of positions searched, the time it took, and its evaluation of the position from White's point of view.

## The AIs

| AI | Technique |
| --- | --- |
| Random | Plays a random legal move. Use it as a baseline. |
| Greedy | Looks one move ahead and takes whatever scores best right now. |
| Minimax | Textbook minimax with no pruning: White maximizes the score and Black minimizes it. |
| Alpha-Beta | Minimax plus alpha-beta pruning and captures-first move ordering. It gives the same result as minimax with far fewer positions searched. |
| Negamax | Alpha-beta in negamax form, plus quiescence search, a transposition table, killer moves and check extensions. This is the strongest search AI. |
| MCTS | Monte Carlo tree search (UCT) with short playouts that are scored by the evaluation function. |
| Stockfish | An optional external engine, shown only if Stockfish is installed. Set `STOCKFISH_PATH` or put `stockfish` on PATH. |

Every search AI gets the same thinking time and uses iterative deepening, so you can see the difference between the minimax variants in the panel. In about 2 seconds from the starting position, minimax reaches depth 3, alpha-beta depth 4 and negamax depth 5.

## Tests and AI-vs-AI matches

```
.venv\Scripts\python -m pytest
.venv\Scripts\python -m chess_ai.match negamax alphabeta -n 10 --time 1
```

The match runner plays games in pairs from the same random opening, with the colours swapped between the two games. It prints each result and why the game ended.
