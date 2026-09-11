import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_ROOT / "data" / "munshi.db"


def get_connection():
    """Create and return a database connection."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def _column_names(connection, table_name):
    cursor = connection.cursor()
    try:
        rows = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [row[1] for row in rows]
    except sqlite3.DatabaseError:
        return []


def _ensure_column(connection, table_name, column_name, column_sql):
    cursor = connection.cursor()
    existing = _column_names(connection, table_name)
    if column_name not in existing:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def _migrate_legacy_transactions(connection):
    """Support older schema versions with total_amount/paid_amount/due_amount names."""
    cursor = connection.cursor()
    columns = _column_names(connection, "transactions")

    if not columns:
        return

    if "amount" in columns and "paid" in columns and "due" in columns:
        return

    if "total_amount" in columns and "paid_amount" in columns and "due_amount" in columns:
        cursor.execute("ALTER TABLE transactions RENAME TO transactions_legacy")
        cursor.execute(
            """
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                transaction_type TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                paid REAL DEFAULT 0,
                due REAL DEFAULT 0,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO transactions (customer_id, transaction_type, description, amount, paid, due, date)
            SELECT customer_id, transaction_type, description, total_amount, paid_amount, due_amount, transaction_date
            FROM transactions_legacy
            """
        )
        cursor.execute("DROP TABLE transactions_legacy")
        connection.commit()


def initialize_database():
    """Create all required database tables and migrate legacy schema if needed."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE,
            plan TEXT DEFAULT 'starter',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO tenants (id, name, slug, plan, is_active)
        VALUES (1, 'Main Shop', 'main-shop', 'starter', 1)
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL DEFAULT 1,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'owner',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            owner_name TEXT DEFAULT 'Owner',
            phone TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
        """
    )

    _ensure_column(connection, "shops", "tenant_id", "INTEGER DEFAULT 1")

    cursor.execute(
        """
        INSERT OR IGNORE INTO shops (id, tenant_id, name, owner_name, phone, address)
        VALUES (1, 1, 'Main Shop', 'Owner', '', '')
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shop_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            shop_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'Staff',
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
        """
    )

    _ensure_column(connection, "shop_users", "tenant_id", "INTEGER DEFAULT 1")

    cursor.execute(
        """
        INSERT OR IGNORE INTO shop_users (id, tenant_id, shop_id, name, role, phone)
        VALUES (1, 1, 1, 'Owner', 'Owner', '')
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            shop_id INTEGER DEFAULT 1,
            name TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
        """
    )

    _ensure_column(connection, "customers", "tenant_id", "INTEGER DEFAULT 1")
    _ensure_column(connection, "customers", "shop_id", "INTEGER DEFAULT 1")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            customer_id INTEGER,
            shop_id INTEGER DEFAULT 1,
            transaction_type TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            paid REAL DEFAULT 0,
            due REAL DEFAULT 0,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
        """
    )

    _ensure_column(connection, "transactions", "tenant_id", "INTEGER DEFAULT 1")
    _ensure_column(connection, "transactions", "shop_id", "INTEGER DEFAULT 1")
    _migrate_legacy_transactions(connection)

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER DEFAULT 1,
            shop_id INTEGER DEFAULT 1,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
        """
    )

    _ensure_column(connection, "expenses", "tenant_id", "INTEGER DEFAULT 1")
    _ensure_column(connection, "expenses", "shop_id", "INTEGER DEFAULT 1")

    connection.commit()
    connection.close()


def get_shops(tenant_id):
    """Return shops belonging to the given tenant only."""
    connection = get_connection()
    rows = connection.execute(
        "SELECT id, name, owner_name, phone, address FROM shops WHERE tenant_id = ? ORDER BY id ASC",
        (tenant_id,),
    ).fetchall()
    connection.close()
    return rows


def get_shop_users(tenant_id, shop_id=1):
    connection = get_connection()
    rows = connection.execute(
        "SELECT id, name, role, phone FROM shop_users WHERE tenant_id = ? AND shop_id = ? ORDER BY role ASC, name ASC",
        (tenant_id, shop_id),
    ).fetchall()
    connection.close()
    return rows


def get_team_members(tenant_id, shop_id=1):
    connection = get_connection()
    rows = connection.execute(
        "SELECT id, name, role, phone FROM shop_users WHERE tenant_id = ? AND shop_id = ? ORDER BY role ASC, name ASC",
        (tenant_id, shop_id),
    ).fetchall()
    connection.close()
    return rows


def add_team_member(tenant_id, name, role="Staff", phone="", shop_id=1):
    name = (name or "").strip()
    if not name:
        return None
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO shop_users (tenant_id, shop_id, name, role, phone) VALUES (?, ?, ?, ?, ?)",
        (tenant_id, shop_id, name, role, phone),
    )
    member_id = cursor.lastrowid
    connection.commit()
    connection.close()
    return member_id


def add_shop(tenant_id, name, owner_name="Owner", phone="", address=""):
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO shops (tenant_id, name, owner_name, phone, address) VALUES (?, ?, ?, ?, ?)",
        (tenant_id, name, owner_name, phone, address),
    )
    shop_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO shop_users (tenant_id, shop_id, name, role, phone) VALUES (?, ?, ?, 'Owner', ?)",
        (tenant_id, shop_id, owner_name, phone),
    )
    connection.commit()
    connection.close()
    return shop_id


initialize_database()


if __name__ == "__main__":
    initialize_database()
    print("Munshi AI database initialized successfully!")