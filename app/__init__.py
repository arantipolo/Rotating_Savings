from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

# Initialize extensions (no imports from models yet!)
db = SQLAlchemy()
login = LoginManager()
login.login_view = 'main.login'  # blueprint name.login route

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login.init_app(app)

    # Import blueprints AFTER db & login are initialized
    from app.routes import main
    app.register_blueprint(main)

    # Import models AFTER db is initialized
    from app import models

    return app
