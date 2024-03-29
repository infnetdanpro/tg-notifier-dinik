from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from db.pg import Base


class Twitch(Base):
    __tablename__ = "twitch"
    __table_args__ = (UniqueConstraint("channel_name", "tgbot_id"),)

    id = Column(Integer, primary_key=True)
    channel_name = Column(String, nullable=False)
    twitch_username = Column(String)
    twitch_link = Column(String)
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


class VkPlayLive(Base):
    __tablename__ = "vkplay_live"
    __table_args__ = (UniqueConstraint("channel_name", "tgbot_id"),)

    id = Column(Integer, primary_key=True)
    channel_name = Column(String, nullable=False)
    channel_link = Column(String, nullable=False)
    is_live_now = Column(Boolean, default=False, server_default=text("false"))
    is_active = Column(Boolean, default=True, server_default=text("true"))
    author_id = Column(ForeignKey("users.id"), nullable=False)
    tgbot_id = Column(Integer, ForeignKey("tgbots.id"))
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
    action_type = Column(String, nullable=False)
    action_text = Column(String, nullable=True)
    action_image = Column(String, nullable=True)


class VkPlayLiveNotifications(Base):
    __tablename__ = "vkplay_live_notifications"

    id = Column(Integer, primary_key=True)
    vkplay_live_id = Column(Integer, ForeignKey("vkplay_live.id"), nullable=False)
    is_sent = Column(Boolean, default=False, server_default=text("false"))
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )


class GoodgameStreams(Base):
    __tablename__ = "goodgame"
    __table_args__ = (UniqueConstraint("channel_name", "tgbot_id"),)

    id = Column(Integer, primary_key=True)
    channel_name = Column(String, nullable=False)
    channel_link = Column(String, nullable=False)
    is_live_now = Column(Boolean, default=False, server_default=text("false"))
    is_active = Column(Boolean, default=True, server_default=text("true"))
    author_id = Column(ForeignKey("users.id"), nullable=False)
    tgbot_id = Column(Integer, ForeignKey("tgbots.id"))
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
    action_type = Column(String, nullable=False)
    action_text = Column(String, nullable=True)
    action_image = Column(String, nullable=True)


class GoodgameStreamsNotifications(Base):
    __tablename__ = "goodgame_notifications"

    id = Column(Integer, primary_key=True)
    goodgame_id = Column(Integer, ForeignKey("goodgame.id"), nullable=False)
    is_sent = Column(Boolean, default=False, server_default=text("false"))
    created_at = Column(
        DateTime, default=datetime.now, server_default=text("CURRENT_TIMESTAMP")
    )
