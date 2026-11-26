"""SQLite connection helper and table creation for the business data."""
import os
import sqlite3

from config.settings import SQLITE_PATH


def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection whose rows can be read like dictionaries."""
    os.makedirs(os.path.dirname(SQLITE_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def drop_tables() -> None:
    """Drop all business tables so the seed script can rebuild them with the latest schema."""
    conn = get_connection()
    conn.executescript(
        """
        DROP TABLE IF EXISTS shipments;
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;
        """
    )
    conn.commit()
    conn.close()


def create_tables() -> None:
    """Create the customers, orders, order_items and shipments tables if they do not exist."""
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL
        );
        -- One row per order: billing summary, payment and cancellation info
        CREATE TABLE IF NOT EXISTS orders (
            order_id            TEXT PRIMARY KEY,
            customer_id         TEXT NOT NULL REFERENCES customers(customer_id),
            order_date          TEXT NOT NULL,
            status              TEXT NOT NULL,   -- Processing / Shipped / Delivered / Cancelled
            subtotal            REAL NOT NULL,
            discount            REAL NOT NULL,
            shipping_fee        REAL NOT NULL,
            tax                 REAL NOT NULL,
            total               REAL NOT NULL,
            payment_method      TEXT NOT NULL,
            payment_status      TEXT NOT NULL,   -- Paid / Refunded / Refund Pending
            billing_address     TEXT NOT NULL,
            shipping_address    TEXT NOT NULL,
            cancelled_date      TEXT,
            cancellation_reason TEXT,
            refund_amount       REAL,
            refund_status       TEXT
        );
        -- One row per product in an order
        CREATE TABLE IF NOT EXISTS order_items (
            item_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   TEXT NOT NULL REFERENCES orders(order_id),
            product    TEXT NOT NULL,
            sku        TEXT NOT NULL,
            quantity   INTEGER NOT NULL,
            unit_price REAL NOT NULL
        );
        -- One row per shipped order, including delay information
        CREATE TABLE IF NOT EXISTS shipments (
            order_id                    TEXT PRIMARY KEY REFERENCES orders(order_id),
            carrier                     TEXT NOT NULL,
            tracking_number             TEXT NOT NULL,
            status                      TEXT NOT NULL,  -- In Transit / Out for Delivery / Delayed / Delivered
            last_location               TEXT,
            shipped_date                TEXT NOT NULL,
            original_delivery_date      TEXT NOT NULL,
            estimated_delivery          TEXT NOT NULL,  -- current/new ETA
            delay_reason                TEXT,
            delivered_date              TEXT
        );
        """
    )
    conn.commit()
    conn.close()
