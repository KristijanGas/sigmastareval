from __future__ import annotations

from typing import Any, Sequence

import streamlit as st
from plotly.offline import get_plotlyjs


# Components v2 was introduced in Streamlit 1.51. The project already targets
# a newer Streamlit, but keeping the error explicit is nicer than failing with
# an AttributeError during page import.
if not hasattr(st.components, "v2"):
    raise RuntimeError(
        "The live passive dashboard requires Streamlit >= 1.51 for "
        "st.components.v2. Upgrade Streamlit before using this page."
    )


_COMPONENT_HTML = r"""
<div class="passive-live-dashboard">
  <div class="passive-chart" data-chart="portfolio"></div>
  <div class="passive-chart" data-chart="crypto"></div>
  <div class="passive-chart" data-chart="market"></div>
</div>
"""

_COMPONENT_CSS = r"""
.passive-live-dashboard {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
}

.passive-chart {
  width: 100%;
  height: 330px;
  min-height: 330px;
}
"""

# The Plotly bundle is obtained from the installed Python Plotly package, so
# the dashboard does not depend on a CDN or an additional npm build step.
# The component is registered once when this module is imported.
_COMPONENT_JS = get_plotlyjs() + r"""

export default function(component) {
  const { parentElement, data } = component;

  if (!window.Plotly) {
    throw new Error("Plotly failed to initialize inside the live dashboard component.");
  }

  const Plotly = window.Plotly;
  const portfolio = parentElement.querySelector('[data-chart="portfolio"]');
  const crypto = parentElement.querySelector('[data-chart="crypto"]');
  const market = parentElement.querySelector('[data-chart="market"]');

  if (!portfolio || !crypto || !market) {
    return;
  }

  // State lives on the DOM node instead of in this function's local scope.
  // Streamlit calls this renderer again when Python sends new data, while the
  // DOM/component instance remains mounted. Keeping state here lets us append
  // points without recreating the Plotly figures.
  const state = parentElement.__passivePlotState || {
    initialized: false,
    sessionId: null,
    updateChain: Promise.resolve(),
    resizeObserver: null,
  };
  parentElement.__passivePlotState = state;

  const config = {
    responsive: true,
    scrollZoom: true,
    displaylogo: false,
  };

  function baseLayout(title, yTitle = null) {
    return {
      title: { text: title },
      height: 330,
      margin: { l: 55, r: 20, t: 50, b: 45 },
      hovermode: "x unified",
      xaxis: { title: { text: "Minutes since session start" }, autorange: true },
      yaxis: yTitle ? { title: { text: yTitle }, autorange: true } : { autorange: true },
      legend: { orientation: "h" },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: "var(--st-text-color, currentColor)" },
    };
  }

  function captureView(gd) {
    if (!gd || !gd._fullLayout) return null;
    const xaxis = gd._fullLayout.xaxis;
    const yaxis = gd._fullLayout.yaxis;
    return {
      xAutorange: xaxis ? xaxis.autorange : true,
      xRange: xaxis && xaxis.range ? Array.from(xaxis.range) : null,
      yAutorange: yaxis ? yaxis.autorange : true,
      yRange: yaxis && yaxis.range ? Array.from(yaxis.range) : null,
    };
  }

  async function restoreView(gd, view) {
    if (!view) return;
    const update = {};

    // Only restore ranges that the user explicitly zoomed/panned. If an axis
    // was still on autorange, leave it on autorange so new live points remain
    // visible automatically.
    if (view.xAutorange === false && view.xRange) {
      update["xaxis.autorange"] = false;
      update["xaxis.range"] = view.xRange;
    }
    if (view.yAutorange === false && view.yRange) {
      update["yaxis.autorange"] = false;
      update["yaxis.range"] = view.yRange;
    }

    if (Object.keys(update).length) {
      await Plotly.relayout(gd, update);
    }
  }

  function portfolioTraces(payload) {
    return [
      { x: payload.x, y: payload.up_shares, type: "scattergl", mode: "lines", name: "UP Shares", uid: "up-shares" },
      { x: payload.x, y: payload.down_shares, type: "scattergl", mode: "lines", name: "DOWN Shares", uid: "down-shares" },
      { x: payload.x, y: payload.cash, type: "scattergl", mode: "lines", name: "Cash", uid: "cash" },
      { x: payload.x, y: payload.net, type: "scattergl", mode: "lines", name: "Net Worth", uid: "net" },
    ];
  }

  function cryptoTraces(payload) {
    return [
      { x: payload.x, y: payload.crypto, type: "scattergl", mode: "lines", name: "Crypto - Strike", uid: "crypto" },
      { x: payload.x, y: payload.crypto_mean, type: "scattergl", mode: "lines", name: "Moving mean - Strike", uid: "crypto-mean" },
    ];
  }

  function marketTraces(payload) {
    return [
      { x: payload.x, y: payload.up, type: "scattergl", mode: "lines", name: "UP", uid: "up" },
      { x: payload.x, y: payload.down, type: "scattergl", mode: "lines", name: "DOWN", uid: "down" },
      { x: payload.x, y: payload.up_fair, type: "scattergl", mode: "lines", name: "UP Fair", uid: "up-fair", line: { dash: "dash" } },
      { x: payload.x, y: payload.down_fair, type: "scattergl", mode: "lines", name: "DOWN Fair", uid: "down-fair", line: { dash: "dash" } },
    ];
  }

  async function replacePlots(payload, preserveView) {
    const oldViews = preserveView ? {
      portfolio: captureView(portfolio),
      crypto: captureView(crypto),
      market: captureView(market),
    } : null;

    const marketLayout = baseLayout("Market vs Fair Value");
    marketLayout.yaxis = { range: [0, 1], autorange: false };

    await Promise.all([
      Plotly.react(portfolio, portfolioTraces(payload), baseLayout("Portfolio"), config),
      Plotly.react(crypto, cryptoTraces(payload), baseLayout(`${data.market_binance} - Strike`), config),
      Plotly.react(market, marketTraces(payload), marketLayout, config),
    ]);

    if (oldViews) {
      await Promise.all([
        restoreView(portfolio, oldViews.portfolio),
        restoreView(crypto, oldViews.crypto),
        restoreView(market, oldViews.market),
      ]);
    }
  }

  async function appendPoints(payload) {
    if (!payload.x || payload.x.length === 0) return;

    await Promise.all([
      Plotly.extendTraces(
        portfolio,
        {
          x: [payload.x, payload.x, payload.x, payload.x],
          y: [payload.up_shares, payload.down_shares, payload.cash, payload.net],
        },
        [0, 1, 2, 3]
      ),
      Plotly.extendTraces(
        crypto,
        {
          x: [payload.x, payload.x],
          y: [payload.crypto, payload.crypto_mean],
        },
        [0, 1]
      ),
      Plotly.extendTraces(
        market,
        {
          x: [payload.x, payload.x, payload.x, payload.x],
          y: [payload.up, payload.down, payload.up_fair, payload.down_fair],
        },
        [0, 1, 2, 3]
      ),
    ]);
  }

  // Serialize updates. Fragment reruns can arrive before a previous WebGL
  // operation has finished; overlapping Plotly operations are a common source
  // of unstable rendering and context-loss symptoms.
  state.updateChain = state.updateChain
    .catch(() => undefined)
    .then(async () => {
      const newSession = state.sessionId !== data.session_id;
      const mustReplace = !state.initialized || newSession || data.reset === true;

      if (mustReplace) {
        await replacePlots(data.points, state.initialized && !newSession);
        state.initialized = true;
        state.sessionId = data.session_id;
      } else {
        await appendPoints(data.points);
      }
    })
    .catch((error) => {
      console.error("Passive live Plotly update failed", error);
    });

  if (!state.resizeObserver && typeof ResizeObserver !== "undefined") {
    state.resizeObserver = new ResizeObserver(() => {
      if (!state.initialized) return;
      Plotly.Plots.resize(portfolio);
      Plotly.Plots.resize(crypto);
      Plotly.Plots.resize(market);
    });
    state.resizeObserver.observe(parentElement);
  }

  return () => {
    if (state.resizeObserver) {
      state.resizeObserver.disconnect();
      state.resizeObserver = null;
    }
    for (const gd of [portfolio, crypto, market]) {
      try {
        Plotly.purge(gd);
      } catch (_) {
        // Best-effort cleanup when the page/component is unmounted.
      }
    }
    parentElement.__passivePlotState = undefined;
  };
}
"""


_live_plot_component = st.components.v2.component(
    name="passive_live_plotly",
    html=_COMPONENT_HTML,
    css=_COMPONENT_CSS,
    js=_COMPONENT_JS,
    isolate_styles=False,
)


_NUMERIC_COLUMNS = (
    "crypto",
    "crypto_mean",
    "up",
    "down",
    "up_fair",
    "down_fair",
    "cash",
    "net",
    "up_shares",
    "down_shares",
)


def build_points_payload(rows: Sequence[dict[str, Any]], started_at: float) -> dict[str, list[Any]]:
    """Convert sample rows to compact column-oriented component data."""
    payload: dict[str, list[Any]] = {
        "x": [],
        **{column: [] for column in _NUMERIC_COLUMNS},
    }

    for row in rows:
        timestamp = row.get("timestamp")
        if timestamp is None:
            continue
        payload["x"].append((float(timestamp) - started_at) / 60.0)
        for column in _NUMERIC_COLUMNS:
            payload[column].append(row.get(column))

    return payload


def render_live_plots(
    *,
    session_id: int,
    market_binance: str,
    rows: Sequence[dict[str, Any]],
    started_at: float,
    reset: bool,
) -> None:
    """Mount/update persistent Plotly charts.

    On the initial render (or an occasional downsampling-step change), ``reset``
    sends a full plotted snapshot. Normal one-second refreshes send only new
    rows, and the frontend calls ``Plotly.extendTraces`` so zoom/pan state and
    the existing WebGL canvases are retained.
    """
    _live_plot_component(
        data={
            "session_id": int(session_id),
            "market_binance": market_binance,
            "reset": bool(reset),
            "points": build_points_payload(rows, started_at),
        },
        key=f"passive-live-plots-{session_id}",
        width="stretch",
        height=1030,
    )