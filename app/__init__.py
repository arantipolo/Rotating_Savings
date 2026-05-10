from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
from flask_migrate import Migrate
import click

# Initialize extensions (no imports from models yet!)
db = SQLAlchemy()
login = LoginManager()
login.login_view = 'main.login'  # blueprint name.login route

migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    #app.config["UPLOAD_FOLDER"] = Config.UPLOAD_FOLDER

    # Initialize extensions
    db.init_app(app)
    login.init_app(app)

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
