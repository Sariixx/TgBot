import asyncio, aiosqlite, uuid
from typing import Optional, List, Any, Tuple
from config import DB_PATH

_WRITE_LOCK = asyncio.Lock()
_DB_CONN: Optional[aiosqlite.Connection] = None
_INIT_LOCK = asyncio.Lock()

async def get_db() -> aiosqlite.Connection:
    global _DB_CONN
    if _DB_CONN:
        return _DB_CONN
    async with _INIT_LOCK:
        if _DB_CONN:
            return _DB_CONN
        _DB_CONN = await aiosqlite.connect(DB_PATH, timeout=30.0)
        await _DB_CONN.execute('PRAGMA busy_timeout = 30000')
        await _DB_CONN.execute('PRAGMA synchronous=NORMAL')
        _DB_CONN.row_factory = aiosqlite.Row
        async with _DB_CONN.execute("PRAGMA table_info(orders)") as cur:
            cols = [row[1] async for row in cur]
        for col in ['username', 'rental_period', 'start_date']:
            if col not in cols:
                await _DB_CONN.execute(f"ALTER TABLE orders ADD COLUMN {col} TEXT")
                await _DB_CONN.commit()
    return _DB_CONN

class VehicleRepository:
    async def get_available_by_type(self, t: str) -> List[Any]:
        db = await get_db()
        sql = 'SELECT id, model, power, range_km, price, quantity FROM vehicles WHERE type=? AND quantity > 0'
        async with db.execute(sql, (t,)) as cur:
            return await cur.fetchall()

    async def _unlock_orphaned(self) -> bool:
        async with _WRITE_LOCK:
            db = await get_db()
            cur = await db.execute(
                """
                UPDATE vehicles
                SET available = 1
                WHERE id IN (
                    SELECT v.id FROM vehicles v
                    LEFT JOIN orders o ON v.id = o.vehicle_id AND o.active = 1
                    WHERE v.available = 0 AND o.id IS NULL
                )
                """
            )
            if cur.rowcount:
                await db.commit()
                return True
            return False

    async def get_available(self) -> List[Any]:
        db = await get_db()
        async with db.execute(
           'SELECT id, model, power, range_km, price, quantity FROM vehicles WHERE quantity > 0'
        ) as cur:
            return await cur.fetchall()

    async def set_availability(self, vehicle_id: int, avail: int) -> bool:
        async with _WRITE_LOCK:
            db = await get_db()
            await db.execute('BEGIN IMMEDIATE')
            await db.execute(
                'UPDATE vehicles SET available=? WHERE id=?', (avail, vehicle_id)
            )
            await db.commit()
            return True

    async def decrease_quantity(self, vehicle_id: int) -> bool:
        async with _WRITE_LOCK:
            db = await get_db()
            await db.execute('BEGIN IMMEDIATE')
            await db.execute('UPDATE vehicles SET quantity = quantity - 1 WHERE id=? AND quantity > 0', (vehicle_id,))
            await db.commit()
            return True

    async def increase_quantity(self, vehicle_id: int) -> bool:
        async with _WRITE_LOCK:
            db = await get_db()
            await db.execute('BEGIN IMMEDIATE')
            await db.execute('UPDATE vehicles SET quantity = MIN(quantity + 1, max_quantity) WHERE id=?', (vehicle_id,))
            await db.commit()
            return True

class OrderRepository:
    async def create_order(self, user_id: int, vehicle_id: int, username: str, rental_period: str, start_date: str) -> Tuple[bool, Optional[str]]:
        async with _WRITE_LOCK:
            db = await get_db()
            await db.execute('BEGIN IMMEDIATE')
            cur = await db.execute('SELECT quantity FROM vehicles WHERE id=?', (vehicle_id,))
            row = await cur.fetchone()
            if not row or row[0] == 0:
                await db.rollback()
                return False, None
            order_code = str(uuid.uuid4())[:8]
            await db.execute(
                'INSERT INTO orders (user_id, vehicle_id, username, active, rental_period, start_date, order_code) VALUES (?, ?, ?, 1, ?, ?, ?)',
                (user_id, vehicle_id, username, rental_period, start_date, order_code)
            )
            await db.execute('UPDATE vehicles SET quantity = quantity - 1 WHERE id=?', (vehicle_id,))
            await db.commit()
            return True, order_code

    async def get_active_orders(self, user_id: int) -> List[Any]:
        db = await get_db()
        async with db.execute('''
            SELECT o.id, v.id, v.model, v.price, o.rental_period, o.start_date, o.order_code
            FROM orders o JOIN vehicles v ON o.vehicle_id=v.id
            WHERE o.user_id=? AND o.active=1
        ''', (user_id,)) as cur:
            return await cur.fetchall()

    async def close_order(self, user_id: int, vehicle_id: int) -> bool:
        async with _WRITE_LOCK:
            db = await get_db()
            await db.execute('BEGIN IMMEDIATE')
            await db.execute(
                'UPDATE orders SET active=0 WHERE user_id=? AND vehicle_id=? AND active=1',
                (user_id, vehicle_id)
            )
            await db.execute('UPDATE vehicles SET quantity = quantity + 1 WHERE id=?', (vehicle_id,))
            await db.commit()
            return True

    async def vehicle_has_active_order(self, vehicle_id: int) -> bool:
        db = await get_db()
        async with db.execute(
            "SELECT 1 FROM orders WHERE vehicle_id=? AND active=1 LIMIT 1", (vehicle_id,)
        ) as cur:
            row = await cur.fetchone()
            return row is not None

    async def force_close_by_vehicle(self, vehicle_id: int) -> None:
        async with _WRITE_LOCK:
            db = await get_db()
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                "UPDATE orders SET active=0 WHERE vehicle_id=? AND active=1",
                (vehicle_id,)
            )
            await db.execute(
                "UPDATE vehicles SET available=1 WHERE id=?",
                (vehicle_id,)
            )
            await db.commit()