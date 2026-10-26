from fastapi.testclient import TestClient

from tests.test_auth_users import register_user


def register_approved_user(client: TestClient, **overrides):
    data = register_user(client, **overrides)

    async def approve():
        from app.modules.users.models import ParticipationStatus, User

        session = client.app.state.test_db_session
        user = await session.get(User, data["id"])
        user.participation_status = ParticipationStatus.APPROVED
        await session.commit()

    client.portal.call(approve)
    return data
