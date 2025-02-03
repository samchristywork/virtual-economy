const ASSETS = ['FOOD', 'OIL', 'WATER'];
const TRADE_FEE = 0.005;

const DEFAULT_AGENTS = [
  { name: 'Alice', strategy: 'chaos' },
  { name: 'Bob', strategy: 'flipper' },
  { name: 'Charlie', strategy: 'hoarder' },
  { name: 'Diana', strategy: 'sniper' },
  { name: 'Eve', strategy: 'undercut' },
  { name: 'Frank', strategy: 'value-investor' },
  { name: 'Grace', strategy: 'momentum' },
];

const AGENT_COLORS = {
  Alice:   '#ef4444',
  Bob:     '#3b82f6',
  Charlie: '#22c55e',
  Diana:   '#a855f7',
  Eve:     '#f97316',
  Frank:   '#14b8a6',
  Grace:   '#eab308',
};

const ASSET_COLORS = { FOOD: '#22c55e', OIL: '#f97316', WATER: '#3b82f6' };

let state;

function createState() {
  return {
    users: new Map(),       // name -> { balance }
    holdings: new Map(),    // name -> Map(asset -> qty)
    listings: [],           // { id, seller, asset, quantity, price_per_share }
    transactions: [],       // { buyer, seller, asset, qty, price, total, fee }
    priceHistory: [],       // { iteration, asset, avg_price }
    nwHistory: [],          // { iteration, name, nw }
    nextId: 1,
    lastSnapshotTxIdx: 0,
  };
}

function resetState(agents) {
  state = createState();
  for (const a of agents) {
    state.users.set(a.name, { balance: 1000 });
    state.holdings.set(a.name, new Map([['FOOD', 50], ['OIL', 50], ['WATER', 50]]));
  }
}

function getBalance(name)          { return state.users.get(name)?.balance ?? 0; }
function getHolding(name, asset)   { return state.holdings.get(name)?.get(asset) ?? 0; }

function othersListings(name) {
  return state.listings.filter(l => l.seller !== name);
}

function createListing(seller, asset, qty, price) {
  qty = Math.floor(qty);
  if (qty <= 0 || price <= 0) return false;
  const h = state.holdings.get(seller);
  const have = h?.get(asset) ?? 0;
  if (have < qty) return false;
  h.set(asset, have - qty);
  state.listings.push({ id: state.nextId++, seller, asset, quantity: qty, price_per_share: +price.toFixed(2) });
  return true;
}

function buyListing(listingId, buyer, qty) {
  qty = Math.floor(qty);
  if (qty <= 0) return false;
  const idx = state.listings.findIndex(l => l.id === listingId);
  if (idx < 0) return false;
  const listing = state.listings[idx];
  if (listing.quantity < qty) return false;
  const total = qty * listing.price_per_share;
  const fee   = Math.round(total * TRADE_FEE * 100) / 100;
  const due   = total + fee;
  if (getBalance(buyer) < due) return false;

  state.users.get(buyer).balance -= due;
  state.users.get(listing.seller).balance += total;

  const bh = state.holdings.get(buyer);
  bh.set(listing.asset, (bh.get(listing.asset) ?? 0) + qty);

  listing.quantity -= qty;
  if (listing.quantity === 0) state.listings.splice(idx, 1);

  state.transactions.push({ buyer, seller: listing.seller, asset: listing.asset,
    qty, price: listing.price_per_share, total, fee });
  return true;
}

function consume(user, asset, qty) {
  const h = state.holdings.get(user);
  const have = h?.get(asset) ?? 0;
  h.set(asset, Math.max(0, have - qty));
}

function recordPriceSnapshot(iteration) {
  const newTxs = state.transactions.slice(state.lastSnapshotTxIdx);
  state.lastSnapshotTxIdx = state.transactions.length;

  const prices = {};

  for (const asset of ASSETS) {
    const txs = newTxs.filter(t => t.asset === asset);
    if (txs.length) {
      const totalQty   = txs.reduce((s, t) => s + t.qty, 0);
      const totalValue = txs.reduce((s, t) => s + t.qty * t.price, 0);
      prices[asset] = totalValue / totalQty;
    }
  }

  // Fall back to min listing price for assets with no recent transactions
  for (const asset of ASSETS) {
    if (!(asset in prices)) {
      const ap = state.listings.filter(l => l.asset === asset).map(l => l.price_per_share);
      if (ap.length) prices[asset] = Math.min(...ap);
    }
  }

  for (const [asset, p] of Object.entries(prices)) {
    state.priceHistory.push({ iteration, asset, avg_price: +p.toFixed(4) });
  }
}

function recordNwSnapshot(iteration) {
  // Current min listing price per asset (for valuation)
  const prices = {};
  for (const asset of ASSETS) {
    const ap = state.listings.filter(l => l.asset === asset).map(l => l.price_per_share);
    if (ap.length) {
      prices[asset] = Math.min(...ap);
    } else {
      const last = [...state.priceHistory].reverse().find(p => p.asset === asset);
      prices[asset] = last?.avg_price ?? 0;
    }
  }
  for (const [name] of state.users) {
    let nw = getBalance(name);
    for (const asset of ASSETS) nw += getHolding(name, asset) * (prices[asset] ?? 0);
    state.nwHistory.push({ iteration, name, nw: +nw.toFixed(2) });
  }
}

function strategyChaos(name) {
  if (Math.random() < 0.4) {
    const listings = othersListings(name);
    if (!listings.length) return;
    const listing = listings[Math.floor(Math.random() * listings.length)];
    const maxQty = Math.floor(getBalance(name) / (listing.price_per_share * 1.005));
    if (maxQty <= 0) return;
    const qty = Math.floor(Math.random() * Math.min(maxQty, listing.quantity)) + 1;
    buyListing(listing.id, name, qty);
  } else {
    const owned = ASSETS.filter(a => getHolding(name, a) > 0);
    if (!owned.length) return;
    const asset = owned[Math.floor(Math.random() * owned.length)];
    const have  = getHolding(name, asset);
    const qty   = Math.floor(Math.random() * have) + 1;
    const price = +(1 + Math.random() * 19).toFixed(2);
    createListing(name, asset, qty, price);
  }
}

function strategyFlipper(name) {
  const listings = othersListings(name).sort((a, b) => a.price_per_share - b.price_per_share);
  if (!listings.length) return;
  const listing = listings[0];
  const maxQty  = Math.floor(getBalance(name) / (listing.price_per_share * 1.005));
  if (maxQty <= 0) return;
  const qty = Math.min(maxQty, listing.quantity);
  if (buyListing(listing.id, name, qty)) {
    createListing(name, listing.asset, qty, +(listing.price_per_share * 1.25).toFixed(2));
  }
}

function strategyHoarder(name) {
  const food = othersListings(name)
    .filter(l => l.asset === 'FOOD')
    .sort((a, b) => a.price_per_share - b.price_per_share);
  for (const listing of food) {
    const maxQty = Math.floor(getBalance(name) / (listing.price_per_share * 1.005));
    if (maxQty <= 0) break;
    buyListing(listing.id, name, Math.min(maxQty, listing.quantity));
  }
}

function strategyMomentum(name) {
  const avail = othersListings(name);
  if (!avail.length) return;
  const vol = {};
  for (const l of avail) vol[l.asset] = (vol[l.asset] ?? 0) + l.quantity;
  const top = Object.entries(vol).sort((a, b) => b[1] - a[1])[0]?.[0];
  if (!top) return;
  const targets = avail.filter(l => l.asset === top).sort((a, b) => a.price_per_share - b.price_per_share);
  for (const listing of targets) {
    const maxQty = Math.floor(getBalance(name) / (listing.price_per_share * 1.005));
    if (maxQty <= 0) break;
    buyListing(listing.id, name, Math.min(maxQty, listing.quantity));
  }
}

function strategySniper(name) {
  const MAX_PRICE = 10;
  const cheap = othersListings(name)
    .filter(l => l.price_per_share < MAX_PRICE)
    .sort((a, b) => a.price_per_share - b.price_per_share);
  for (const listing of cheap) {
    const maxQty = Math.floor(getBalance(name) / (listing.price_per_share * 1.005));
    if (maxQty <= 0) break;
    buyListing(listing.id, name, Math.min(maxQty, listing.quantity));
  }
}

function strategyUndercut(name) {
  const others = othersListings(name);
  for (const asset of ASSETS) {
    const qty = getHolding(name, asset);
    if (qty <= 0) continue;
    const prices = others.filter(l => l.asset === asset).map(l => l.price_per_share);
    if (!prices.length) continue;
    const minP = Math.min(...prices);
    if (minP <= 0.01) continue;
    createListing(name, asset, qty, +(minP - 0.01).toFixed(2));
  }
}

function strategyValueInvestor(name) {
  for (const asset of ASSETS) {
    const all = state.listings.filter(l => l.asset === asset);
    if (!all.length) continue;
    const avg = all.reduce((s, l) => s + l.price_per_share, 0) / all.length;

    const bargains = all
      .filter(l => l.seller !== name && l.price_per_share < avg)
      .sort((a, b) => a.price_per_share - b.price_per_share);

    for (const listing of bargains) {
      const maxQty = Math.floor(getBalance(name) / (listing.price_per_share * 1.005));
      if (maxQty <= 0) break;
      buyListing(listing.id, name, Math.min(maxQty, listing.quantity));
    }

    const hold = getHolding(name, asset);
    if (hold > 0) createListing(name, asset, hold, +(avg * 1.05).toFixed(2));
  }
}

function strategyPanicSell(name) {
  for (const asset of ASSETS) {
    const qty = getHolding(name, asset);
    if (qty > 0) createListing(name, asset, qty, 1.00);
  }
}

function strategyBuyEverything(name) {
  const listings = othersListings(name).sort(() => Math.random() - 0.5);
  for (const snap of listings) {
    const cur = state.listings.find(l => l.id === snap.id);
    if (!cur) continue;
    buyListing(snap.id, name, cur.quantity);
  }
}

const STRATEGIES = {
  'chaos':          strategyChaos,
  'flipper':        strategyFlipper,
  'hoarder':        strategyHoarder,
  'momentum':       strategyMomentum,
  'sniper':         strategySniper,
  'undercut':       strategyUndercut,
  'value-investor': strategyValueInvestor,
  'panic-sell':     strategyPanicSell,
  'buy-everything': strategyBuyEverything,
};

let running = false;

async function runSimulation() {
  if (running) return;
  running = true;

  const iterations = Math.max(1, parseInt(document.getElementById('iterations').value) || 30);
  const agents = DEFAULT_AGENTS;

  document.getElementById('runBtn').disabled = true;
  document.getElementById('log').textContent = '';

  resetState(agents);
  recordNwSnapshot(0);

  buildLegends(agents);
  drawPriceChart(iterations);
  drawNwChart(agents, iterations);
  updateLeaderboard(agents);

  for (let i = 1; i <= iterations; i++) {
    // Each agent takes a turn
    for (const agent of agents) {
      const fn = STRATEGIES[agent.strategy];
      if (fn) fn(agent.name);
    }

    // Consumption: 1-3 units of each asset per agent
    for (const agent of agents) {
      for (const asset of ASSETS) {
        consume(agent.name, asset, Math.floor(Math.random() * 3) + 1);
      }
    }

    recordPriceSnapshot(i);
    recordNwSnapshot(i);

    updateProgress(i, iterations);
    drawPriceChart(iterations);
    drawNwChart(agents, iterations);
    updateLeaderboard(agents);
    logIteration(i, agents);

    await new Promise(r => setTimeout(r, 16));
  }

  document.getElementById('progress-text').textContent =
    `Done — ${iterations} iterations, ${agents.length} agents`;
  document.getElementById('runBtn').disabled = false;
  running = false;
}

function logIteration(i, agents) {
  const el = document.getElementById('log');
  const txs = state.transactions.slice(-agents.length * 4);
  if (!txs.length) return;
  const lines = txs.map(t =>
    `iter ${i.toString().padStart(3)} | ${t.buyer.padEnd(7)} bought ${t.qty.toString().padStart(3)}x ${t.asset.padEnd(5)} @ $${t.price.toFixed(2)} from ${t.seller}`
  );
  el.textContent = lines.join('\n') + '\n' + el.textContent;
}

function updateProgress(i, total) {
  document.getElementById('progress-bar').style.width = (i / total * 100) + '%';
  document.getElementById('progress-text').textContent = `Iteration ${i} / ${total}`;
}

function buildLegends(agents) {
  const pl = document.getElementById('priceLegend');
  pl.innerHTML = ASSETS.map(a =>
    `<span class="legend-item">
      <span class="legend-swatch" style="background:${ASSET_COLORS[a]}"></span>${a}
    </span>`
  ).join('');

  const nl = document.getElementById('nwLegend');
  nl.innerHTML = agents.map(a =>
    `<span class="legend-item">
      <span class="legend-swatch" style="background:${AGENT_COLORS[a.name] ?? '#999'}"></span>${a.name}
    </span>`
  ).join('');
}

function updateLeaderboard(agents) {
  const prices = {};
  for (const asset of ASSETS) {
    const ap = state.listings.filter(l => l.asset === asset).map(l => l.price_per_share);
    if (ap.length) prices[asset] = Math.min(...ap);
    else {
      const last = [...state.priceHistory].reverse().find(p => p.asset === asset);
      prices[asset] = last?.avg_price ?? 0;
    }
  }

  const rows = agents.map(a => {
    const bal = getBalance(a.name);
    const food  = getHolding(a.name, 'FOOD');
    const oil   = getHolding(a.name, 'OIL');
    const water = getHolding(a.name, 'WATER');
    const nw    = bal + food * (prices.FOOD ?? 0) + oil * (prices.OIL ?? 0) + water * (prices.WATER ?? 0);
    return { name: a.name, strategy: a.strategy, bal, food, oil, water, nw };
  }).sort((a, b) => b.nw - a.nw);

  const tbody = document.getElementById('leaderboard-body');
  tbody.innerHTML = rows.map((r, i) => {
    const rankCls = i < 3 ? `rank rank-${i + 1}` : 'rank';
    const medal   = ['🥇', '🥈', '🥉'][i] ?? `${i + 1}.`;
    const color   = AGENT_COLORS[r.name] ?? '#999';
    return `<tr>
      <td><span class="${rankCls}">${medal}</span></td>
      <td><span class="color-pip" style="background:${color}"></span>${r.name}</td>
      <td><span class="strategy-tag">${r.strategy}</span></td>
      <td>$${r.bal.toFixed(2)}</td>
      <td>${r.food}</td>
      <td>${r.oil}</td>
      <td>${r.water}</td>
      <td class="nw">$${r.nw.toFixed(2)}</td>
    </tr>`;
  }).join('');
}

document.getElementById('runBtn').addEventListener('click', runSimulation);

resetState(DEFAULT_AGENTS);
buildLegends(DEFAULT_AGENTS);
updateLeaderboard(DEFAULT_AGENTS);
