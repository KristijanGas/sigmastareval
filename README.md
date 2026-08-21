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
- Average time to backtest an hour of market data (single thread): 5.12 seconds
- Replay speed relative to real time: 703.125x
- Average end-to-end processing latency in paper-trading: 16 μs

## Technical Characteristics

- Uses WebSocket connection for order-book updates and data gathering
- Separate strategy logic, prediction models, market simulation, data providers and evaluation
- Multiprocess bot performance evaluation
- Replays timestamped market events in chronological order avoiding lookahead bias
- sklearn
- Uses interactive Streamlit app with detailed trading performance analysis and live dashboard
