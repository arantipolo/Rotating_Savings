import os

basedir = os.path.abspath(os.path.dirname(__file__))
database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supersecretkey')  # used for sessions and login security
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///' + os.path.join(basedir, 'app.db') # database location
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # turns off unnecesary overhead tracking
    UPLOAD_FOLDER = os.path.join(basedir, "app", "uploads")  # Uploaded files will be save here
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

