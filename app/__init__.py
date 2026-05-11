from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import inspect, text
from config import Config
from flask_migrate import Migrate
import click

# Initialize extensions (no imports from models yet!)
db = SQLAlchemy()
login = LoginManager()
login.login_view = 'main.login'  # blueprint name.login route
oauth = OAuth()

migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    #app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER

    # Initialize extensions
    db.init_app(app)
    login.init_app(app)
    oauth.init_app(app)

    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        # Google OAuth client used by the login and register screens
        # The openid profile lets the app receive verified email and display name
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    # Import blueprints AFTER db & login are initialized
    from app.routes import main
    app.register_blueprint(main)

    #print(app.url_map)

    # Import models AFTER db is initialized

    from app import models

    migrate.init_app(app, db)

    # Initializes database tables for the deployed app
    # Render runs this before deployment so registration and groups have tables to write to
    @app.cli.command("init-db")
    def init_db_command():
        with app.app_context():
            db.create_all()
            inspector = inspect(db.engine)
            group_columns = {
                column["name"]
                for column in inspector.get_columns("group")
            }

            # Keeps existing local and Render databases compatible
            # when new group fields are added after tables already exist
            if "max_members" not in group_columns:
                group_table = db.engine.dialect.identifier_preparer.quote("group")
                db.session.execute(
                    text(
                        f"ALTER TABLE {group_table} "
                        "ADD COLUMN max_members INTEGER NOT NULL DEFAULT 15"
                    )
                )
                db.session.commit()
        click.echo("Initialized the database.")

    @app.after_request
    def add_no_cache_headers(response):
        # Stops protected pages from being reused from the browser cache after logout
        # This helps make sure old dashboard data is not visible once the session ends
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    return app
