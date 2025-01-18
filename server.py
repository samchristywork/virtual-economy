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
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    NOT NULL UNIQUE,
            balance REAL    NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS holdings (
            user_id  INTEGER NOT NULL,
            asset    TEXT    NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, asset),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS listings (
            id              INTEGER   PRIMARY KEY AUTOINCREMENT,
            seller_id       INTEGER   NOT NULL,
            asset           TEXT      NOT NULL,
            quantity        INTEGER   NOT NULL,
            price_per_share REAL      NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (seller_id) REFERENCES users(id)
        );
    """)

    for name in ("Alice", "Bob"):
        conn.execute("INSERT OR IGNORE INTO users (name, balance) VALUES (?, 1000)", (name,))
    conn.commit()

    for name in ("Alice", "Bob"):
        uid = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()["id"]
        for asset in ("FOOD", "OIL", "WATER"):
            conn.execute(
                "INSERT OR IGNORE INTO holdings (user_id, asset, quantity) VALUES (?, ?, 50)",
                (uid, asset),
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
                rows = conn.execute("SELECT id, name, balance FROM users").fetchall()
                conn.close()
            send_json(self, 200, [dict(r) for r in rows])

        elif parsed.path == "/holdings":
            user_id = params.get("user_id", [None])[0]
            with db_lock:
                conn = get_db()
                if user_id:
                    rows = conn.execute(
                        "SELECT asset, quantity FROM holdings WHERE user_id = ? AND quantity > 0",
                        (user_id,),
                    ).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT u.name, h.asset, h.quantity
                        FROM holdings h JOIN users u ON h.user_id = u.id
                        WHERE h.quantity > 0
                        ORDER BY u.name, h.asset
                    """).fetchall()
                conn.close()
            send_json(self, 200, [dict(r) for r in rows])

        elif parsed.path == "/listings":
            with db_lock:
                conn = get_db()
                rows = conn.execute("""
                    SELECT l.id, u.name AS seller, l.asset, l.quantity,
                           l.price_per_share, l.created_at
                    FROM listings l JOIN users u ON l.seller_id = u.id
                    ORDER BY l.created_at DESC
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
        elif parsed.path == "/listings/cancel":
            self._cancel_listing(data)
        elif parsed.path == "/buy":
            self._buy(data)
        else:
            send_error(self, 404, "Not found")
