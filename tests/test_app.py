from app.models import Group, User


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
