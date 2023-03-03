import asyncio
import logging
import multiprocessing as mp
from datetime import datetime
from time import sleep
from typing import Dict, List, Tuple

import httpx
from httpx import Timeout
from sqlalchemy import text

from config import config
from db.pg import db_session

logger = logging.getLogger(__name__)


def partition(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


async def is_stream_is_live(stream_username: str) -> bool:
    async with httpx.AsyncClient() as client:
        timeout = Timeout(timeout=59)
        resp = await client.get(
            f"https://api.vkplay.live/v1/blog/{stream_username}/public_video_stream?from=layer",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.exception(
                "Кажется нас забанили или сервис недоступен: %s. Весь респ: %s",
                resp.status_code,
                resp.text,
            )
            return False
        data = resp.json()
        return bool(data.get("isOnline"))


def run_coros(loop, tasks: Dict):
    row_ids = []
    coros = []

    for row_id, coro in tasks.items():
        row_ids.append(row_id)
        coros.append(coro)

    responses = loop.run_until_complete(asyncio.gather(*coros))
    results = {(a[0], a[1]) for a in list(zip(row_ids, responses))}
    return results


def worker(channels: List[Tuple[str, bool]]):
    if not channels:
        return False
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    origin_states = set()
    for channel in channels:
        origin_states.add((channel[0], channel[1]))

    coros = {}
    for channel in channels:
        # TODO: PASS PROXY
        coros[channel[0]] = is_stream_is_live(stream_username=channel[0])

    new_states = run_coros(loop=loop, tasks=coros)
    diff = new_states - origin_states
    if not diff:
        return

    need_to_notify = []
    for channel_name, is_live_now in diff:
        try:
            result = db_session.execute(
                text(
                    """
                UPDATE vkplay_live
                SET is_live_now = :is_live_now
                WHERE channel_link = :channel_link
                RETURNING id
            """
                ),
                params={
                    "channel_link": f"https://vkplay.live/{channel_name}",
                    "is_live_now": is_live_now,
                },
            ).fetchone()
            db_session.commit()
            if is_live_now and result:
                need_to_notify.append(result[0])
        except Exception as e:
            logger.exception("Error: %s", e)
            db_session.rollback()
            return

    if not need_to_notify:
        return

    query = "INSERT INTO vkplay_live_notifications (vkplay_live_id) VALUES "
    insert_values = []
    for value in need_to_notify:
        insert_values.append(f"({value})")
    query += ", ".join(insert_values)
    try:
        db_session.execute(text(query))
        db_session.commit()
    except Exception as e:
        logger.exception("Error saving notifications vkplay: %s", e)
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
                DISTINCT LOWER(channel_link),
                is_live_now
            FROM vkplay_live
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
        for channel_link, is_live_now in streams_all:
            channel_stream_name = channel_link.split(".")[1].split("/")[1]
            data.append((channel_stream_name, is_live_now))

        for streams in partition(data, 100):
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
