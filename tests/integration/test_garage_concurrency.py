import asyncio
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.modules.garage.creation import create_garage_vehicle_link
from app.modules.garage.policy import get_garage_capacity
from app.modules.garage.schemas import GarageVehicleCreate
from app.modules.users.models import User
from app.modules.vehicles.models import GarageMembership, VehicleUser
from tests.integration.test_admin_concurrency import prepare_users
from tests.test_vehicles import vehicle_payload


async def test_concurrent_vehicle_additions_only_allocate_one_free_slot(pg_engine):
    factory = await prepare_users(pg_engine)

    async def create(plate, chassis, renavam):
        async with factory() as session:
            user = await session.get(User, 1)
            await create_garage_vehicle_link(
                session,
                GarageVehicleCreate(
                    **vehicle_payload(plate=plate, chassis=chassis, renavam=renavam)
                ),
                user,
            )

    await asyncio.gather(
        create("ABC1D23", "chassis-one", "11111111111"),
        create("DEF2E34", "chassis-two", "22222222222"),
    )
    async with factory() as session:
        capacity = await get_garage_capacity(session, 1, datetime.now(UTC))
        assert capacity.limit == 1
        assert len(capacity.writable_vehicle_ids) == 1
        assert await session.scalar(select(func.count()).select_from(GarageMembership)) == 2
        assert await session.scalar(select(func.count()).select_from(VehicleUser)) == 2
