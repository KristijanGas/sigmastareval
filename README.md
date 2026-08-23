# Prediction market trading research and evaluation platform

## Overview

An event-driven Python platform built for Polymarket crypto prediction markets.\
The platform supports:

- Collecting crypto prices and L2 order-book data
- Backtesting and validating trading strategies on real historical data
- Prediction model training and evaluation
- Real time paper-trading with simulated delays
- Detailed backtest and paper-trading analysis

## Characteristics

- Average data snapshots per second: 40
- Replay speed relative to real time: 703.125x
- Time to backtest an hour of market data (single thread):
  - p50: 5.12 sec
  - p95: 7.3 sec
  - p99: 10.93 sec
- Average end-to-end processing latency in paper-trading:
  - p50: 30 μs
  - p95: 152 μs
  - p99: 787 μs

## Technical Characteristics

- Uses WebSocket connections to receive live order-book updates and collect market data
- Separates trading strategy logic, prediction models, market simulation, data providers, and evaluation into independent components
- Supports multiprocessing to evaluate bot performance across runs efficiently
- Replays timestamped market events in chronological order to prevent look-ahead bias
- Integrates scikit-learn models for machine-learning-based predictions
- Uses lock-free threaded concurrency to receive market data, update shared state, run strategy logic, and compute machine-learning predictions without blocking the live data-ingestion loop
- Provides an interactive Streamlit application for detailed trading-performance analysis and live paper-trading monitoring

### Data-flow diagram

![Data-flow diagram](https://raw.githubusercontent.com/KristijanGas/sigmastareval/refs/heads/main/docs/diagrams/data_flow_diagram.drawio.svg)

### Performance analysis preview

![Performance analysis screenshot](https://raw.githubusercontent.com/KristijanGas/sigmastareval/refs/heads/main/docs/screenshots/screenshot_preview.png)\
<i>Disclaimer: Shown results assume least restrictive constraints in the backtester (such as zero latency)</i>

## Installation and usage

**Step 0 (cloning the repo):**\
`$ git clone https://github.com/KristijanGas/sigmastareval.git`

**Step 1:**\
`$ python -m venv .venv`

**Step 2:**\
Windows PowerShell\
`$ .\.venv\Scripts\Activate.ps1`

Windows Command Prompt\
`$ .venv\Scripts\activate.bat`

macOS/Linux\
`$ source .venv/bin/activate`

**Step 3:**\
`$ python -m pip install -r requirements.txt`

**Step 4 (Running the application):**\
`$ python -m streamlit run streamlit-app.py`

**(Optional) Running replay engine:**

> Warning: Recommended minimum of 16GB RAM available before running

`$ python evaluator/replay_engine_master.py bot/k_strategy.py datasets/ethereum-up-or-down`

To see the results of backtesting, change the analysis directory to `tmp/ethereum-up-or-down`
