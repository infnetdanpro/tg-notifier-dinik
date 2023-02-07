import os

import aiohttp
from flask import Blueprint, jsonify, request, Response

from config import config
from db.pg import db_session
from models.bots import BotLogs, Bots
from models.connectors import Twitch

app = Blueprint("webhooks", __name__)

import requests
from jinja2 import Environment
jinja_env = Environment()


# TODO:
# 1. Сделать кнопку "включения" пересылки
# 2. Сохранять при включении пересылки ивентов в лог таблицу
# 3.

def prepare_file(obj):
    """
    returns os.path.basename for a given file

    :param obj:
    :return:
    """
    name = getattr(obj, 'name', None)
    if name and isinstance(name, str) and name[0] != '<' and name[-1] != '>':
        return os.path.basename(name)


def prepare_data(params=None, files=None):
    """
    prepare data for request.

    :param params:
    :param files:
    :return:
    """
    data = {}

    if params:
        for key, value in params.items():
            data[key] = str(value)

    if files:
        for key, f in files.items():
            if isinstance(f, tuple):
                if len(f) == 2:
                    filename, fileobj = f
                else:
                    raise ValueError('Tuple must have exactly 2 elements: filename, fileobj')
            else:
                filename, fileobj = prepare_file(f) or key, f

            data[key] = fileobj

    return data


@app.route("/webhooks/<int:twitch_id>/<int:tgbot_id>/", methods=["POST"])
def post_webhooks(twitch_id: int, tgbot_id: int):
    if not all([twitch_id, tgbot_id]):
        return 'Missed mandatory fields', 404

    # first request is verification?
    # {'subscription': {'id': '342cc30c-f372-4214-8c05-05f82051e1b7', 'status': 'webhook_callback_verification_pending', 'type': 'stream.online', 'version': '1', 'condition': {'broadcaster_user
    # _id': '47655518'}, 'transport': {'method': 'webhook', 'callback': 'https://8cc2-62-4-55-19.eu.ngrok.io/webhooks/danpro_infnet/1/'}, 'created_at': '2023-02-05T12:47:48.374168559Z', 'cost': 1}, 'chal
    # lenge': 'vzHrrSksraBn6fnYrmx4AseZEQnYDn52AaxNEQk7Nfo'}

    data = request.get_json()

    bot_log = BotLogs(
        tgbot_id=tgbot_id, message_type=data["subscription"]["status"], message=data
    )
    db_session.add(bot_log)
    db_session.commit()

    # First we need to verify webhook url
    if data["subscription"]["status"] == "webhook_callback_verification_pending":
        r = Response()
        r.headers = {'Content-Type': 'text/plain'}
        r.data = data["challenge"]
        return r

    if data["subscription"]["status"] == "enabled" and data["subscription"]['type'] == 'stream.online':
        twitch: Twitch = db_session.query(Twitch).filter(Twitch.id == twitch_id).first()
        if not twitch:
            return 'Not found twitch id', 404

        tgbot: Bots = db_session.query(Bots).filter(Bots.id == tgbot_id).first()
        if not tgbot:
            return 'Not found bot id', 404

        # send message to channels
        # get channel_ids
        tpl = jinja_env.from_string(twitch.actions.action_text)
        text = tpl.render({'username': twitch.twitch_username, 'twitch_link': twitch.twitch_link})
        payload = {'text': text, 'parse_mode': 'html'}

        if twitch.actions.attachments and twitch.actions.attachments.attachment_type == 'image':
            file_to_send = os.path.join(os.getcwd(), 'web', twitch.actions.attachments.attachment_filename)
            payload['photo'] = (twitch.actions.attachments.attachment_filename.split('/')[-1], open(file_to_send, 'rb'))

        payload['disable_web_page_preview'] = True

        for channel_id in tgbot.channels:
            if payload.get('photo'):
                resp = requests.post(
                    f'https://api.telegram.org/bot{tgbot.tg_key}/sendPhoto',
                    params={'chat_id': channel_id, 'caption': text, 'parse_mode': 'html'},
                    files=payload
                )
            else:
                payload['chat_id'] = channel_id
                resp = requests.post(
                    f'https://api.telegram.org/bot{tgbot.tg_key}/sendMessage',
                    json=payload
                )

            bot_log = BotLogs(
                tgbot_id=tgbot_id, message_type='tgmessage', message=resp.json()
            )
            db_session.add(bot_log)
            db_session.commit()

    # get tg bot id
    # {'subscription': {'id': 'f1824bb1-ede5-47c0-b65b-5c69be55082f', 'status': 'enabled', 'type': 'stream.online', 'version': '1', 'condition': {'broadcaster_user_id': '47655518'}, 'transport'
    # : {'method': 'webhook', 'callback': 'https://8cc2-62-4-55-19.eu.ngrok.io/webhooks/danpro_infnet/'}, 'created_at': '2023-02-05T12:53:08.627584519Z', 'cost': 1}, 'event': {'id': '40441147192', 'bro
    # adcaster_user_id': '47655518', 'broadcaster_user_login': 'danpro_infnet', 'broadcaster_user_name': 'danpro_infnet', 'type': 'live', 'started_at': '2023-02-05T12:53:55Z'}}

    return "", 200


@app.route("/webhooks-list/")
def unsubscribe_webhooks():
    auth_resp = requests.post(
        f"https://id.twitch.tv/oauth2/token?client_id={config.APP_ID}&client_secret={config.APP_SECRET}&grant_type=client_credentials&scope="
    )
    bearer = auth_resp.json()["access_token"]
    headers = {"Client-ID": config.APP_ID, "Authorization": f"Bearer {bearer}"}
    subs_resp = requests.get(
        "https://api.twitch.tv/helix/eventsub/subscriptions", headers=headers
    )
    return jsonify(subs_resp.json())


if __name__ == "__main__":
    # установка коллбека
    # {'data': [{'id': '4a4cf6f4-3f9b-49eb-9981-339ac3684a08', 'status': 'webhook_callback_verification_pending', 'type': 'stream.online', 'version': '1', 'condition': {'broadcaster_user_id': '47655518'}, 'created_at': '2023-02-05T19:48:33.932778233Z', 'transport': {'method': 'webhook', 'callback': 'https://8cc2-62-4-55-19.eu.ngrok.io/webhooks/danpro_infnet/'}, 'cost': 1}], 'total': 1, 'max_total_cost': 10000, 'total_cost': 1}
    headers = {
        "Client-ID": "4d8t7cbll7i3bg3ddc533pibisxvaj",
        "Content-Type": "application/json",
        "Authorization": "Bearer 6ruey65gvayrn1ap5s1xxu4dfolle6",
    }
    data = {
        "type": "stream.online",
        "version": "1",
        "condition": {"broadcaster_user_id": "47655518"},
        "transport": {
            "method": "webhook",
            "callback": "https://8cc2-62-4-55-19.eu.ngrok.io/webhooks/danpro_infnet2/",
            "secret": "teikpgfkpthqojstncsu",
        },
    }

    r = requests.post(
        url="https://api.twitch.tv/helix/eventsub/subscriptions",
        headers=headers,
        json=data,
    )
    print(r.status_code)
    print(r.json())
