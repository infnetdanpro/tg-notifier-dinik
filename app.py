import os

from flask import Flask
from flask_login import LoginManager
from jinja2 import Environment

from config import config
from db.pg import db_session
from models.user import Users
from web.views.auth import app as auth_blueprint
from web.views.panel import app as panel_blueprint
from web.views.webhooks import app as webhook_blueprint


def create_app() -> "Flask":
    flask_app = Flask(
        __name__, template_folder="web/templates/", static_folder="web/static/"
    )
    flask_app.secret_key = "@#!$23askjdhkash123__#$_#@$//"
    flask_app.config["UPLOADED_PHOTOS_DEST"] = os.path.join(os.getcwd(), "uploads")
    flask_app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    flask_app.config["SERVER_NAME"] = config.SERVER_NAME
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(flask_app)

    flask_app.register_blueprint(auth_blueprint)
    flask_app.register_blueprint(panel_blueprint)
    flask_app.register_blueprint(webhook_blueprint)

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return db_session.query(Users).get(user_id)

    return flask_app


app = create_app()
