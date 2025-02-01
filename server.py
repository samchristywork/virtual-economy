#!/usr/bin/env python3

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DB_PATH = "market.db"
db_lock = threading.Lock()

TRADE_FEE = 0.005 #0.5% of transaction value

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            name    TEXT PRIMARY KEY,
            balance REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS holdings (
            user_name TEXT    NOT NULL,
            asset     TEXT    NOT NULL,
            quantity  INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_name, asset),
            FOREIGN KEY (user_name) REFERENCES users(name)
        );

        CREATE TABLE IF NOT EXISTS listings (
            id              INTEGER   PRIMARY KEY AUTOINCREMENT,
            seller_name     TEXT      NOT NULL,
            asset           TEXT      NOT NULL,
            quantity        INTEGER   NOT NULL,
            price_per_share REAL      NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_name) REFERENCES users(name)
        );

        CREATE INDEX IF NOT EXISTS idx_listings_created_at ON listings(created_at DESC);

        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER   PRIMARY KEY AUTOINCREMENT,
            buyer_name      TEXT      NOT NULL,
            seller_name     TEXT      NOT NULL,
            asset           TEXT      NOT NULL,
            quantity        INTEGER   NOT NULL,
            price_per_share REAL      NOT NULL,
            total_price     REAL      NOT NULL,
            fee             REAL      NOT NULL DEFAULT 0,
            executed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_transactions_executed_at ON transactions(executed_at DESC);

        CREATE TABLE IF NOT EXISTS price_history (
            id          INTEGER   PRIMARY KEY AUTOINCREMENT,
            iteration   INTEGER   NOT NULL,
            asset       TEXT      NOT NULL,
            avg_price   REAL      NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_price_history ON price_history(iteration, asset);
    """)

    conn.close()

def send_json(handler, status, data):
    body = json.dumps(data, indent=2).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", len(body))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)

def send_error(handler, status, message):
    send_json(handler, status, {"error": message})

class MarketHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path in ("/", "/index.html"):
            try:
                with open("index.html", "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            except FileNotFoundError:
                send_error(self, 404, "index.html not found")

        elif parsed.path == "/users":
            with db_lock:
                conn = get_db()
                rows = conn.execute("SELECT name, balance FROM users").fetchall()
                conn.close()
            send_json(self, 200, [dict(r) for r in rows])

        elif parsed.path == "/holdings":
            user_name = params.get("user", [None])[0]
            with db_lock:
                conn = get_db()
                if user_name:
                    rows = conn.execute(
                        "SELECT asset, quantity FROM holdings WHERE user_name = ? AND quantity > 0",
                        (user_name,),
                    ).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT user_name AS name, asset, quantity
                        FROM holdings
                        WHERE quantity > 0
                        ORDER BY user_name, asset
                    """).fetchall()
                conn.close()
            send_json(self, 200, [dict(r) for r in rows])

        elif parsed.path == "/listings":
            with db_lock:
                conn = get_db()
                rows = conn.execute("""
                    SELECT id, seller_name AS seller, asset, quantity,
                           price_per_share, created_at
                    FROM listings
                    ORDER BY created_at DESC
                """).fetchall()
                conn.close()
            send_json(self, 200, [dict(r) for r in rows])

        elif parsed.path == "/transactions":
            user_name = params.get("user", [None])[0]
            with db_lock:
                conn = get_db()
                if user_name:
                    rows = conn.execute("""
                        SELECT id, buyer_name AS buyer, seller_name AS seller,
                               asset, quantity, price_per_share, total_price, fee, executed_at
                        FROM transactions
                        WHERE buyer_name = ? OR seller_name = ?
                        ORDER BY executed_at DESC
                    """, (user_name, user_name)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT id, buyer_name AS buyer, seller_name AS seller,
                               asset, quantity, price_per_share, total_price, fee, executed_at
                        FROM transactions
                        ORDER BY executed_at DESC
                    """).fetchall()
                conn.close()
            send_json(self, 200, [dict(r) for r in rows])

        elif parsed.path == "/prices/history":
            self._get_price_history(params)

        else:
            send_error(self, 404, "Not found")

    def do_POST(self):
        data = self.read_body()
        if data is None:
            send_error(self, 400, "Invalid JSON")
            return

        parsed = urlparse(self.path)

        if parsed.path == "/users":
            self._create_user(data)
        elif parsed.path == "/listings":
            self._create_listing(data)
        elif parsed.path == "/buy":
            self._buy(data)
        elif parsed.path == "/consume":
            self._consume(data)
        elif parsed.path == "/prices/snapshot":
            self._record_snapshot(data)
        elif parsed.path == "/reset":
            self._reset()
        else:
            send_error(self, 404, "Not found")

    def _create_user(self, data):
        name    = data.get("name")
        balance = data.get("balance", 1000)

        if not name:
            send_error(self, 400, "Required: name")
            return

        try:
            balance = float(balance)
        except (ValueError, TypeError):
            send_error(self, 400, "Invalid numeric value for balance")
            return

        if balance < 0:
            send_error(self, 400, "balance must be non-negative")
            return

        name = str(name)

        with db_lock:
            conn = get_db()
            try:
                existing = conn.execute(
                    "SELECT name FROM users WHERE name = ?", (name,)
                ).fetchone()
                if existing:
                    send_error(self, 409, f"User '{name}' already exists")
                    return

                conn.execute(
                    "INSERT INTO users (name, balance) VALUES (?, ?)", (name, balance)
                )
                for asset in ("FOOD", "OIL", "WATER"):
                    conn.execute(
                        "INSERT INTO holdings (user_name, asset, quantity) VALUES (?, ?, 50)",
                        (name, asset),
                    )
                conn.commit()
                send_json(self, 201, {"name": name, "balance": balance})
            except Exception as e:
                conn.rollback()
                send_error(self, 500, str(e))
            finally:
                conn.close()

    def _create_listing(self, data):
        seller   = data.get("seller")
        asset    = data.get("asset")
        quantity = data.get("quantity")
        price    = data.get("price_per_share")

        if not all(v is not None for v in [seller, asset, quantity, price]):
            send_error(self, 400, "Required: seller, asset, quantity, price_per_share")
            return

        try:
            quantity = int(quantity)
            price    = float(price)
        except (ValueError, TypeError):
            send_error(self, 400, "Invalid numeric values")
            return

        if quantity <= 0 or price <= 0:
            send_error(self, 400, "quantity and price_per_share must be positive")
            return

        asset = str(asset).upper()

        with db_lock:
            conn = get_db()
            try:
                user_row = conn.execute(
                    "SELECT name FROM users WHERE name = ?", (seller,)
                ).fetchone()
                if not user_row:
                    send_error(self, 404, f"Seller '{seller}' not found")
                    return

                holding = conn.execute(
                    "SELECT quantity FROM holdings WHERE user_name = ? AND asset = ?",
                    (seller, asset),
                ).fetchone()

                if not holding or holding["quantity"] < quantity:
                    available = holding["quantity"] if holding else 0
                    send_error(self, 400, f"Insufficient holdings: have {available}, need {quantity}")
                    return

                conn.execute(
                    "UPDATE holdings SET quantity = quantity - ? WHERE user_name = ? AND asset = ?",
                    (quantity, seller, asset),
                )
                row = conn.execute(
                    "INSERT INTO listings (seller_name, asset, quantity, price_per_share) VALUES (?, ?, ?, ?)",
                    (seller, asset, quantity, price),
                )
                conn.commit()
                send_json(self, 201, {"listing_id": row.lastrowid, "message": "Listing created"})
            except Exception as e:
                conn.rollback()
                send_error(self, 500, str(e))
            finally:
                conn.close()

    def _buy(self, data):
        listing_id = data.get("listing_id")
        buyer      = data.get("buyer")
        quantity   = data.get("quantity")

        if not all(v is not None for v in [listing_id, buyer, quantity]):
            send_error(self, 400, "Required: listing_id, buyer, quantity")
            return

        try:
            listing_id = int(listing_id)
            quantity   = int(quantity)
        except (ValueError, TypeError):
            send_error(self, 400, "Invalid numeric values")
            return

        if quantity <= 0:
            send_error(self, 400, "quantity must be positive")
            return

        with db_lock:
            conn = get_db()
            try:
                listing = conn.execute(
                    "SELECT * FROM listings WHERE id = ?", (listing_id,)
                ).fetchone()

                if not listing:
                    send_error(self, 404, "Listing not found")
                    return

                if listing["quantity"] < quantity:
                    send_error(self, 400, f"Only {listing['quantity']} shares available")
                    return

                total_cost = quantity * listing["price_per_share"]
                fee        = round(total_cost * TRADE_FEE, 2)
                total_due  = total_cost + fee

                buyer_row = conn.execute(
                    "SELECT balance FROM users WHERE name = ?", (buyer,)
                ).fetchone()

                if not buyer_row:
                    send_error(self, 404, "Buyer not found")
                    return

                if buyer_row["balance"] < total_due:
                    send_error(
                        self, 400,
                        f"Insufficient funds: need ${total_due:.2f} (${total_cost:.2f} + ${fee:.2f} fee),"
                        f" have ${buyer_row['balance']:.2f}",
                    )
                    return

                conn.execute(
                    "UPDATE users SET balance = balance - ? WHERE name = ?",
                    (total_due, buyer),
                )
                conn.execute(
                    "UPDATE users SET balance = balance + ? WHERE name = ?",
                    (total_cost, listing["seller_name"]),
                )
                conn.execute(
                    "INSERT INTO holdings (user_name, asset, quantity) VALUES (?, ?, ?)"
                    " ON CONFLICT(user_name, asset) DO UPDATE SET quantity = quantity + ?",
                    (buyer, listing["asset"], quantity, quantity),
                )

                remaining = listing["quantity"] - quantity
                if remaining == 0:
                    conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
                else:
                    conn.execute(
                        "UPDATE listings SET quantity = ? WHERE id = ?",
                        (remaining, listing_id),
                    )

                conn.execute(
                    "INSERT INTO transactions"
                    " (buyer_name, seller_name, asset, quantity, price_per_share, total_price, fee)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (buyer, listing["seller_name"], listing["asset"],
                     quantity, listing["price_per_share"], total_cost, fee),
                )

                conn.commit()
                send_json(self, 200, {
                    "message": f"Bought {quantity} shares of {listing['asset']}"
                               f" for ${total_cost:.2f} + ${fee:.2f} fee",
                    "total_cost": total_cost,
                    "fee": fee,
                })
            except Exception as e:
                conn.rollback()
                send_error(self, 500, str(e))
            finally:
                conn.close()

    def _consume(self, data):
        user     = data.get("user")
        asset    = data.get("asset")
        quantity = data.get("quantity")

        if not all(v is not None for v in [user, asset, quantity]):
            send_error(self, 400, "Required: user, asset, quantity")
            return

        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            send_error(self, 400, "Invalid numeric values")
            return

        if quantity <= 0:
            send_error(self, 400, "quantity must be positive")
            return

        asset = str(asset).upper()

        with db_lock:
            conn = get_db()
            try:
                holding = conn.execute(
                    "SELECT quantity FROM holdings WHERE user_name = ? AND asset = ?",
                    (user, asset),
                ).fetchone()

                if not holding or holding["quantity"] < quantity:
                    available = holding["quantity"] if holding else 0
                    send_error(self, 400, f"Insufficient holdings: have {available}, need {quantity}")
                    return

                conn.execute(
                    "UPDATE holdings SET quantity = quantity - ? WHERE user_name = ? AND asset = ?",
                    (quantity, user, asset),
                )
                conn.commit()
                send_json(self, 200, {"message": f"Consumed {quantity} units of {asset}"})
            except Exception as e:
                conn.rollback()
                send_error(self, 500, str(e))
            finally:
                conn.close()

    def _reset(self):
        with db_lock:
            conn = get_db()
            try:
                conn.executescript("""
                    DELETE FROM price_history;
                    DELETE FROM transactions;
                    DELETE FROM listings;
                    DELETE FROM holdings;
                    DELETE FROM users;
                """)
                conn.commit()
            finally:
                conn.close()
        init_db()
        send_json(self, 200, {"message": "Reset complete"})

    def _get_price_history(self, params):
        asset = params.get("asset", [None])[0]
        with db_lock:
            conn = get_db()
            if asset:
                rows = conn.execute(
                    "SELECT iteration, asset, avg_price, recorded_at"
                    " FROM price_history WHERE asset = ? ORDER BY iteration",
                    (asset.upper(),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT iteration, asset, avg_price, recorded_at"
                    " FROM price_history ORDER BY iteration, asset"
                ).fetchall()
            conn.close()
        send_json(self, 200, [dict(r) for r in rows])

    def _record_snapshot(self, data):
        iteration = data.get("iteration", 0)
        try:
            iteration = int(iteration)
        except (ValueError, TypeError):
            send_error(self, 400, "Invalid iteration value")
            return

        with db_lock:
            conn = get_db()
            try:
                last_row = conn.execute(
                    "SELECT MAX(recorded_at) AS ts FROM price_history"
                ).fetchone()
                last_ts = last_row["ts"]

                # Weighted average of transactions since the previous snapshot
                if last_ts:
                    tx_rows = conn.execute("""
                        SELECT asset,
                               CAST(SUM(quantity * price_per_share) AS REAL) / SUM(quantity) AS avg_price
                        FROM transactions
                        WHERE executed_at > ?
                        GROUP BY asset
                    """, (last_ts,)).fetchall()
                else:
                    tx_rows = conn.execute("""
                        SELECT asset,
                               CAST(SUM(quantity * price_per_share) AS REAL) / SUM(quantity) AS avg_price
                        FROM transactions
                        GROUP BY asset
                    """).fetchall()

                prices = {r["asset"]: r["avg_price"] for r in tx_rows}

                # Fall back to minimum listing price for assets with no recent transactions
                for r in conn.execute(
                    "SELECT asset, MIN(price_per_share) AS p FROM listings GROUP BY asset"
                ).fetchall():
                    if r["asset"] not in prices:
                        prices[r["asset"]] = r["p"]

                if not prices:
                    send_json(self, 200, {"message": "No price data available", "iteration": iteration})
                    return

                for asset, avg_price in prices.items():
                    conn.execute(
                        "INSERT INTO price_history (iteration, asset, avg_price) VALUES (?, ?, ?)",
                        (iteration, asset, round(avg_price, 4)),
                    )
                conn.commit()
                send_json(self, 201, {
                    "iteration": iteration,
                    "prices": {k: round(v, 4) for k, v in prices.items()},
                })
            except Exception as e:
                conn.rollback()
                send_error(self, 500, str(e))
            finally:
                conn.close()


if __name__ == "__main__":
    init_db()
    port = 8000
    server = HTTPServer(("0.0.0.0", port), MarketHandler)
    print(f"Server running on http://localhost:{port}")
    server.serve_forever()
