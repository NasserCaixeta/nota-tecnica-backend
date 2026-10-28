"""Seed the schema under test without importing future ORM column defaults."""

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import MetaData, Table


async def insert_legacy_row(connection, table_name, values):
    table = await connection.run_sync(
        lambda sync: Table(table_name, MetaData(), autoload_with=sync)
    )
    data = dict(values)
    for column in ("created_at", "updated_at"):
        if column in table.c:
            data.setdefault(column, datetime.now(UTC))
    if table_name == "users":
        data.setdefault("is_active", True)
    data = {key: value.name if isinstance(value, Enum) else value for key, value in data.items()}
    return (
        await connection.execute(table.insert().values(**data).returning(table.c.id))
    ).scalar_one()
