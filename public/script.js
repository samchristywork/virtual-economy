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
