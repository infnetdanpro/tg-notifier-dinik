import os
from datetime import datetime
from typing import Optional

import httpx
from flask_login import current_user
from twitchAPI.helper import first
from twitchAPI.twitch import Twitch as TwitchService
from werkzeug.datastructures import FileStorage

from config import config
from db.pg import db_session
from models.bots import Bots
from models.webhooks import Webhooks
from web.views.forms.new_twitch import allowed_file


def get_bots_choices(current_user_id: int) -> list[tuple[int, str]]:
    bots = (
        db_session.query(Bots)
        .with_entities(Bots.id, Bots.name)
        .filter(Bots.author_id == current_user_id)
        .filter(Bots.is_active.is_(True))
        .order_by(Bots.created_at.desc())
        .all()
    )
    bots_choices = []
    for bot in bots:
        bots_choices.append((bot.id, bot.name))
    return bots_choices


def sync_webhook_statuses():
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

    webhooks_response = httpx.get(
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


def save_file(file: "FileStorage", filename: str) -> Optional[str]:
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
