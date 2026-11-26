# TFT Coach

A data-driven Teamfight Tactics analysis and coaching project.

## MVP scope

1. Collect official set metadata from Riot Data Dragon.
2. Store match and round observations in SQLite.
3. Score in-game decisions from round type, health, gold, level, board state, and opponent state.
4. Add live match observation and personalized coaching later.

## Data principles

- Official source data is collected explicitly and traceably.
- Community statistics are kept separate from official metadata.
- Recommendations use observed samples and must expose sample count and confidence.
- No strategy or statistic is presented as guaranteed.

## Run

```powershell
python -m tftcoach.cli collect --locale ko_KR
python -m tftcoach.cli recommend --stage 3-5 --health 42 --gold 35 --level 7
```
