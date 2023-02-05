from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from db.pg import db_session
from models.user import Users
from web.views.forms.login import LoginForm
from web.views.forms.signup import SignupForm

app = Blueprint("auth", __name__)


@app.route("/")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("panel.index"))
    form = LoginForm()
    return render_template("login.html", form=form)


@app.route("/", methods=["POST"])
def login_post():
    form = LoginForm(request.form)
    if not form.validate():
        return render_template("login.html", form=form), 422
    user: Users = (
        db_session.query(Users)
        .filter(Users.email == form.email.data, Users.is_active.is_(True))
        .first()
    )

    if not user:
        flash("Пользователь не найден", category="danger")
        return render_template("login.html", form=form), 404

    if not check_password_hash(pwhash=user.hashed_pwd, password=form.password.data):
        flash("Пароль неверный", category="danger")
        return render_template("login.html", form=form), 404

    remember = True if request.form.get("remember") else False
    login_user(user, remember=remember)

    return redirect(url_for("panel.index"))


@app.route("/signup/")
def signup_get():
    form = SignupForm()
    return render_template("register.html", form=form)


@app.route("/signup/", methods=["POST"])
def signup_post():
    form = SignupForm(request.form)
    if not form.validate():
        return render_template("register.html", form=form), 422

    if db_session.query(Users).filter(Users.email == request.form.get("email")).first():
        flash("Этот email уже занят другим пользователем", category="danger")
        return render_template("register.html", form=form), 409

    created_user = Users(
        email=form.email.data,
        hashed_pwd=generate_password_hash(password=form.password.data),
    )
    db_session.add(created_user)

    try:
        db_session.commit()
    except Exception as e:
        print(e)
        db_session.rollback()
        flash("Что-то пошло не так, обратитесь к админу", category="danger")
        return redirect(url_for("signup"))

    return redirect(url_for("panel"))


@app.route("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
