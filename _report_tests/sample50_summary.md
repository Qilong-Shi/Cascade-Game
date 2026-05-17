# 50-sample local opponent test summary

Planned games: 50

| Test Setting | Games Played | Agent as Red | Agent as Blue | Win Rate | Notes |
|---|---:|---:|---:|---:|---|
| Versus random baseline | 24 | 12/12 | 12/12 | 100% | Tests robustness against seeded random legal play; average game runtime 2.2s |
| Versus greedy baseline | 14 | 7/7 | 7/7 | 100% | Tests tactical strength against one-step evaluation; average game runtime 2.3s |
| Self-play against earlier version | 12 | 6/6 | 6/6 | 100% | Compares against the depth-3 earlier variant; average game runtime 5.8s |

Total local opponent games: 50
Overall local win rate: 50/50 (100%)
Average runtime across all games: 3.1s
