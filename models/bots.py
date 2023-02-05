from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, text

from db.pg import Base


class Bots(Base):
    __tablename__ = "tgbots"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    tg_key = Column(String, nullable=False, unique=True)
    is_active = Column(Boolean, default=True, server_default=text("true"))
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )


class BotLogs(Base):
    __tablename__ = "tgbots_logs"

    id = Column(Integer, primary_key=True)
    tgbot_id = Column(Integer, ForeignKey("tgbots.id"), nullable=False)
    message = Column(String)
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
