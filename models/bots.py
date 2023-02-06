from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from db.pg import Base


class Bots(Base):
    __tablename__ = "tgbots"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    tg_key = Column(String, nullable=False, unique=True)
    channels = Column(ARRAY(item_type=String))
    is_active = Column(Boolean, default=True, server_default=text("true"))
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )


class BotLogs(Base):
    __tablename__ = "tgbots_logs"

    id = Column(Integer, primary_key=True)
    tgbot_id = Column(Integer, ForeignKey("tgbots.id"), nullable=False)
    message_type = Column(String)
    message = Column(JSONB)
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
