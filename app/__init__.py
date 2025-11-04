# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path

# Initialize SQLAlchemy outside the function
db = SQLAlchemy()

def create_app(config_object='config.Config'):
    """Application factory function."""
    
    app = Flask(__name__, instance_relative_config=True)

    # 1. Load configuration from config.py
    app.config.from_object(config_object)
    
    # 2. Setup the database file path (must be done before db.init_app)
    # The DB_PATH in main.py points to instance/vin.db
    instance_path = Path(app.instance_path)
    instance_path.mkdir(exist_ok=True)
    db_path = instance_path / 'vin.db'
    
    # CRITICAL FIX: Set the URI here on the app config object
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 3. Initialize extensions
    # Now db.init_app(app) can access the required configuration
    db.init_app(app)

    # 4. Import models so SQLAlchemy knows about them (Crucial for db.create_all() in main.py)
    from app.models import country, wmi 

    return app