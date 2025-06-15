from db import VehicleRepository, OrderRepository
from typing import Tuple, Optional, List, Any

class RentService:
    def __init__(self):
        self.vehicle_repo = VehicleRepository()
        self.order_repo = OrderRepository()

    async def get_available_vehicles_by_type(self, vehicle_type: str) -> List[Any]:
        return await self.vehicle_repo.get_available_by_type(vehicle_type)

    async def get_available_vehicles(self) -> List[Any]:
        return await self.vehicle_repo.get_available()

    async def create_order(self, user_id: int, vehicle_id: int, username: str, rental_period: str, start_date: str) -> Tuple[bool, Optional[str]]:
        try:
            vehicles = await self.vehicle_repo.get_available()
            vehicle = next((v for v in vehicles if v[0] == vehicle_id), None)
            
            if not vehicle and not await self.order_repo.vehicle_has_active_order(vehicle_id):
                await self.vehicle_repo.set_availability(vehicle_id, 1)
                vehicles = await self.vehicle_repo.get_available()
                vehicle = next((v for v in vehicles if v[0] == vehicle_id), None)
            
            if not vehicle:
                return False, None
                
            return await self.order_repo.create_order(user_id, vehicle_id, username, rental_period, start_date)
        except Exception:
            return False, None

    async def return_vehicle(self, user_id: int, vehicle_id: int) -> Tuple[bool, str]:
        try:
            active_orders = await self.order_repo.get_active_orders(user_id)
            if not any(str(order[1]) == str(vehicle_id) for order in active_orders):
                return False, "Цей транспорт не орендований вами"
            
            await self.vehicle_repo.increase_quantity(vehicle_id)
            await self.order_repo.close_order(user_id, vehicle_id)
            return True, "Оренду скасовано. Дякуємо, що скористались сервісом!"
        except Exception:
            return False, "Сталася помилка при поверненні транспорту. Спробуйте пізніше."

    async def get_user_orders(self, user_id: int) -> List[Any]:
        try:
            return await self.order_repo.get_active_orders(user_id)
        except Exception:
            return []

    async def admin_cancel(self, vehicle_id: int) -> Tuple[bool, str]:
        await self.order_repo.force_close_by_vehicle(vehicle_id)
        return True, "Оренду скасовано адміністратором."