import os

basedir = os.path.abspath(os.path.dirname(__file__))

# Uses Render's database URL when the app is deployed
# Falls back to the local SQLite database while developing on our machine
database_url = os.environ.get('DATABASE_URL')

# Render gives Postgres URLs in a general format
# SQLAlchemy uses this driver format so it knows to connect with psycopg
if database_url and database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey')  # uses Render secret key when deployed
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///' + os.path.join(basedir, 'app.db') # database location
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # turns off unnecesary overhead tracking
    UPLOAD_FOLDER = os.path.join(basedir, "app", "uploads")  # Uploaded files will be save here
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

