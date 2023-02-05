from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import relationship

from db.pg import Base

# from sqlalchemy.orm import relationship


class Twitch(Base):
    __tablename__ = "twitch"

    id = Column(Integer, primary_key=True)
    channel_name = Column(String, nullable=False)
    broadcaster_id = Column(Integer)
    tgbot_id = Column(Integer, ForeignKey("tgbots.id"))
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
    is_active = Column(Boolean, default=True, server_default=text("true"))
    actions = relationship("TwitchActions", uselist=False)


class TwitchActions(Base):
    __tablename__ = "twitch_actions"

    id = Column(Integer, primary_key=True)
    twitch_id = Column(Integer, ForeignKey("twitch.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_name = Column(String, nullable=False)
    action_text = Column(String)
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
    is_active = Column(Boolean, default=True, server_default=text("true"))
    attachments = relationship("TwitchActionsAttachments", uselist=False)


class TwitchActionsAttachments(Base):
    __tablename__ = "twitch_actions_attachments"

    id = Column(Integer, primary_key=True)
    twitch_action_id = Column(Integer, ForeignKey("twitch_actions.id"), nullable=False)
    attachment_type = Column(String, nullable=False)
    attachment_filename = Column(String, nullable=False)
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
    is_active = Column(Boolean, default=True, server_default=text("true"))
