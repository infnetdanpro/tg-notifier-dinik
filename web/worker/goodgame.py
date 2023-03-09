import logging
import multiprocessing as mp
from datetime import datetime
from time import sleep

import httpx
from httpx import Timeout
from sqlalchemy import text

from config import config
from db.pg import db_session
from models.connectors import GoodgameStreams
from web.worker import tools

logger = logging.getLogger(__name__)


def is_streams_is_live(stream_usernames: list[str]) -> dict[str, bool]:
    if not stream_usernames:
        return {}
    stream_usernames = [s.lower() for s in stream_usernames]
    with httpx.Client() as client:
        timeout = Timeout(timeout=59)
        resp = client.post(
            "http://goodgame.ru/api/getchannelstatus?fmt=json",
            data={"id": ",".join(stream_usernames), "fmt": "json"},
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.exception(
                "[%s] Кажется нас забанили или сервис недоступен: %s. Весь респ: %s",
                stream_usernames,
                resp.status_code,
                resp.text,
            )
            return False
        data: dict = resp.json()
        statuses = {}
        for stream_id, stream_info in data.items():
            statuses[stream_info["key"].lower()] = bool(
                stream_info["status"].lower() == "live"
            )
        return statuses


def worker(channels: list[str]):
    # {'stream_1': False, 'stream_2': True, 'stream_3': False, 'non-exists-stream': False}
    all_channels = {c[0].lower(): c[1] for c in channels}

    # {'stream_1': False, 'stream_2': True, 'stream_3': False}
    streams_statuses: dict = is_streams_is_live(
        stream_usernames=[c[0].lower() for c in channels]
    )

    # update statuses for each stream channel is live now or not
    if streams_statuses:
        for channel_name, status in streams_statuses.items():
            db_session.execute(
                text(
                    """
                UPDATE
                    goodgame
                SET is_live_now = :status
                WHERE LOWER(channel_name) = :name
            """
                ),
                params={"name": channel_name, "status": status},
            )
            db_session.commit()

    channels_to_notify: list[str] = []
    for channel_name, new_status in streams_statuses.items():
        old_status = all_channels[channel_name]
        if old_status == new_status:
            continue

        if old_status is False and new_status is True:
            print(channel_name, old_status, new_status)
            # add here notification
            channels_to_notify.append(channel_name)
            # get goodgame ids
    if not channels_to_notify:
        return

    channels_to_notify = tuple(c for c in channels_to_notify)
    goodgame_ids = db_session.execute(
        text(
            """
        SELECT
            id
        FROM goodgame
        WHERE LOWER(channel_name) IN :channels
    """
        ),
        params={"channels": channels_to_notify},
    ).fetchall()

    if not goodgame_ids:
        return

    goodgame_ids = [r[0] for r in goodgame_ids]
    query = """
        INSERT INTO goodgame_notifications (goodgame_id) VALUES
    """
    query_add = []
    for gg_id in goodgame_ids:
        query_add.append(f"({gg_id})")
    query += ", ".join(query_add)

    try:
        db_session.execute(text(query))
        db_session.commit()
        print("Sent for gg.ids", goodgame_ids)
    except Exception as e:
        print(e)
        db_session.rollback()


def main():
    spawn = mp.get_context("spawn")
    i = 0
    # TODO: proxy
    logger.info("Worker starting")
    while True:
        streams_all = db_session.execute(
            text(
                """
            SELECT
                DISTINCT LOWER(channel_name),
                is_live_now
            FROM goodgame
            WHERE is_active IS TRUE
            GROUP BY 1, 2
        """
            )
        ).fetchall()
        if not streams_all:
            # Check fresh records in DB
            sleep(config.app_sleep)
            continue

        data = []
        for channel_name, is_live_now in streams_all:
            if channel_name.startswith("https://goodgame.ru/channel/"):
                channel_name = channel_name.split("/")[4]
                data.append((channel_name, is_live_now))
                continue
            data.append((channel_name, is_live_now))

        for streams in tools.partition(data, 100):
            process = spawn.Process(target=worker, kwargs={"channels": streams})
            process.daemon = True
            process.start()

        sleep(config.app_sleep)
        i += 1
        if i == 100:
            print(f"[{datetime.utcnow()}] Worker still alive")
            logger.info("[%s] Worker still alive: %s", datetime.utcnow())
            i = 0
    logger.info("Worker finished")


if __name__ == "__main__":
    main()
