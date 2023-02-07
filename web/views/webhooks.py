import os

import requests
from flask import Blueprint, Response, jsonify, request
from jinja2 import Environment

from config import config
from db.pg import db_session
from models.bots import BotLogs, Bots
from models.connectors import Twitch

app = Blueprint("webhooks", __name__)


jinja_env = Environment()


# TODO:
# 1. Сделать кнопку "включения" пересылки
# 2. Сохранять при включении пересылки ивентов в лог таблицу
# 3.


@app.route("/webhooks/<int:twitch_id>/<int:tgbot_id>/", methods=["POST"])
def post_webhooks(twitch_id: int, tgbot_id: int):
    if not all([twitch_id, tgbot_id]):
        return "Missed mandatory fields", 404

    data = request.get_json()

    bot_log = BotLogs(
        tgbot_id=tgbot_id, message_type=data["subscription"]["status"], message=data
    )
    db_session.add(bot_log)
    db_session.commit()

    # First we need to verify webhook url
    if data["subscription"]["status"] == "webhook_callback_verification_pending":
        r = Response()
        r.headers = {"Content-Type": "text/plain"}
        r.data = data["challenge"]
        return r

    if (
        data["subscription"]["status"] == "enabled"
        and data["subscription"]["type"] == "stream.online"
    ):
        twitch: Twitch = db_session.query(Twitch).filter(Twitch.id == twitch_id).first()
        if not twitch:
            return "Not found twitch id", 405

        tgbot: Bots = db_session.query(Bots).filter(Bots.id == tgbot_id).first()
        if not tgbot:
            return "Not found bot id", 406

        # send message to channels
        # get channel_ids
        tpl = jinja_env.from_string(twitch.actions.action_text)
        text = tpl.render(
            {"username": twitch.twitch_username, "twitch_link": twitch.twitch_link}
        )
        payload = {"text": text, "parse_mode": "html"}

        if (
            twitch.actions.attachments
            and twitch.actions.attachments.attachment_type == "image"
        ):
            file_to_send = os.path.join(
                os.getcwd(), "web", twitch.actions.attachments.attachment_filename
            )
            payload["photo"] = (
                twitch.actions.attachments.attachment_filename.split("/")[-1],
                open(file_to_send, "rb"),
            )

        payload["disable_web_page_preview"] = True

        for channel_id in tgbot.channels:
            if payload.get("photo"):
                resp = requests.post(
                    f"https://api.telegram.org/bot{tgbot.tg_key}/sendPhoto",
                    params={
                        "chat_id": channel_id,
                        "caption": text,
                        "parse_mode": "html",
                    },
                    files=payload,
                )
            else:
                payload["chat_id"] = channel_id
                resp = requests.post(
                    f"https://api.telegram.org/bot{tgbot.tg_key}/sendMessage",
                    json=payload,
                )

            bot_log = BotLogs(
                tgbot_id=tgbot_id, message_type="tgmessage", message=resp.json()
            )
            db_session.add(bot_log)
            db_session.commit()

    # get tg bot id
    # {'subscription': {'id': 'f1824bb1-ede5-47c0-b65b-5c69be55082f', 'status': 'enabled', 'type': 'stream.online', 'version': '1', 'condition': {'broadcaster_user_id': '47655518'}, 'transport'
    # : {'method': 'webhook', 'callback': 'https://8cc2-62-4-55-19.eu.ngrok.io/webhooks/danpro_infnet/'}, 'created_at': '2023-02-05T12:53:08.627584519Z', 'cost': 1}, 'event': {'id': '40441147192', 'bro
    # adcaster_user_id': '47655518', 'broadcaster_user_login': 'danpro_infnet', 'broadcaster_user_name': 'danpro_infnet', 'type': 'live', 'started_at': '2023-02-05T12:53:55Z'}}

    return "", 200


@app.route("/webhooks-list/")
def webhooks_list():
    auth_resp = requests.post(
        f"https://id.twitch.tv/oauth2/token?client_id={config.APP_ID}&client_secret={config.APP_SECRET}&grant_type=client_credentials&scope="
    )
    bearer = auth_resp.json()["access_token"]
    headers = {"Client-ID": config.APP_ID, "Authorization": f"Bearer {bearer}"}
    subs_resp = requests.get(
        "https://api.twitch.tv/helix/eventsub/subscriptions", headers=headers
    )
    return jsonify(subs_resp.json())


@app.route('/webhook-unsub/')
def webhook_unsub():
    webhook_id = request.args.get('id')
    auth_resp = requests.post(
        f"https://id.twitch.tv/oauth2/token?client_id={config.APP_ID}&client_secret={config.APP_SECRET}&grant_type=client_credentials&scope="
    )
    bearer = auth_resp.json()["access_token"]
    headers = {"Client-ID": config.APP_ID, "Authorization": f"Bearer {bearer}"}
    subs_resp = requests.delete(
        "https://api.twitch.tv/helix/eventsub/subscriptions", params={'id': webhook_id}, headers=headers
    )
    if subs_resp.status_code == 204:
        return jsonify({'result': 'deleted'})

    return jsonify(subs_resp.json()), subs_resp.status_code
