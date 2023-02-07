from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB

from db.pg import Base


class Webhooks(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True)
    tgbot_id = Column(Integer, ForeignKey("tgbots.id"), nullable=False)
    twitch_id = Column(Integer, ForeignKey("twitch.id"), nullable=False)
    twitch_webhook_id = Column(String)
    twitch_webhook_status = Column(String)
    data = Column(JSONB)
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
