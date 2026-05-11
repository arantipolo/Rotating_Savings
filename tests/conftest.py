import pytest

from app import create_app, db
from config import Config


@pytest.fixture()
def app(tmp_path):
    original_database_uri = Config.SQLALCHEMY_DATABASE_URI
    original_secret_key = Config.SECRET_KEY
    original_google_client_id = Config.GOOGLE_CLIENT_ID
    original_google_client_secret = Config.GOOGLE_CLIENT_SECRET

    Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
    Config.SECRET_KEY = "test-secret-key"
    # Tests should not depend on private local OAuth credentials from .env
    # This keeps the fallback login behavior predictable on every machine
    Config.GOOGLE_CLIENT_ID = None
    Config.GOOGLE_CLIENT_SECRET = None

    flask_app = create_app()
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )

    try:
        with flask_app.app_context():
            db.create_all()
            yield flask_app
            db.session.remove()
            db.drop_all()
    finally:
        Config.SQLALCHEMY_DATABASE_URI = original_database_uri
        Config.SECRET_KEY = original_secret_key
        Config.GOOGLE_CLIENT_ID = original_google_client_id
        Config.GOOGLE_CLIENT_SECRET = original_google_client_secret


@pytest.fixture()
def client(app):
    return app.test_client()
