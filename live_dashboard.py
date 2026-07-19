import sys
import time
from collections import deque

import pyqtgraph as pg
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


class LiveDashboard:

    def __init__(self, data_provider, history=60000):

        self.data = data_provider
        self.history = history

        self.times = deque(maxlen=history)

        self.crypto = deque(maxlen=history)

        self.up = deque(maxlen=history)
        self.down = deque(maxlen=history)

        self.up_fair = deque(maxlen=history)
        self.down_fair = deque(maxlen=history)

        self.cash = deque(maxlen=history)
        self.net = deque(maxlen=history)

        self.up_shares = deque(maxlen=history)
        self.down_shares = deque(maxlen=history)

    def run(self):

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        win = pg.GraphicsLayoutWidget(
            title="Trading Dashboard"
        )
        win.resize(1400, 900)

        #
        # Portfolio
        #

        portfolio = win.addPlot(
            title="Portfolio"
        )

        portfolio.showGrid(x=True, y=True)
        portfolio.addLegend()

        up_shares_curve = portfolio.plot(
            pen='g',
            name="UP Shares"
        )

        down_shares_curve = portfolio.plot(
            pen='r',
            name="DOWN Shares"
        )

        cash_curve = portfolio.plot(
            pen='y',
            name="Cash"
        )

        net_curve = portfolio.plot(
            pen='w',
            name="Net Worth"
        )

        #
        # Crypto
        #

        win.nextRow()

        crypto_plot = win.addPlot(
            title="BTC - Price To Beat"
        )

        crypto_plot.showGrid(x=True, y=True)

        crypto_curve = crypto_plot.plot(
            pen='c'
        )

        crypto_plot.addLine(
            y=0,
            pen=pg.mkPen('w')
        )

        #
        # Market
        #

        win.nextRow()

        market = win.addPlot(
            title="YES / NO Prices"
        )

        market.showGrid(x=True, y=True)
        market.setYRange(0, 1)

        market.addLegend()

        up_curve = market.plot(
            pen='g',
            name="UP"
        )

        down_curve = market.plot(
            pen='r',
            name="DOWN"
        )

        up_fair_curve = market.plot(
            pen=pg.mkPen('g', style=pg.QtCore.Qt.PenStyle.DashLine),
            name="UP Fair Value"
        )

        down_fair_curve = market.plot(
            pen=pg.mkPen('r', style=pg.QtCore.Qt.PenStyle.DashLine),
            name="DOWN Fair Value"
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

                up_fair_value = self.data.get_fair_value_up()
                down_fair_value = self.data.get_fair_value_down()

                cash = self.data.get_user_cash()

                holdings = self.data.get_user_holdings()

                up_shares = holdings.get(asset_ids[0], 0)
                down_shares = holdings.get(asset_ids[1], 0)

                net = (
                    cash
                    + up_shares * up_price
                    + down_shares * down_price
                )

                self.times.append(now)

                self.crypto.append(
                    0 if strike is None else crypto - strike
                )
                if up_price is not None:
                    self.up.append(up_price)
                if down_price is not None:
                    self.down.append(down_price)

                self.cash.append(cash)
                self.net.append(net)

                self.up_shares.append(up_shares)
                self.down_shares.append(down_shares)
                if up_fair_value is not None and down_fair_value is not None:
                    self.up_fair.append(up_fair_value)
                    self.down_fair.append(down_fair_value)

                #
                # x axis
                #

                x = [t - self.times[0] for t in self.times]

                #
                # update plots
                #

                up_shares_curve.setData(
                    x,
                    list(self.up_shares)
                )

                down_shares_curve.setData(
                    x,
                    list(self.down_shares)
                )

                cash_curve.setData(
                    x,
                    list(self.cash)
                )

                net_curve.setData(
                    x,
                    list(self.net)
                )

                crypto_curve.setData(
                    x,
                    list(self.crypto)
                )

                up_curve.setData(
                    x,
                    list(self.up)
                )

                down_curve.setData(
                    x,
                    list(self.down)
                )

                up_fair_curve.setData(
                    x,
                    list(self.up_fair)
                )

                down_fair_curve.setData(
                    x,
                    list(self.down_fair)
                )

            except Exception as e:
                print(e)

        timer.timeout.connect(update)

        timer.start(100)

        win.show()

        app.exec()