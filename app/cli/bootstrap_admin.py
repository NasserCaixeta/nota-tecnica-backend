"""Operational bootstrap; never registered as an HTTP route."""

import argparse
import asyncio

from sqlalchemy import func, select, text

from app.db.session import get_async_session_factory
from app.modules.audit.service import append_audit
from app.modules.users.models import ParticipationStatus, User


async def bootstrap_admin(email: str) -> int:
    async with get_async_session_factory()() as session:
        if session.get_bind().dialect.name == "postgresql":
            await session.execute(text("SELECT pg_advisory_xact_lock(730041)"))
        count = await session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.is_admin.is_(True),
                User.is_active.is_(True),
                User.participation_status == ParticipationStatus.APPROVED,
            )
        )
        if count:
            raise ValueError("An active administrator already exists; use administrative review")
        user = await session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None or not user.is_active:
            raise ValueError("An existing active account is required")
        user.is_admin = True
        user.participation_status = ParticipationStatus.APPROVED
        user.participation_version += 1
        await append_audit(
            session,
            actor_id=None,
            action="admin.bootstrap",
            target_type="user",
            target_id=user.id,
            version=user.participation_version,
            reason="Operational first-administrator bootstrap",
        )
        await session.commit()
        return user.id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        user_id = asyncio.run(bootstrap_admin(args.email))
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Administrator {user_id} provisioned")


if __name__ == "__main__":
    main()
