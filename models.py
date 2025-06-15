from dataclasses import dataclass
from typing import Optional

@dataclass
class Vehicle:
    id: int
    type: str
    model: str
    power: int
    range_km: int
    price: float
    quantity: int

@dataclass
class Order:
    id: int
    user_id: int
    vehicle_id: int
    active: bool
    rental_period: Optional[str] = None
    start_date: Optional[str] = None