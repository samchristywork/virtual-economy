![Banner](https://s-christy.com/sbs/status-banner.svg?icon=editor/candlestick_chart&hue=45&title=Virtual%20Economy&description=A%20multi-agent%20market%20simulation%20with%20competing%20trading%20strategies)

## Overview

Virtual Economy is a browser-based market simulation where autonomous agents
trade three commodities (FOOD, OIL, and WATER) using a variety of competing
strategies. The simulation runs entirely in JavaScript, with an optional Python
backend for persistence and multi-tab synchronization.

Agents are initialized with a cash balance and equal holdings of each asset.
Each iteration they apply their strategy: buying underpriced listings, posting
sell orders, hoarding a preferred asset, or reacting to price momentum, while a
0.5% transaction fee drains liquidity over time. Price history, trade volume,
and per-agent net worth are tracked across iterations and displayed as live
charts.

Shock events can be injected mid-simulation to stress-test how strategies
respond to sudden supply or demand shifts. Batch mode lets you run many trials
back-to-back and export the results as JSON for further analysis.

<p align="center">
  <img src="./assets/screenshot.png" />
</p>

## Features

## Strategies

## Usage

## Dependencies

## License

This work is licensed under the GNU General Public License version 3 (GPLv3).

[<img src="https://s-christy.com/status-banner-service/GPLv3_Logo.svg" width="150" />](https://www.gnu.org/licenses/gpl-3.0.en.html)
