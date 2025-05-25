import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Récupère l'URL et corrige le format si nécessaire
    raw_database_url = os.getenv('DATABASE_URL') or os.getenv('DATABASE-URL')
    if raw_database_url and raw_database_url.startswith('postgres://'):
        raw_database_url = raw_database_url.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_DATABASE_URI = raw_database_url or 'sqlite:///local.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')

    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_USERNAME')
