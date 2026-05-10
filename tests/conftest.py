import pytest

from app import create_app, db
from config import Config


@pytest.fixture()
def app(tmp_path):
    original_database_uri = Config.SQLALCHEMY_DATABASE_URI
    original_secret_key = Config.SECRET_KEY

    Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
    Config.SECRET_KEY = "test-secret-key"

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


@pytest.fixture()
def client(app):
    return app.test_client()
