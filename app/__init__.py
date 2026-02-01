from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app import routes
    app.register_blueprint(routes.bp)

    with app.app_context():
        db.create_all()
        try:
            db.session.execute(db.text(
                "ALTER TABLE cultivar ADD COLUMN validated BOOLEAN DEFAULT 0"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

    return app
