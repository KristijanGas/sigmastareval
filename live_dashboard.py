import math
import sys
import time
from collections import deque

import pyqtgraph as pg
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication


class LiveDashboard:

    def __init__(self, data_provider, history=60000):
        self.data = data_provider
        self.history = history

        self.history_data = deque(maxlen=history)

    def _f(self, value):
        if value is None:
            return math.nan
        return float(value)

    def run(self):

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        win = pg.GraphicsLayoutWidget(title="Trading Dashboard")
        win.resize(1600, 900)

        #
        # Portfolio
        #

        portfolio = win.addPlot(title="Portfolio")
        portfolio.showGrid(x=True, y=True)
        portfolio.addLegend()

        up_shares_curve = portfolio.plot(
            pen=pg.mkPen('g', width=2),
            name="UP Shares"
        )

        down_shares_curve = portfolio.plot(
            pen=pg.mkPen('r', width=2),
            name="DOWN Shares"
        )

        cash_curve = portfolio.plot(
            pen=pg.mkPen('y', width=2),
            name="Cash"
        )

        net_curve = portfolio.plot(
            pen=pg.mkPen('w', width=3),
            name="Net Worth"
        )

        #
        # Crypto
        #

        win.nextRow()

        crypto_plot = win.addPlot(title="BTC - Strike")
        crypto_plot.showGrid(x=True, y=True)

        crypto_curve = crypto_plot.plot(
            pen=pg.mkPen('c', width=2)
        )

        crypto_plot.addLine(
            y=0,
            pen=pg.mkPen(
                'w',
                style=Qt.PenStyle.DashLine
            )
        )

        #
        # Market
        #

        win.nextRow()

        market = win.addPlot(title="Market vs Fair Value")

        market.showGrid(x=True, y=True)
        market.setYRange(0, 1)

        market.addLegend()

        up_curve = market.plot(
            pen=pg.mkPen('g', width=2),
            name="UP"
        )

        down_curve = market.plot(
            pen=pg.mkPen('r', width=2),
            name="DOWN"
        )

        up_fair_curve = market.plot(
            pen=pg.mkPen(
                'g',
                width=2,
                style=Qt.PenStyle.DashLine
            ),
            name="UP Fair"
        )

        down_fair_curve = market.plot(
            pen=pg.mkPen(
                'r',
                width=2,
                style=Qt.PenStyle.DashLine
            ),
            name="DOWN Fair"
        )

        timer = QTimer()

        def update():

            try:

                now = time.time()

                strike = self.data.get_price_to_beat()
                crypto = self.data.get_crypto_value()

                asset_ids = self.data.get_market_asset_ids()

                up_price = self.data.get_best_bid(asset_ids[0])
                down_price = self.data.get_best_bid(asset_ids[1])

                up_fair = self.data.get_fair_value_up()
                down_fair = self.data.get_fair_value_down()

                cash = self.data.get_user_cash()

                holdings = self.data.get_user_holdings()

                up_shares = holdings.get(asset_ids[0], 0)
                down_shares = holdings.get(asset_ids[1], 0)

                net = (
                    cash
                    + (0 if up_price is None else up_shares * up_price)
                    + (0 if down_price is None else down_shares * down_price)
                )

                self.history_data.append({

                    "time": now,

                    "crypto":
                        math.nan if strike is None
                        else crypto - strike,

                    "up":
                        self._f(up_price),

                    "down":
                        self._f(down_price),

                    "up_fair":
                        self._f(up_fair),

                    "down_fair":
                        self._f(down_fair),

                    "cash":
                        cash,

                    "net":
                        net,

                    "up_shares":
                        up_shares,

                    "down_shares":
                        down_shares,
                })

                if len(self.history_data) < 2:
                    return

                t0 = self.history_data[0]["time"]

                x = [
                    p["time"] - t0
                    for p in self.history_data
                ]

                up = [p["up"] for p in self.history_data]
                down = [p["down"] for p in self.history_data]

                up_fair = [p["up_fair"] for p in self.history_data]
                down_fair = [p["down_fair"] for p in self.history_data]

                crypto = [p["crypto"] for p in self.history_data]

                cash = [p["cash"] for p in self.history_data]
                net = [p["net"] for p in self.history_data]

                up_shares = [p["up_shares"] for p in self.history_data]
                down_shares = [p["down_shares"] for p in self.history_data]

                #
                # Portfolio
                #

                up_shares_curve.setData(x, up_shares)
                down_shares_curve.setData(x, down_shares)

                cash_curve.setData(x, cash)
                net_curve.setData(x, net)

                #
                # Crypto
                #

                crypto_curve.setData(x, crypto)

                #
                # Market
                #

                up_curve.setData(x, up)
                down_curve.setData(x, down)

                up_fair_curve.setData(x, up_fair)
                down_fair_curve.setData(x, down_fair)

            except Exception as e:
                print(e)

        timer.timeout.connect(update)
        timer.start(100)

        win.show()
        app.exec()