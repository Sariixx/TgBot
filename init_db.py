import sqlite3
import os

DB_PATH = "rental.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('DROP TABLE IF EXISTS orders')
    c.execute('DROP TABLE IF EXISTS vehicles')

    c.execute('''
        CREATE TABLE vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            model TEXT NOT NULL,
            power INTEGER NOT NULL,
            range_km INTEGER NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 5,
            max_quantity INTEGER NOT NULL DEFAULT 5
        )
    ''')

    c.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            active INTEGER DEFAULT 1,
            order_code TEXT UNIQUE,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )
    ''')

    vehicles = [
        ('electric_bike', 'E-Bike Pro X1', 250, 40, 80, 5, 5),
        ('electric_bike', 'E-Bike Sport S2', 750, 100, 200, 5, 5),
        ('electric_scooter', 'Scooter Max', 350, 40, 100, 5, 5),
        ('electric_scooter', 'Scooter Ultra', 500, 60, 150, 5, 5)
    ]
    c.executemany(
        'INSERT INTO vehicles (type, model, power, range_km, price, quantity, max_quantity) VALUES (?, ?, ?, ?, ?, ?, ?)',
        vehicles
    )

    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_active   ON orders(active)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_orders_vehicle  ON orders(vehicle_id)")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("База даних успішно ініціалізована!")
