import os

basedir = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = "app/static/uploads/"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

class Config:
    UPLOAD_FOLDER = None
    SECRET_KEY = 'supersecretkey'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

