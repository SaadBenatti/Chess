# Chess AI

A chess game in Python for playing against different AI search techniques, from plain minimax up to an enhanced negamax and Monte Carlo tree search. You can see how strong each one is: the menu shows an estimated Elo for every AI at every difficulty, and while it plays, the side panel shows its search depth, positions searched, evaluation and expected line.

You can also watch two AIs play each other, or play another person on the same computer.

## Running

```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

In the menu, pick a player for White and a player for Black (a human or any AI), choose a difficulty, then click **Start**. When you play Black against an AI, the board is shown from Black's side.

| Key | Action |
| --- | --- |
| Click | Select a piece, then click a target square. For a promotion, click the piece you want. |
| H | Hint: a 1-second negamax search draws its suggested move as a green arrow |
| U | Undo your last move, and the AI's reply to it |
| R | Restart with the same players |
| M / Esc | Back to the menu |

The difficulty sets how long each AI thinks per move: 0.5 s on Easy, 2 s on Medium, 5 s on Hard. Stockfish is the exception; it uses its own Elo limiter (1320 on Easy, 1800 on Medium, 2400 on Hard).

On the board, an orange arrow shows the AI's last move and the bar beside the board shows the latest evaluation. The side panel shows each AI's last search: the depth it reached, the positions searched (and searched per second), the time taken, the evaluation, and the line of play it expects (its principal variation).

## The AIs

| AI | Technique |
| --- | --- |
| Random | Plays a random legal move. |
| Greedy | Looks one move ahead and takes whatever scores best right now. |
| Minimax | Textbook minimax: White maximizes the score and Black minimizes it, and every move is searched. |
| Alpha-Beta | Minimax plus alpha-beta pruning and captures-first move ordering. It finds the same move as minimax but searches far fewer positions. |
| Negamax | Alpha-beta in negamax form with principal-variation search, aspiration windows, null-move pruning, late-move reductions, quiescence search, a transposition table, killer/history move ordering and check extensions. |
| MCTS | Monte Carlo tree search (UCT) with an MCTS-Solver that proves forced wins and losses, tree reuse between moves, mating moves expanded first, and short playouts scored by the evaluation. |
| Stockfish | The real engine, used as a reference opponent with a calibrated Elo. It's optional; see below. |

Every search AI uses the same evaluation function: tapered middlegame/endgame scoring with material, piece-square tables, passed/doubled/isolated pawns, the bishop pair, rooks on open files, mobility and a king pawn shield. Every AI also gets the same thinking time, so differences in strength come from the search itself. In 2 seconds from the starting position, minimax reaches depth 3, alpha-beta depth 4 and negamax depth 6.

There is no opening book and no endgame table. Every move is found by search.

## Elo ratings

| AI | Easy (0.5 s) | Medium (2 s) | Hard (5 s) |
| --- | --- | --- | --- |
| Random | ~100 | ~100 | ~100 |
| Greedy | 607 ± 160 | 607 ± 160 | 607 ± 160 |
| MCTS | 575 ± 150 | 976 ± 196 | ~1241 |
| Minimax | 1058 ± 132 | 1092 ± 134 | ~1114 |
| Alpha-Beta | 1327 ± 111 | 1502 ± 115 | ~1617 |
| Negamax | 1641 ± 140 | 1840 ± 126 | ~1971 |
| Stockfish (limited) | 1320 | 1800 | 2400 |

These come from 264 games played on 2026-11-06. The ± figures are 95% intervals, and ~ marks an extrapolated value. Random only played Greedy and lost every game, so its number is a rough floor, not a measurement.

What the table shows:
- Each search technique is clearly stronger than the one before it: Minimax → Alpha-Beta → Negamax.
- Pruning lets the same evaluation search deeper in the same time, and that's worth hundreds of Elo.
- Plain minimax barely gains from extra time, because its tree grows so fast that 4× the time doesn't buy another full ply.
- MCTS with random playouts is the weakest search in chess. That's a known result: MCTS shines when it has a learned evaluation, as in AlphaZero.

These ratings come from games against Stockfish limited with `UCI_Elo`, plus games between the AIs, fitted with a Bradley-Terry (Elo) model (`chess_ai/rating.py`). AIs too weak to score against Stockfish are rated by chaining through games against stronger AIs. Hard (marked ~) is extrapolated from the Elo gained between Easy and Medium per doubling of thinking time. The numbers are relative to Stockfish's fast-time-control calibration, so treat them as a yardstick, not official FIDE ratings.

To regenerate them (this takes a few hours of CPU time, and a run can be resumed):

```
.venv\Scripts\python -m chess_ai.rating run --workers 6
.venv\Scripts\python -m chess_ai.rating fit
```

## Stockfish (optional)

Download Stockfish from [stockfishchess.org](https://stockfishchess.org/download/) and extract it into `tools/` (which is gitignored), or set `STOCKFISH_PATH`. Without it, the Stockfish opponent is hidden and its test is skipped.

## Tests and AI-vs-AI matches

```
.venv\Scripts\python -m pytest
.venv\Scripts\python -m chess_ai.match negamax alphabeta -n 10 --time 1
```

The match runner plays games in pairs from the same random opening, with the colours swapped between the two games. It prints each result and why the game ended.
