import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = 'supersecretkey'  # used for sessions and login security
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db') # database location
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # turns off unnecesary overhead tracking
    UPLOAD_FOLDER = os.path.join(basedir, "app", "uploads")  # Uploaded files will be save here
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

