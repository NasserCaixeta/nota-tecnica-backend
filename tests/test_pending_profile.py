from tests.test_auth_users import login, register_user


def test_pending_participant_can_correct_profile_without_granting_access(client):
    register_user(client)
    headers = {"Authorization": f"Bearer {login(client)}"}
    updated = client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={
            "full_name": "Maria Updated",
            "phone": "11999999999",
            "city": "Campinas",
            "state": "sp",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Maria Updated"
    assert updated.json()["state"] == "SP"
    assert updated.json()["participation_status"] == "pending"
    assert updated.json()["is_admin"] is False
    forbidden = client.patch("/api/v1/users/me", headers=headers, json={"is_admin": True})
    assert forbidden.status_code == 422


async def test_rejected_participant_can_resubmit_but_not_self_approve(client, db_session):
    from tests.test_participation_admin import admin_headers

    user = register_user(client)
    own_headers = {"Authorization": f"Bearer {login(client)}"}
    admin = await admin_headers(client, db_session)
    rejected = client.patch(
        f"/api/v1/admin/participants/{user['id']}/review",
        headers=admin,
        json={"decision": "rejected", "expected_version": 1, "reason": "Complete the registration"},
    )
    assert rejected.status_code == 200
    resubmitted = client.post("/api/v1/users/me/resubmit-participation", headers=own_headers)
    assert resubmitted.status_code == 200
    assert resubmitted.json()["participation_status"] == "pending"
    assert resubmitted.json()["participation_version"] == 3
    assert client.get("/api/v1/garage", headers=own_headers).status_code == 403
