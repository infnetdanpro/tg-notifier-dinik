import os
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch as TwitchService
from werkzeug.utils import secure_filename

from config import config
from db.pg import db_session
from models.bots import Bots
from models.connectors import Twitch, TwitchActions, TwitchActionsAttachments
from web.shared_loop import loop
from web.views.forms.bot import NewBotForm
from web.views.forms.new_twitch import NewTwitchSource, allowed_file

app = Blueprint("panel", __name__)


@app.route("/panel/")
@login_required
def index():
    return render_template("panel.html", current_user=current_user)


@app.route("/panel/sources/")
@login_required
def list_sources():
    twitch_sources = (
        db_session.query(Twitch)
        .filter(Twitch.author_id == current_user.id)
        .order_by(Twitch.created_at.desc())
        .all()
    )
    return render_template(
        "panel_list_sources.html",
        current_user=current_user,
        twitch_sources=twitch_sources,
    )


@app.route("/panel/twitch/new/")
@login_required
def new_twitch_source():
    form = NewTwitchSource()
    form.bot.choices = get_bots_choices()
    return render_template(
        "panel_new_sources.html", current_user=current_user, form=form
    )


def get_bots_choices():
    bots = (
        db_session.query(Bots)
        .filter(Bots.author_id == current_user.id)
        .order_by(Bots.created_at.desc())
        .all()
    )
    bots_choices = []
    for bot in bots:
        bots_choices.append((bot.id, bot.name))
    return bots_choices


async def get_broadcaster(channel_name: str):
    twitch_service = await TwitchService(config.APP_ID, config.APP_SECRET)
    broadcaster_user = await first(twitch_service.get_users(logins=channel_name))
    return broadcaster_user


@app.route("/panel/twitch/new/", methods=["POST"])
@login_required
def new_twitch_source_post():
    form = NewTwitchSource(request.form)
    form.bot.choices = get_bots_choices()
    if not form.validate():
        return (
            render_template(
                "panel_new_sources.html", current_user=current_user, form=form
            ),
            422,
        )

    filename = None

    broadcaster = loop.run_until_complete(
        get_broadcaster(form.twitch_channel_name.data)
    )
    if not broadcaster:
        flash("Ваш broadcaster.id (twitch) не найден", category="danger")
        return (
            render_template(
                "panel_new_sources.html", current_user=current_user, form=form
            ),
            400,
        )
    twitch = Twitch(
        channel_name=form.twitch_channel_name.data,
        broadcaster_id=broadcaster.id,
        twitch_username=form.twitch_username.data,
        twitch_link=form.twitch_link.data,
        author_id=current_user.id,
        tgbot_id=form.bot.data,
    )
    db_session.add(twitch)
    try:
        db_session.flush()
    except Exception as e:
        print(e)
        flash("1 бот может быть привязан только 1 каналу", category="danger")
        db_session.rollback()
        return (
            render_template(
                "panel_new_sources.html", current_user=current_user, form=form
            ),
            400,
        )

    twitch_action = TwitchActions(
        twitch_id=twitch.id,
        author_id=current_user.id,
        action_name=form.twitch_action.data,
        action_text=form.twitch_action_text.data,
    )
    db_session.add(twitch_action)
    db_session.flush()

    if "twitch_action_image" in request.files:
        file = request.files["twitch_action_image"]
        # if user does not select file, browser also
        # submit an empty part without filename
        if file and allowed_file(file.filename):
            filename = str(twitch.id)
            dt = datetime.utcnow().date()
            user_path = os.path.join(
                config.PROJECT_PATH,
                os.path.join(*config.UPLOAD_FOLDER),
                str(dt.year),
                str(dt.month),
                str(dt.day),
                str(current_user.id),
            )
            if not os.path.exists(user_path):
                os.makedirs(user_path)
            split = (
                *config.UPLOAD_FOLDER[1:],
                str(dt.year),
                str(dt.month),
                str(dt.day),
                str(current_user.id),
                filename,
            )
            file.save(os.path.join(user_path, filename))
            filename = "/".join(split)
        else:
            if file.filename != "":
                flash(
                    "Разрешено загружать только изображения в формате: png/jpg/jpeg/gif"
                )
                return (
                    render_template(
                        "panel_new_sources.html", current_user=current_user, form=form
                    ),
                    400,
                )

    if filename:
        # add attachments
        twitch_attachment = TwitchActionsAttachments(
            twitch_action_id=twitch_action.id,
            attachment_type="image",
            attachment_filename=filename,
        )
        db_session.add(twitch_attachment)
        db_session.flush()
    try:
        db_session.commit()
    except Exception as e:
        print(e)
        db_session.rollback()
        flash(message=f"Сохранение не прошло: {e}", category="danger")
        return render_template(
            "panel_new_sources.html", current_user=current_user, form=form
        )

    flash("Источник успешно добавлен", category="success")
    return redirect(f"/panel/twitch/edit/{twitch.id}/")


@app.route("/panel/twitch/edit/<int:twitch_id>/")
@login_required
def edit_twitch_source(twitch_id: int):
    twitch: Twitch = db_session.query(Twitch).filter(Twitch.id == twitch_id).first()
    if not twitch:
        flash("Запись не найдена", category="danger")
        return redirect(url_for("panel.list_sources"))

    form = NewTwitchSource()
    form.bot.choices = get_bots_choices()
    form.bot.default = twitch.tgbot_id
    form.process()

    form.twitch_channel_name.data = twitch.channel_name
    form.twitch_action.data = twitch.actions.action_name
    form.twitch_action_text.data = twitch.actions.action_text
    form.twitch_username.data = twitch.twitch_username
    form.twitch_link.data = twitch.twitch_link

    return render_template(
        "panel_edit_sources.html",
        current_user=current_user,
        form=form,
        source={
            "id": twitch.id,
            "is_active": twitch.is_active,
            "twitch_channel_name": twitch.channel_name,
            "twitch_action_name": twitch.actions.action_name,
            "twitch_action_text": twitch.actions.action_text,
            "image": twitch.actions.attachments,
        },
    )


@app.route("/panel/twitch/edit/<int:twitch_id>/", methods=["POST"])
@login_required
def edit_twitch_source_post(twitch_id: int):
    twitch: Twitch = db_session.query(Twitch).filter(Twitch.id == twitch_id).first()
    if not twitch:
        flash("Запись не найдена", category="danger")
        return redirect(f"/panel/twitch/edit/{twitch_id}/")

    form = NewTwitchSource(request.form)
    form.bot.choices = get_bots_choices()
    if not form.validate():
        return (
            render_template(
                "panel_edit_sources.html",
                current_user=current_user,
                form=form,
                source={
                    "id": twitch.id,
                    "is_active": twitch.is_active,
                    "twitch_channel_name": twitch.channel_name,
                    "twitch_action_name": twitch.actions.action_name,
                    "twitch_action_text": twitch.actions.action_text,
                    "image": twitch.actions.attachments,
                },
            ),
            422,
        )
    try:
        if twitch.channel_name != form.twitch_channel_name.data:
            twitch.broadcaster_id = loop.run_until_complete(
                get_broadcaster(form.twitch_channel_name.data)
            ).id
        twitch.channel_name = form.twitch_channel_name.data
        twitch.is_active = True if request.form.get("is_active") else False
        twitch.actions.action_name = form.twitch_channel_name.data
        twitch.actions.action_text = form.twitch_action_text.data
        twitch.tgbot_id = int(form.bot.data)
        twitch.twitch_username = form.twitch_username.data
        twitch.twitch_link = form.twitch_link.data
        db_session.commit()

        if "twitch_action_image" in request.files:
            file = request.files["twitch_action_image"]
            # if user does not select file, browser also
            # submit an empty part without filename
            if file and allowed_file(file.filename):
                filename = str(twitch.id)
                dt = datetime.utcnow().date()
                user_path = os.path.join(
                    config.PROJECT_PATH,
                    os.path.join(*config.UPLOAD_FOLDER),
                    str(dt.year),
                    str(dt.month),
                    str(dt.day),
                    str(current_user.id),
                )
                if not os.path.exists(user_path):
                    os.makedirs(user_path)
                split = (
                    *config.UPLOAD_FOLDER[1:],
                    str(dt.year),
                    str(dt.month),
                    str(dt.day),
                    str(current_user.id),
                    filename,
                )
                file.save(os.path.join(user_path, filename))
                filename = "/".join(split)
                twitch_attachment = (
                    db_session.query(TwitchActionsAttachments)
                    .filter(
                        TwitchActionsAttachments.twitch_action_id == twitch.actions.id
                    )
                    .first()
                )

                if twitch_attachment:
                    twitch_attachment.attachment_filename = filename
                    db_session.commit()
                else:
                    twitch_attachment = TwitchActionsAttachments(
                        twitch_action_id=twitch.actions.id,
                        attachment_filename=filename,
                        attachment_type="image",
                    )
                    db_session.add(twitch_attachment)
                    db_session.commit()

            else:
                if file.filename != "":
                    flash(
                        "Разрешено загружать только изображения в формате: png/jpg/jpeg/gif"
                    )

    except Exception as e:
        print(e)
        flash(
            f"Проблема при обновлении, обратитесь к админу. Ошибка: {e}",
            category="danger",
        )
        db_session.rollback()

    flash("Запись обновлена", category="success")
    return render_template(
        "panel_edit_sources.html",
        current_user=current_user,
        form=form,
        source={
            "id": twitch.id,
            "is_active": twitch.is_active,
            "twitch_channel_name": twitch.channel_name,
            "twitch_action_name": twitch.actions.action_name,
            "twitch_action_text": twitch.actions.action_text,
            "image": twitch.actions.attachments,
        },
    )


@app.route("/panel/bots/")
@login_required
def list_bots():
    user_bots = (
        db_session.query(Bots)
        .filter(Bots.author_id == current_user.id)
        .order_by(Bots.created_at.desc())
        .all()
    )
    return render_template(
        "panel_list_bots.html", current_user=current_user, bots=user_bots
    )


@app.route("/panel/bots/new/")
@login_required
def new_bots():
    form = NewBotForm()
    return render_template("panel_new_bots.html", current_user=current_user, form=form)


@app.route("/panel/bots/new/", methods=["POST"])
@login_required
def new_bots_post():
    form = NewBotForm(request.form)
    if not form.validate():
        return render_template(
            "panel_new_bots.html", current_user=current_user, form=form
        )

    if tgbot := db_session.query(Bots).filter(Bots.tg_key == form.bot_key.data).first():
        flash(f"Бот с этим ключом уже создан под ID: {tgbot.id}")
        return (
            render_template(
                "panel_new_bots.html", current_user=current_user, form=form
            ),
            409,
        )

    new_tgbot = Bots(
        name=form.bot_name.data,
        tg_key=form.bot_key.data,
        channels=form.bot_channels.data.split(","),
        author_id=current_user.id,
    )
    db_session.add(new_tgbot)
    try:
        db_session.commit()
    except Exception as e:
        print(e)
        db_session.rollback()
        flash("При сохранении возникла ошибка, напишите админу", category="danger")
        return (
            render_template(
                "panel_new_bots.html", current_user=current_user, form=form
            ),
            500,
        )

    flash("Запись создана", category="success")
    return render_template("panel_new_bots.html", current_user=current_user, form=form)


@app.route("/panel/bots/edit/<int:bot_id>/")
@login_required
def edit_bots(bot_id: int):
    bot: Bots = db_session.query(Bots).filter(Bots.id == bot_id).first()
    if not bot:
        flash("Запись не найдена", category="danger")
        return redirect(url_for("panel.list_bots"))

    form = NewBotForm()
    form.bot_name.data = bot.name
    form.bot_channels.data = ",".join(bot.channels) if bot.channels else ""
    form.bot_key.data = bot.tg_key
    return render_template(
        "panel_edit_bots.html", current_user=current_user, bot=bot, form=form
    )


@app.route("/panel/bots/edit/<int:bot_id>/", methods=["POST"])
@login_required
def edit_bots_post(bot_id: int):
    bot: Bots = db_session.query(Bots).filter(Bots.id == bot_id).first()
    if not bot:
        flash("Запись не найдена", category="danger")
        return redirect("panel.list_bots")

    form = NewBotForm(request.form)
    if not form.validate():
        return (
            render_template(
                "panel_edit_bots.html", current_user=current_user, bot=bot, form=form
            ),
            422,
        )

    bot.name = form.bot_name.data
    bot.tg_key = form.bot_key.data
    bot.channels = form.bot_channels.data.split(",") if form.bot_channels.data else []
    bot.is_active = True if request.form.get("is_active") else False
    db_session.commit()

    flash("Запись обновлена", category="success")
    return render_template(
        "panel_edit_bots.html", current_user=current_user, bot=bot, form=form
    )


@app.route("/panel/source/twitch/activate/", methods=["POST"])
@login_required
def activate_webhook():
    tgbot_id = int(request.form["tgbot_id"])
    twitch_id = int(request.form["twitch_id"])

    flash("Пересылка сообщений активирована", category="success")
    return redirect(url_for("panel.list_sources"))
