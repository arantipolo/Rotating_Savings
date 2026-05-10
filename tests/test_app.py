from datetime import datetime

from app import db
from app.models import Group, PayoutSchedule, User


def register(client, email="john@example.com", password="password123"):
    return client.post(
        "/register",
        data={
            "full_name": "John Tester",
            "email": email,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=True,
    )


def login(client, email="john@example.com", password="password123"):
    return client.post(
        "/login",
        data={
            "email": email,
            "password": password,
        },
        follow_redirects=True,
    )


def logout(client):
    # Logs the current test user out so another user can be tested cleanly
    return client.get("/logout", follow_redirects=True)


def test_home_page_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Rotating Savings" in response.data


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_user_can_register_and_login(client):
    register_response = register(client)

    assert register_response.status_code == 200
    assert User.query.filter_by(email="john@example.com").first() is not None

    login_response = login(client)

    assert login_response.status_code == 200
    assert b"Welcome John Tester" in login_response.data


def test_duplicate_email_registration_is_handled(client):
    # Makes sure duplicate emails show a friendly message
    # instead of crashing the app with a database error
    register(client)
    response = register(client)

    assert response.status_code == 200
    assert User.query.filter_by(email="john@example.com").count() == 1
    assert b"already exists" in response.data


def test_logged_in_user_can_create_group(client):
    register(client)
    login(client)

    response = client.post(
        "/create_group",
        data={
            "name": "Capstone Savings",
            "amount": "100",
            "members": "4",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert Group.query.filter_by(name="Capstone Savings").first() is not None
    assert b"Capstone Savings" in response.data


def test_user_cannot_view_group_they_do_not_belong_to(client):
    # Creates a group under one user
    # then makes sure another user cannot open it by guessing the URL
    register(client)
    login(client)
    client.post(
        "/create_group",
        data={
            "name": "Owner Only Group",
            "amount": "150",
            "members": "3",
        },
        follow_redirects=True,
    )
    group = Group.query.filter_by(name="Owner Only Group").first()
    logout(client)

    register(client, email="outsider@example.com")
    login(client, email="outsider@example.com")

    response = client.get(f"/group_details/{group.id}")

    assert response.status_code == 403


def test_user_cannot_generate_payouts_for_group_they_do_not_own(client):
    # Makes sure a normal member cannot generate payout schedules
    # because only the group owner should control payout setup
    register(client)
    login(client)
    client.post(
        "/create_group",
        data={
            "name": "Protected Group",
            "amount": "200",
            "members": "4",
        },
        follow_redirects=True,
    )
    group = Group.query.filter_by(name="Protected Group").first()
    logout(client)

    register(client, email="member@example.com")
    login(client, email="member@example.com")
    client.post(f"/join_group/{group.id}", follow_redirects=True)

    response = client.post(f"/generate_payouts/{group.id}")

    assert response.status_code == 403


def test_user_cannot_submit_payment_for_group_they_do_not_belong_to(client):
    # Creates a payout in one group
    # then makes sure an outside user cannot submit payment into that group
    register(client)
    login(client)
    client.post(
        "/create_group",
        data={
            "name": "Payment Protected Group",
            "amount": "75",
            "members": "4",
        },
        follow_redirects=True,
    )
    group = Group.query.filter_by(name="Payment Protected Group").first()
    payout = PayoutSchedule(
        payout_date=datetime.utcnow().date(),
        recipient_id=User.query.filter_by(email="john@example.com").first().id,
        group_id=group.id,
        cycle_number=1,
    )
    db.session.add(payout)
    db.session.commit()
    logout(client)

    register(client, email="stranger@example.com")
    login(client, email="stranger@example.com")

    response = client.post(f"/submit_payment/{payout.id}")

    assert response.status_code == 403
