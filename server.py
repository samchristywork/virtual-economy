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
