from wtforms import Form, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired

from config import config


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )


class NewTwitchSource(Form):
    twitch_channel_name = StringField(
        "Имя канала",
        validators=[InputRequired()],
        render_kw={"class": "form-control", "id": "exampleFormControlInput1"},
    )
    twitch_username = StringField(
        "Имя стримера", render_kw={"class": "form-control", "id": "controlUsername"}
    )
    twitch_link = StringField(
        "Ссылка на канал", render_kw={"class": "form-control", "id": "controlLink"}
    )
    twitch_action = SelectField(
        "Выберите действие",
        validators=[DataRequired()],
        choices=[
            ("stream.online", "Стрим онлайн"),
            ("channel.follow", "Новый фолловер (не используется)"),
        ],
        render_kw={"class": "form-control", "id": "exampleFormControlSelect1"},
    )
    twitch_action_text = TextAreaField(
        "Текст для пересылки боту",
        default="{{ username }} начал стрим! Заходи: {{ twitch_link }}!",
        validators=[DataRequired()],
        render_kw={
            "class": "form-control",
            "id": "exampleFormControlTextarea1",
            "rows": "3",
        },
    )

    bot = SelectField(
        "Выберите бота",
        validators=[DataRequired()],
        choices=[],
        default=1,
        render_kw={"class": "form-control", "id": "exampleFormControlSelect2"},
    )
