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
    conn.commit()
    conn.close()
