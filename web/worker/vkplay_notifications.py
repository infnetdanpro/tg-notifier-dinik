import logging
import os
from time import sleep

import requests
from sqlalchemy import text as text_

from config import config
from db.pg import db_session
from web.views.webhooks import jinja_env

logger = logging.getLogger(__name__)


def main():
    while True:
        rows = db_session.execute(
            text_(
                """
            SELECT
                vln.id as notification_id,
                t.channels,
                t.tg_key,
                vl.action_text,
                vl.action_image,
                vl.channel_name,
                vl.channel_link
            FROM vkplay_live_notifications vln
            JOIN vkplay_live vl ON vl.id = vln.vkplay_live_id
            JOIN tgbots t on vl.tgbot_id = t.id
            WHERE is_sent IS FALSE
        """
            )
        ).fetchall()

        if not rows:
            continue

        for row in rows:
            (
                notification_id,
                channels,
                tg_key,
                action_text,
                action_image,
                channel_name,
                channel_link,
            ) = row

            tpl = jinja_env.from_string(action_text)
            text = tpl.render(
                {"channel_name": channel_name, "channel_link": channel_link}
            )

            payload = {"text": text, "parse_mode": "html"}
            if action_image:
                file_to_send = os.path.join(os.getcwd(), "web", action_image)
                payload["photo"] = (
                    action_image,
                    open(file_to_send, "rb"),
                )

            is_sent = False
            for channel_id in channels:
                if action_image:
                    try:
                        resp = requests.post(
                            f"https://api.telegram.org/bot{tg_key}/sendPhoto",
                            params={
                                "chat_id": channel_id,
                                "caption": text,
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
                            f"https://api.telegram.org/bot{tg_key}/sendMessage",
                            json=payload,
                        )
                        is_sent = resp.status_code == 200
                    except Exception as e:
                        logger.exception(e)
                if not resp.status_code == 200:
                    logger.exception(
                        "Кажется нас забанили или недоступен ТГ-сервер для бота: %s. Ответ: %s",
                        resp.status_code,
                        resp.text,
                    )
                    continue
            if is_sent:
                try:
                    db_session.execute(
                        text_(
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
