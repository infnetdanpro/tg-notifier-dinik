import os
from datetime import datetime
from typing import List, Optional

import requests
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch as TwitchService
from werkzeug.datastructures import FileStorage

from config import config
from db.pg import db_session
from models.bots import Bots
from models.connectors import (
    Twitch,
    TwitchActions,
    TwitchActionsAttachments,
    VkPlayLive,
)
from models.webhooks import Webhooks
from web.shared_loop import loop
from web.views.forms.bot import NewBotForm
from web.views.forms.new_twitch import NewTwitchSource, allowed_file
from web.views.forms.vkplay import VKPlayForm

app = Blueprint("panel", __name__)


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


def sync_webhook_statuses():
    auth_resp = requests.post(
        f"https://id.twitch.tv/oauth2/token?client_id={config.APP_ID}&client_secret={config.APP_SECRET}&grant_type=client_credentials&scope="
    )
    bearer = auth_resp.json()["access_token"]
    headers = {"Client-ID": config.APP_ID, "Authorization": f"Bearer {bearer}"}

    webhooks_response = requests.get(
        "https://api.twitch.tv/helix/eventsub/subscriptions", headers=headers
    )
    if webhooks_response.status_code != 200:
        print("Something happened with webhook sync!")
        return

    webhook_statuses = {}
    for row in webhooks_response.json()["data"]:
        webhook_statuses[row["id"]] = row["status"]

    webhook_ids = list(webhook_statuses.keys())
    webhooks_db = (
        db_session.query(Webhooks)
        .filter(Webhooks.twitch_webhook_id.in_(webhook_ids))
        .all()
    )

    bulk_mappings = []
    for webhook_db in webhooks_db:
        bulk_mappings.append(
            {
                "id": webhook_db.id,
                "twitch_webhook_status": webhook_statuses[webhook_db.twitch_webhook_id],
            }
        )
    db_session.bulk_update_mappings(Webhooks, bulk_mappings)
    db_session.commit()


async def get_broadcaster(channel_name: str):
    twitch_service = await TwitchService(config.APP_ID, config.APP_SECRET)
    broadcaster_user = await first(twitch_service.get_users(logins=channel_name))
    return broadcaster_user


def save_file(file: FileStorage, filename: str) -> Optional[str]:
    if file and allowed_file(file.filename):
        filename += "." + file.filename.split(".")[-1]
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
        return filename


@app.route("/panel/")
@login_required
def index():
    return render_template("panel.html", current_user=current_user)


@app.route("/panel/source/twitch/")
@login_required
def twitch_list():
    twitch_sources: List[Twitch] = (
        db_session.query(Twitch)
        .filter(Twitch.author_id == current_user.id)
        .order_by(Twitch.created_at.desc())
        .all()
    )
    if twitch_sources:
        sync_webhook_statuses()

    webhook_statuses = {}
    for twitch in twitch_sources:
        webhook: Webhooks = (
            db_session.query(Webhooks)
            .filter(
                Webhooks.twitch_id == twitch.id, Webhooks.tgbot_id == twitch.tgbot_id
            )
            .first()
        )
        if not webhook:
            continue

        webhook_statuses[
            f"{webhook.twitch_id}_{webhook.tgbot_id}"
        ] = webhook.twitch_webhook_status

    return render_template(
        "panel/panel_list_twitch.html",
        current_user=current_user,
        twitch_sources=twitch_sources,
        webhook_statuses=webhook_statuses,
    )


@app.route("/panel/source/twitch/new/")
@login_required
def new_twitch_source():
    form = NewTwitchSource()
    form.bot.choices = get_bots_choices()
    form_action = url_for("panel.new_twitch_source_post")
    return render_template(
        "panel/panel_form_twitch.html",
        current_user=current_user,
        form=form,
        form_action=form_action,
        is_new=True,
    )


@app.route("/panel/twitch/new/", methods=["POST"])
@login_required
def new_twitch_source_post():
    form = NewTwitchSource(request.form)
    form.bot.choices = get_bots_choices()
    form_action = url_for("panel.new_twitch_source_post")
    if not form.validate():
        return (
            render_template(
                "panel/panel_form_twitch.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
                is_new=True,
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
                "panel/panel_form_twitch.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
                is_new=True,
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
                "panel/panel_form_twitch.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
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
        filename = save_file(file=file, filename=str(str(twitch.id)))
        if not filename:
            flash("Изображение не загружено", category="warning")

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
            "panel/panel_form_twitch.html",
            current_user=current_user,
            form=form,
            form_action=form_action,
            is_new=True,
        )

    flash("Источник успешно добавлен", category="success")
    return redirect(url_for("panel.twitch_list"))


@app.route("/panel/twitch/edit/<int:twitch_id>/")
@login_required
def edit_twitch_source(twitch_id: int):
    twitch: Twitch = db_session.query(Twitch).filter(Twitch.id == twitch_id).first()
    if not twitch:
        flash("Запись не найдена", category="danger")
        return redirect(url_for("panel.twitch_list"))

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
        "panel/panel_form_twitch.html",
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
                "panel/panel_form_twitch.html",
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
            filename = save_file(file=file, filename=str(twitch.id))
            if filename:
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

    except Exception as e:
        print(e)
        flash(
            f"Проблема при обновлении, обратитесь к админу. Ошибка: {e}",
            category="danger",
        )
        db_session.rollback()

    flash("Запись обновлена", category="success")
    return render_template(
        "panel/panel_form_twitch.html",
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
        "panel/panel_list_bots.html", current_user=current_user, bots=user_bots
    )


@app.route("/panel/bots/new/")
@login_required
def new_bots():
    form = NewBotForm()
    form_action = url_for("panel.new_bots_post")

    return render_template(
        "panel/panel_form_bots.html",
        current_user=current_user,
        form=form,
        form_action=form_action,
    )


@app.route("/panel/bots/new/", methods=["POST"])
@login_required
def new_bots_post():
    form = NewBotForm(request.form)
    form_action = url_for("panel.new_bots_post")
    if not form.validate():
        return render_template(
            "panel/panel_form_bots.html",
            current_user=current_user,
            form=form,
            form_action=form_action,
        )
    if tgbot := db_session.query(Bots).filter(Bots.tg_key == form.bot_key.data).first():
        flash(f"Бот с этим ключом уже создан под ID: {tgbot.id}")
        return (
            render_template(
                "panel/panel_form_bots.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
            ),
            409,
        )
    new_tgbot = Bots(
        name=form.bot_name.data,
        tg_key=form.bot_key.data,
        channels=form.bot_channels.data.split(","),
        author_id=current_user.id,
    )

    try:
        db_session.add(new_tgbot)
        db_session.commit()
        flash("Запись создана", category="success")
        return redirect(url_for("panel.list_bots"))
    except Exception as e:
        print(e)
        db_session.rollback()
        flash("При сохранении возникла ошибка, напишите админу", category="danger")
        return (
            render_template(
                "panel/panel_form_bots.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
            ),
            500,
        )


@app.route("/panel/bots/edit/<int:bot_id>/")
@login_required
def edit_bots(bot_id: int):
    bot: Bots = db_session.query(Bots).filter(Bots.id == bot_id).first()
    if not bot:
        flash("Запись не найдена", category="danger")
        return redirect(url_for("panel.list_bots"))

    form_action = url_for("panel.edit_bots_post", bot_id=bot.id)
    form = NewBotForm()
    form.bot_name.data = bot.name
    form.bot_channels.data = ",".join(bot.channels) if bot.channels else ""
    form.bot_key.data = bot.tg_key
    return render_template(
        "panel/panel_form_bots.html",
        current_user=current_user,
        bot=bot,
        form=form,
        form_action=form_action,
    )


@app.route("/panel/bots/edit/<int:bot_id>/", methods=["POST"])
@login_required
def edit_bots_post(bot_id: int):
    bot: Bots = db_session.query(Bots).filter(Bots.id == bot_id).first()
    if not bot:
        flash("Запись не найдена", category="danger")
        return redirect("panel.list_bots")

    form_action = url_for("panel.edit_bots_post", bot_id=bot.id)
    form = NewBotForm(request.form)
    if not form.validate():
        return (
            render_template(
                "panel/panel_form_bots.html",
                current_user=current_user,
                bot=bot,
                form=form,
                form_action=form_action,
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
        "panel/panel_form_bots.html",
        current_user=current_user,
        bot=bot,
        form=form,
        form_action=form_action,
    )


@app.route("/panel/source/twitch/activate/", methods=["POST"])
@login_required
def activate_webhook():
    twitch_id = request.form["twitch_id"]
    tgbot_id = request.form["tgbot_id"]

    # set webhook path
    webhook_url = config.EVENTSUB_URL + f"/webhooks/{twitch_id}/{tgbot_id}/"
    twitch_data: Twitch = (
        db_session.query(Twitch).filter(Twitch.id == twitch_id).first()
    )
    if not twitch_data:
        flash("Ошибка активации пересылки", category="danger")
        return redirect(url_for("panel.twitch_list"))

    # get auth bearer token header
    auth_resp = requests.post(
        f"https://id.twitch.tv/oauth2/token?client_id={config.APP_ID}&client_secret={config.APP_SECRET}&grant_type=client_credentials&scope="
    )
    bearer = auth_resp.json()["access_token"]
    headers = {"Client-ID": config.APP_ID, "Authorization": f"Bearer {bearer}"}
    data = {
        "type": "stream.online",
        "version": "1",
        "condition": {"broadcaster_user_id": str(twitch_data.broadcaster_id)},
        "transport": {
            "method": "webhook",
            "callback": webhook_url,
            "secret": "teikpgfkpthqojstncsu",
        },
    }

    r = requests.post(
        url="https://api.twitch.tv/helix/eventsub/subscriptions",
        headers=headers,
        json=data,
    )
    if r.status_code != 202:
        flash("Ошибка установки пересылки", category="danger")
        return redirect(url_for("panel.twitch_list"))

    hook = r.json()
    webhook_data = Webhooks(
        tgbot_id=tgbot_id,
        twitch_id=twitch_id,
        twitch_webhook_id=hook["data"][0]["id"],
        twitch_webhook_status=hook["data"][0]["status"],
        data=hook,
    )
    db_session.add(webhook_data)
    db_session.commit()

    flash("Пересылка сообщений активирована", category="success")
    return redirect(url_for("panel.twitch_list"))


@app.route("/panel/source/twitch/deactivate/", methods=["POST"])
@login_required
def deactivate_webhook():
    twitch_id = request.form["twitch_id"]
    tgbot_id = request.form["tgbot_id"]

    webhook: Webhooks = (
        db_session.query(Webhooks)
        .filter(Webhooks.twitch_id == twitch_id, Webhooks.tgbot_id == tgbot_id)
        .first()
    )
    if not webhook:
        flash("Деактивация неуспешна, вебхук не найден", category="danger")
        return redirect(url_for("panel.twitch_list"))
    # get enabled webhooks
    auth_resp = requests.post(
        f"https://id.twitch.tv/oauth2/token?client_id={config.APP_ID}&client_secret={config.APP_SECRET}&grant_type=client_credentials&scope="
    )
    bearer = auth_resp.json()["access_token"]
    headers = {"Client-ID": config.APP_ID, "Authorization": f"Bearer {bearer}"}
    subs_resp = requests.delete(
        "https://api.twitch.tv/helix/eventsub/subscriptions",
        params={"id": webhook.twitch_webhook_id},
        headers=headers,
    )
    db_session.delete(webhook)
    db_session.commit()
    if subs_resp.status_code == 204:
        flash(f"Пересылка сообщений деактивирована ({twitch_id})", category="success")
        return redirect(url_for("panel.twitch_list"))

    flash("Что-то пошло не так, обратитесь к админу", category="danger")
    return redirect(url_for("panel.twitch_list"))


@app.route("/panel/source/vkplay/")
@login_required
def vkplay_list():
    limit = request.args.get("limit") or 0
    offset = request.args.get("offset") or 0
    result = db_session.query(VkPlayLive).filter(
        VkPlayLive.author_id == current_user.id
    )

    if limit:
        result = result.limit(limit)
    if offset:
        result = result.offset(offset)
    result = result.order_by(VkPlayLive.id.desc())
    return render_template(
        "panel/panel_list_vkplay.html", current_user=current_user, vkplay_streams=result
    )


@app.route("/panel/source/vkplay/new/")
@login_required
def new_vkplay_source():
    form = VKPlayForm()
    form.bot.choices = get_bots_choices()
    form_action = url_for("panel.new_vkplay_source_post")
    return render_template(
        "panel/panel_form_vkplay.html",
        current_user=current_user,
        form=form,
        form_action=form_action,
        is_new=True,
    )


@app.route("/panel/source/vkplay/new/", methods=["POST"])
@login_required
def new_vkplay_source_post():
    form = VKPlayForm(request.form)
    form.bot.choices = get_bots_choices()
    form_action = url_for("panel.new_vkplay_source_post")

    if not form.channel_link.data.startswith("https://vkplay.live/"):
        flash(
            "Ссылка на канал должна начинаться https://vkplay.live/}", category="danger"
        )
        return render_template(
            "panel/panel_form_vkplay.html",
            current_user=current_user,
            form=form,
            form_action=form_action,
            is_new=True,
        )

    if not form.validate():
        return render_template(
            "panel/panel_form_vkplay.html",
            current_user=current_user,
            form=form,
            form_action=form_action,
            is_new=True,
        )

    action_image_filename = None
    if "action_image" in request.files:
        file = request.files["action_image"]
        if file.filename != "":
            action_image_filename = save_file(
                file=file, filename="vkplay_" + str(current_user.id)
            )
            if not action_image_filename:
                flash("Изображение не загружено", category="warning")

    vkplay = VkPlayLive(
        channel_name=form.channel_name.data,
        author_id=current_user.id,
        channel_link=form.channel_link.data,
        tgbot_id=form.bot.data,
        action_type=form.action_type.data,
        action_text=form.action_text.data,
        action_image=action_image_filename,
    )
    try:
        db_session.add(vkplay)
        db_session.commit()
    except Exception as e:
        print(e)
        db_session.rollback()
        flash("Запись не создана, обратитесь к администратору", category="danger")
        return (
            render_template(
                "panel/panel_form_vkplay.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
                is_new=True,
            ),
            400,
        )

    flash("Источник создан", category="success")
    return redirect(url_for("panel.vkplay_list"))


@app.route("/panel/source/vkplay/edit/<int:vkplay_id>/")
@login_required
def vkplay_edit(vkplay_id: int):
    vkplay: VkPlayLive = (
        db_session.query(VkPlayLive).filter(VkPlayLive.id == vkplay_id).first()
    )
    if not vkplay:
        flash("Стрим не найден", category="danger")
        return redirect(url_for("panel.vkplay_list"))

    form = VKPlayForm()
    form.bot.choices = get_bots_choices()
    form.bot.default = vkplay.tgbot_id
    form.process()

    form.channel_name.data = vkplay.channel_name
    form.channel_link.data = vkplay.channel_link
    form.action_type.data = vkplay.action_type
    form.action_text.data = vkplay.action_text
    form.is_active.data = vkplay.is_active
    form_action = url_for("panel.vkplay_edit_post", vkplay_id=vkplay.id)
    return render_template(
        "panel/panel_form_vkplay.html",
        current_user=current_user,
        form=form,
        form_action=form_action,
        source=vkplay,
    )


@app.route("/panel/source/vkplay/edit/<int:vkplay_id>/", methods=["POST"])
@login_required
def vkplay_edit_post(vkplay_id: int):
    vkplay: VkPlayLive = (
        db_session.query(VkPlayLive).filter(VkPlayLive.id == vkplay_id).first()
    )
    if not vkplay:
        flash("Стрим не найден", category="danger")
        return redirect(url_for("panel.vkplay_list"))

    form = VKPlayForm(request.form)
    form.bot.choices = get_bots_choices()
    form_action = url_for("panel.vkplay_edit_post", vkplay_id=vkplay.id)

    if not form.validate():
        return render_template(
            "panel/panel_form_vkplay.html",
            current_user=current_user,
            form=form,
            form_action=form_action,
            source=vkplay,
        )

    if "action_image" in request.files:
        file = request.files["action_image"]
        if file.filename != "":
            action_image_filename = save_file(
                file=file, filename="vkplay_" + str(current_user.id)
            )
            if not action_image_filename:
                flash("Изображение не загружено", category="warning")
            else:
                vkplay.action_image = action_image_filename

    vkplay.channel_name = form.channel_name.data
    vkplay.author_id = current_user.id
    vkplay.channel_link = form.channel_link.data
    vkplay.tgbot_id = form.bot.data
    vkplay.action_type = form.action_type.data
    vkplay.action_text = form.action_text.data
    vkplay.is_active = form.is_active.data

    try:
        db_session.commit()
    except Exception as e:
        print(e)
        db_session.rollback()
        flash("Запись не обновлена, обратитесь к администратору", category="danger")
        return (
            render_template(
                "panel/panel_form_vkplay.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
                is_new=True,
            ),
            400,
        )
    flash("Запись обновлена", category="success")
    return redirect(url_for("panel.vkplay_list"))
