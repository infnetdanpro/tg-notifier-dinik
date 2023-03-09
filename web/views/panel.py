from typing import List

import httpx
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import config
from db.pg import db_session
from models.bots import Bots
from models.connectors import (
    GoodgameStreams,
    Twitch,
    TwitchActions,
    TwitchActionsAttachments,
    VkPlayLive,
)
from models.webhooks import Webhooks
from web.shared_loop import loop
from web.views import tools
from web.views.forms.bot import NewBotForm
from web.views.forms.new_twitch import NewTwitchSource
from web.views.forms.vkplay import BasicStreamForm

app = Blueprint("panel", __name__)


@app.route("/panel/")
@login_required
def index():
    return render_template("panel.html", current_user=current_user)


@app.route("/panel/source/twitch/")
@login_required
def twitch_list():
    limit = request.args.get("limit") or 100
    offset = request.args.get("offset") or 0
    query = (
        db_session.query(Twitch)
        .filter(Twitch.author_id == current_user.id)
        .order_by(Twitch.created_at.desc())
    )
    if limit:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)

    twitch_sources: List[Twitch] = query.all()

    if twitch_sources:
        tools.sync_webhook_statuses()

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
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
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
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
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
        tools.get_broadcaster(form.twitch_channel_name.data)
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
        filename = tools.save_file(file=file, filename=str(str(twitch.id)))
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
    twitch: Twitch = (
        db_session.query(Twitch)
        .filter(Twitch.id == twitch_id)
        .filiter(Twitch.author_id == current_user.id)
        .first()
    )
    if not twitch:
        flash("Запись не найдена", category="danger")
        return redirect(url_for("panel.twitch_list"))

    form = NewTwitchSource()
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
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
    twitch: Twitch = (
        db_session.query(Twitch)
        .filter(Twitch.id == twitch_id, Twitch.author_id == current_user.id)
        .first()
    )
    if not twitch:
        flash("Запись не найдена", category="danger")
        return redirect(f"/panel/twitch/edit/{twitch_id}/")

    form = NewTwitchSource(request.form)
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
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
                tools.get_broadcaster(form.twitch_channel_name.data)
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
            filename = tools.save_file(file=file, filename=str(twitch.id))
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
    bot: Bots = (
        db_session.query(Bots)
        .filter(Bots.id == bot_id, Bots.author_id == current_user.id)
        .first()
    )
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
    bot: Bots = (
        db_session.query(Bots)
        .filter(Bots.id == bot_id, Bots.author_id == current_user.id)
        .first()
    )
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
    auth_resp = httpx.post(
        f"https://id.twitch.tv/oauth2/token",
        params={
            "client_id": config.APP_ID,
            "client_secret": config.APP_SECRET,
            "grant_type": "client_credentials",
            "scope": "",
        },
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

    r = httpx.post(
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
    auth_resp = httpx.post(
        "https://id.twitch.tv/oauth2/token",
        params={
            "client_id": config.APP_ID,
            "client_secret": config.APP_SECRET,
            "grant_type": "client_credentials",
            "scope": "",
        },
    )
    bearer = auth_resp.json()["access_token"]
    headers = {"Client-ID": config.APP_ID, "Authorization": f"Bearer {bearer}"}
    subs_resp = httpx.delete(
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
    limit: int = request.args.get("limit") or 100
    offset: int = request.args.get("offset") or 0
    query = (
        db_session.query(VkPlayLive)
        .filter(VkPlayLive.author_id == current_user.id)
        .order_by(VkPlayLive.id.desc())
    )

    if limit:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    vkplay_streams: List[VkPlayLive] = query.all()
    return render_template(
        "panel/panel_list_streams.html",
        current_user=current_user,
        sources=vkplay_streams,
        source_type="vkplay",
    )


@app.route("/panel/source/vkplay/new/")
@login_required
def new_vkplay_source():
    form = BasicStreamForm()
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
    form_action = url_for("panel.new_vkplay_source_post")
    return render_template(
        "panel/panel_form_stream.html",
        current_user=current_user,
        form=form,
        form_action=form_action,
        is_new=True,
        source_name="VK Play Live",
    )


@app.route("/panel/source/vkplay/new/", methods=["POST"])
@login_required
def new_vkplay_source_post():
    form: BasicStreamForm = BasicStreamForm(request.form)
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
    form_action: str = url_for("panel.new_vkplay_source_post")
    source_name = "VK Play Live"

    if not form.channel_link.data.startswith("https://vkplay.live/"):
        flash(
            "Ссылка на канал должна начинаться https://vkplay.live/}", category="danger"
        )
        return render_template(
            "panel/panel_form_stream.html",
            current_user=current_user,
            form=form,
            form_action=form_action,
            is_new=True,
            source_name=source_name,
        )

    if not form.validate():
        return render_template(
            "panel/panel_form_stream.html",
            current_user=current_user,
            form=form,
            form_action=form_action,
            is_new=True,
            source_name=source_name,
        )

    action_image_filename = None
    if "action_image" in request.files:
        file = request.files["action_image"]
        if file.filename != "":
            action_image_filename = tools.save_file(
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
                "panel/panel_form_stream.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
                is_new=True,
                source_name=source_name,
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

    source_name = "VK Play Live"
    form = BasicStreamForm()
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
    form.bot.default = vkplay.tgbot_id
    form.process()

    form.channel_name.data = vkplay.channel_name
    form.channel_link.data = vkplay.channel_link
    form.action_type.data = vkplay.action_type
    form.action_text.data = vkplay.action_text
    form.is_active.data = vkplay.is_active
    form_action = url_for("panel.vkplay_edit_post", vkplay_id=vkplay.id)
    return render_template(
        "panel/panel_form_stream.html",
        current_user=current_user,
        form=form,
        form_action=form_action,
        source=vkplay,
        source_name=source_name,
    )


@app.route("/panel/source/vkplay/edit/<int:vkplay_id>/", methods=["POST"])
@login_required
def vkplay_edit_post(vkplay_id: int):
    vkplay: VkPlayLive = (
        db_session.query(VkPlayLive)
        .filter(VkPlayLive.id == vkplay_id, VkPlayLive.author_id == current_user.id)
        .first()
    )
    if not vkplay:
        flash("Стрим не найден", category="danger")
        return redirect(url_for("panel.vkplay_list"))

    source_name = "VK Play Live"
    form = BasicStreamForm(request.form)
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
    form_action = url_for("panel.vkplay_edit_post", vkplay_id=vkplay.id)

    if not form.validate():
        return render_template(
            "panel/panel_form_stream.html",
            current_user=current_user,
            form=form,
            form_action=form_action,
            source=vkplay,
            source_name=source_name,
        )

    if "action_image" in request.files:
        file = request.files["action_image"]
        if file.filename != "":
            action_image_filename = tools.save_file(
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
                "panel/panel_form_stream.html",
                current_user=current_user,
                form=form,
                form_action=form_action,
                is_new=True,
                source_name=source_name,
            ),
            400,
        )
    flash("Запись обновлена", category="success")
    return redirect(url_for("panel.vkplay_list"))


@app.route("/panel/source/goodgame/")
def goodgame_list():
    limit = request.args.get("limit") or 100
    offset = request.args.get("offset") or 0
    query = (
        db_session.query(GoodgameStreams)
        .filter(GoodgameStreams.author_id == current_user.id)
        .order_by(GoodgameStreams.id.desc())
    )
    if limit:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)

    goodgame_streams = query.all()

    return render_template(
        "panel/panel_list_streams.html",
        sources=goodgame_streams,
        source_name="GoodGame",
        source_type="goodgame",
    )


@app.route("/panel/source/goodgame/new/")
def new_goodgame_source():
    form = BasicStreamForm()
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
    form_action = url_for("panel.new_goodgame_source_post")
    source_name = "GoodGame"
    return render_template(
        "panel/panel_form_stream.html",
        form=form,
        form_action=form_action,
        source_name=source_name,
        source_type="goodgame",
        is_new=True,
    )


@app.route("/panel/source/goodgame/new/", methods=["POST"])
def new_goodgame_source_post():
    form = BasicStreamForm(request.form)
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
    form_action = url_for("panel.new_goodgame_source_post")
    source_name = "GoodGame"

    if not form.channel_link.data.startswith("https://goodgame.ru/channel/"):
        flash("Канал должен начинаться c https://goodgame.ru/channel/...")
        return render_template(
            "panel/panel_form_stream.html",
            form=form,
            form_action=form_action,
            source_name=source_name,
            source_type="goodgame",
            is_new=True,
        )

    if not form.validate():
        return render_template(
            "panel/panel_form_stream.html",
            form=form,
            form_action=form_action,
            source_name=source_name,
            source_type="goodgame",
            is_new=True,
        )

    gg = GoodgameStreams(
        channel_name=form.channel_name.data,
        channel_link=form.channel_link.data,
        author_id=current_user.id,
        tgbot_id=form.bot.data,
        action_type="stream.online",
        action_text=form.action_text.data,
    )
    try:
        db_session.add(gg)
        db_session.flush()
    except Exception as e:
        db_session.rollback()
        flash(f"Ошибка создания записи: {e}", category="danger")
        return render_template(
            "panel/panel_form_stream.html",
            form=form,
            form_action=form_action,
            source_name=source_name,
            source_type="goodgame",
            is_new=True,
        )

    if "action_image" in request.files:
        file = request.files["action_image"]
        if file.filename != "":
            action_image_filename = tools.save_file(
                file=file, filename="goodgame_" + str(current_user.id)
            )
            if not action_image_filename:
                flash("Изображение не загружено", category="warning")
            else:
                gg.action_image = action_image_filename
    db_session.commit()

    flash("Запись успешно создана", category="success")
    return redirect(url_for("panel.goodgame_list"))


@app.route("/panel/source/goodgame/edit/<int:source_id>/")
def edit_goodgame_source(source_id: int):
    source: GoodgameStreams = (
        db_session.query(GoodgameStreams)
        .filter(GoodgameStreams.id == source_id)
        .filter(GoodgameStreams.author_id == current_user.id)
        .first()
    )
    if not source:
        flash("Ресурс не найден", category="danger")
        return redirect(url_for("panel.goodgame_list"))

    form = BasicStreamForm()
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)
    form.bot.default = source.tgbot_id
    form.process()

    form.channel_name.data = source.channel_name
    form.channel_link.data = source.channel_link
    form.action_type.data = source.action_type
    form.action_text.data = source.action_text
    form.is_active.data = source.is_active

    form_action = url_for("panel.edit_goodgame_source", source_id=source.id)
    return render_template(
        "panel/panel_form_stream.html",
        form=form,
        form_action=form_action,
        source_type="goodgame",
        source_name="GoodGame",
        source=source,
    )


@app.route("/panel/source/goodgame/edit/<int:source_id>/", methods=["POST"])
def edit_goodgame_source_post(source_id: int):
    source: GoodgameStreams = (
        db_session.query(GoodgameStreams)
        .filter(GoodgameStreams.id == source_id)
        .filter(GoodgameStreams.author_id == current_user.id)
        .first()
    )
    if not source:
        flash("Ресурс не найден", category="danger")
        return redirect(url_for("panel.goodgame_list"))

    form_action = url_for("panel.edit_goodgame_source_post", source_id=source.id)
    form = BasicStreamForm(request.form)
    form.bot.choices = tools.get_bots_choices(current_user_id=current_user.id)

    if not form.channel_link.data.startswith("https://goodgame.ru/channel/"):
        flash("Канал должен начинаться c https://goodgame.ru/channel/...")
        return render_template(
            "panel/panel_form_stream.html",
            form=form,
            form_action=form_action,
            source_name="GoodGame",
            source_type="goodgame",
        )

    if not form.validate():
        return render_template(
            "panel/panel_form_stream.html",
            form=form,
            form_action=form_action,
            source_type="goodgame",
            source_name="GoodGame",
            source=source,
        )

    source.channel_name = form.channel_name.data
    source.channel_link = form.channel_link.data
    source.action_text = form.action_text.data
    source.is_active = form.is_active.data
    source.tgbot_id = form.bot.data

    if "action_image" in request.files:
        file = request.files["action_image"]
        if file.filename != "":
            action_image_filename = tools.save_file(
                file=file, filename="goodgame_" + str(current_user.id)
            )
            if not action_image_filename:
                flash("Изображение не загружено", category="warning")
            else:
                source.action_image = action_image_filename

    try:
        db_session.commit()
    except Exception as e:
        flash(f"Возникла проблема при обновлении: {e}", category="warning")
        return render_template(
            "panel/panel_form_stream.html",
            form=form,
            form_action=form_action,
            source_type="goodgame",
            source_name="GoodGame",
            source=source,
        )

    flash("Источник успешно обновлен", category="success")
    return render_template(
        "panel/panel_form_stream.html",
        form=form,
        form_action=form_action,
        source_type="goodgame",
        source_name="GoodGame",
        source=source,
    )
