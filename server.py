#!/usr/bin/env python3

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DB_PATH = "market.db"
db_lock = threading.Lock()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
    """)

    for name in ("Alice", "Bob"):
        conn.execute("INSERT OR IGNORE INTO users (name, balance) VALUES (?, 1000)", (name,))
    conn.commit()

    for name in ("Alice", "Bob"):
        for asset in ("FOOD", "OIL", "WATER"):
            conn.execute(
                "INSERT OR IGNORE INTO holdings (user_name, asset, quantity) VALUES (?, ?, 50)",
                (name, asset),
            )
    conn.commit()
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

        else:
            send_error(self, 404, "Not found")

    def do_POST(self):
        data = self.read_body()
        if data is None:
            send_error(self, 400, "Invalid JSON")
            return

        parsed = urlparse(self.path)

        if parsed.path == "/listings":
            self._create_listing(data)
        elif parsed.path == "/cancel":
            self._cancel_listing(data)
        elif parsed.path == "/buy":
            self._buy(data)
        elif parsed.path == "/consume":
            self._consume(data)
        elif parsed.path == "/reset":
            self._reset()
        else:
            send_error(self, 404, "Not found")

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

    def _cancel_listing(self, data):
        listing_id = data.get("listing_id")
        seller     = data.get("seller")

        if not all(v is not None for v in [listing_id, seller]):
            send_error(self, 400, "Required: listing_id, seller")
            return

        try:
            listing_id = int(listing_id)
        except (ValueError, TypeError):
            send_error(self, 400, "Invalid numeric values")
            return

        with db_lock:
            conn = get_db()
            try:
                listing = conn.execute(
                    "SELECT * FROM listings WHERE id = ? AND seller_name = ?",
                    (listing_id, seller),
                ).fetchone()

                if not listing:
                    send_error(self, 404, "Listing not found or not owned by seller")
                    return

                conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
                conn.execute(
                    "UPDATE holdings SET quantity = quantity + ? WHERE user_name = ? AND asset = ?",
                    (listing["quantity"], seller, listing["asset"]),
                )
                conn.commit()
                send_json(self, 200, {"message": "Listing cancelled, shares returned"})
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

                if listing["seller_name"] == buyer:
                    send_error(self, 400, "Cannot buy your own listing")
                    return

                if listing["quantity"] < quantity:
                    send_error(self, 400, f"Only {listing['quantity']} shares available")
                    return

                total_cost = quantity * listing["price_per_share"]

                buyer_row = conn.execute(
                    "SELECT balance FROM users WHERE name = ?", (buyer,)
                ).fetchone()

                if not buyer_row:
                    send_error(self, 404, "Buyer not found")
                    return

                if buyer_row["balance"] < total_cost:
                    send_error(
                        self, 400,
                        f"Insufficient funds: need ${total_cost:.2f}, have ${buyer_row['balance']:.2f}",
                    )
                    return

                conn.execute(
                    "UPDATE users SET balance = balance - ? WHERE name = ?",
                    (total_cost, buyer),
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

                conn.commit()
                send_json(self, 200, {
                    "message": f"Bought {quantity} shares of {listing['asset']} for ${total_cost:.2f}"
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
                    DELETE FROM listings;
                    DELETE FROM holdings;
                    DELETE FROM users;
                """)
                conn.commit()
            finally:
                conn.close()
        init_db()
        send_json(self, 200, {"message": "Reset complete"})

if __name__ == "__main__":
    init_db()
    port = 8000
    server = HTTPServer(("0.0.0.0", port), MarketHandler)
    print(f"Server running on http://localhost:{port}")
    server.serve_forever()
