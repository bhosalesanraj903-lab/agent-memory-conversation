"""Loads pre-built demo customers, orders, items and shipments. Run: python -m db.seed"""
from db.database import create_tables, drop_tables, get_connection

CUSTOMERS = [
    ("C001", "Alice Johnson", "alice@example.com"),
    ("C002", "Bob Smith", "bob@example.com"),
    ("C003", "Carol Lee", "carol@example.com"),
]

ORDERS = [
    # order_id, customer_id, order_date, status, subtotal, discount, shipping_fee, tax, total,
    # payment_method, payment_status, billing_address, shipping_address,
    # cancelled_date, cancellation_reason, refund_amount, refund_status
    ("ORD-1001", "C001", "2026-10-01", "Shipped", 129.98, 10.00, 5.99, 9.60, 135.57,
     "Visa ending 4242", "Paid", "12 Maple St, Austin, TX 78701", "12 Maple St, Austin, TX 78701",
     None, None, None, None),
    ("ORD-1002", "C001", "2026-10-10", "Processing", 70.00, 0.00, 0.00, 5.60, 75.60,
     "Visa ending 4242", "Paid", "12 Maple St, Austin, TX 78701", "98 Oak Ave, Dallas, TX 75001",
     None, None, None, None),
    ("ORD-1003", "C002", "2026-09-25", "Delivered", 120.50, 0.00, 0.00, 9.64, 130.14,
     "Mastercard ending 8811", "Paid", "44 Pine Rd, Boston, MA 02108", "44 Pine Rd, Boston, MA 02108",
     None, None, None, None),
    ("ORD-1004", "C002", "2026-10-15", "Shipped", 64.00, 6.40, 4.99, 4.61, 67.20,
     "PayPal", "Paid", "44 Pine Rd, Boston, MA 02108", "44 Pine Rd, Boston, MA 02108",
     None, None, None, None),
    ("ORD-1005", "C003", "2026-10-18", "Shipped", 219.98, 0.00, 0.00, 17.60, 237.58,
     "Visa ending 1177", "Paid", "7 Lake View, Denver, CO 80202", "7 Lake View, Denver, CO 80202",
     None, None, None, None),
    ("ORD-1006", "C003", "2026-10-20", "Cancelled", 78.00, 0.00, 5.99, 6.24, 90.23,
     "Visa ending 1177", "Refund Pending", "7 Lake View, Denver, CO 80202", "7 Lake View, Denver, CO 80202",
     "2026-10-21", "Customer found a lower price elsewhere and requested cancellation", 90.23,
     "Refund initiated, 5-7 business days"),
]

ORDER_ITEMS = [
    # order_id, product, sku, quantity, unit_price
    ("ORD-1001", "Wireless Headphones", "WH-100", 1, 89.99),
    ("ORD-1001", "Headphone Carry Case", "HC-020", 1, 39.99),
    ("ORD-1002", "USB-C Charger 65W", "UC-065", 2, 35.00),
    ("ORD-1003", "Running Shoes (Size 10)", "RS-410", 1, 120.50),
    ("ORD-1004", "Travel Backpack", "BP-230", 1, 64.00),
    ("ORD-1005", "Coffee Maker", "CM-500", 1, 149.99),
    ("ORD-1005", "Coffee Grinder", "CG-110", 1, 69.99),
    ("ORD-1006", "Desk Lamp", "DL-300", 3, 26.00),
]

SHIPMENTS = [
    # order_id, carrier, tracking_number, status, last_location, shipped_date,
    # original_delivery_date, estimated_delivery (new ETA), delay_reason, delivered_date
    ("ORD-1001", "FedEx", "FX123456789", "In Transit", "Memphis, TN", "2026-10-03",
     "2026-10-28", "2026-10-28", None, None),
    ("ORD-1003", "UPS", "UP987654321", "Delivered", "Boston, MA", "2026-09-26",
     "2026-09-29", "2026-09-29", None, "2026-09-28"),
    ("ORD-1004", "DHL", "DH555000111", "Out for Delivery", "Boston, MA", "2026-10-16",
     "2026-10-26", "2026-10-26", None, None),
    ("ORD-1005", "FedEx", "FX246813579", "Delayed", "Denver Hub, CO", "2026-10-19",
     "2026-10-24", "2026-11-02", "Severe snowstorm closed the Denver sorting hub for 3 days", None),
]


def seed_database() -> None:
    """Rebuild the tables from scratch and insert the demo rows (safe to run repeatedly)."""
    drop_tables()
    create_tables()
    conn = get_connection()
    conn.executemany("INSERT INTO customers VALUES (?,?,?)", CUSTOMERS)
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ORDERS)
    conn.executemany(
        "INSERT INTO order_items (order_id, product, sku, quantity, unit_price) VALUES (?,?,?,?,?)",
        ORDER_ITEMS,
    )
    conn.executemany("INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?,?,?)", SHIPMENTS)
    conn.commit()
    conn.close()


def list_customers() -> list[dict]:
    """Return all customers; the UI user picker will use this later."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM customers ORDER BY customer_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    seed_database()
    print(f"Seeded {len(CUSTOMERS)} customers, {len(ORDERS)} orders, "
          f"{len(ORDER_ITEMS)} order items, {len(SHIPMENTS)} shipments.")
