import logging
import os
from time import sleep

import requests
from sqlalchemy import text

from config import config
from db.pg import db_session
from web.views.webhooks import jinja_env

# https://github.com/GoodGame/API/blob/master/Streams/stream_api.md
logger = logging.getLogger(__name__)


def main():
    while True:
        rows = db_session.execute(
            text(
                """
            SELECT
              gn.id,
              g.channel_name,
              g.channel_link,
              g.is_live_now,
              g.action_text,
              g.action_image,
              t.channels,
              t.tg_key
            FROM
              goodgame_notifications gn
              JOIN goodgame g on gn.goodgame_id = g.id
              AND g.is_active IS TRUE
              JOIN tgbots t on g.tgbot_id = t.id 
              AND t.is_active IS TRUE
            WHERE
              gn.is_sent IS FALSE
        """
            )
        ).fetchall()

        if not rows:
            sleep(config.app_sleep)
            continue

        streams = {}
        for row in rows:
            streams[row[0]] = {
                "channel_name": row[1],
                "channel_link": row[2],
                "is_live_now": row[3],
                "action_text": row[4],
                "action_image": row[5],
                "channels": row[6],
                "tg_key": row[7],
            }

        for notification_id, channel_data in streams.items():
            tpl = jinja_env.from_string(channel_data["action_text"])
            tpl_text = tpl.render(
                {
                    "channel_name": channel_data["channel_name"],
                    "channel_link": channel_data["channel_link"],
                }
            )
            payload = {"text": tpl_text, "parse_mode": "html"}

            if channel_data.get("action_image"):
                file_to_send = os.path.join(
                    os.getcwd(), "web", channel_data["action_image"]
                )
                payload["photo"] = (
                    channel_data["action_image"],
                    open(file_to_send, "rb"),
                )

            unique_channels = set()

            for channel_id in channel_data["channels"]:
                unique_channels.add(channel_id)

            is_sent = False
            for channel_id in unique_channels:
                ##########
                if channel_data.get("action_image"):
                    try:
                        resp = requests.post(
                            f"https://api.telegram.org/bot{channel_data['tg_key']}/sendPhoto",
                            params={
                                "chat_id": channel_id,
                                "caption": tpl_text,
                                "parse_mode": "html",
                            },
                            files=payload,
                        )
                        is_sent = resp.status_code == 200
                    except Exception as e:
                        logger.exception(e)
                else:
                    payload["chat_id"] = channel_id
                    try:
                        resp = requests.post(
                            f"https://api.telegram.org/bot{channel_data['tg_key']}/sendMessage",
                            json=payload,
                        )
                        is_sent = resp.status_code == 200
                    except Exception as e:
                        logger.exception(e)
                sleep(1)
                if not resp.status_code == 200:
                    logger.exception(
                        "Кажется нас забанили или недоступен ТГ-сервер для бота: %s. Ответ: %s. payload=%s",
                        resp.status_code,
                        resp.text,
                        payload,
                    )
                    continue
            if is_sent:
                try:
                    db_session.execute(
                        text(
                            """
                        UPDATE goodgame_notifications SET is_sent = TRUE WHERE id = :id
                    """
                        ),
                        params={"id": notification_id},
                    )
                    db_session.commit()
                except Exception as e:
                    logger.exception(
                        "Can't update notification id=%s. Full error: %s",
                        notification_id,
                        e,
                    )
                    db_session.rollback()

        sleep(config.app_sleep)
