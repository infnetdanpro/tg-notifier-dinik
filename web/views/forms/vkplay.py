from wtforms import BooleanField, Form, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length


class BasicStreamForm(Form):
    channel_name = StringField(
        "Имя канала",
        validators=[InputRequired("Поле обязательно"), Length(min=1, max=64)],
        render_kw={"class": "form-control", "id": "controlChannelName"},
    )
    channel_link = StringField(
        "Ссылка на канал",
        validators=[InputRequired("Поле обязательно"), Length(min=1, max=128)],
        render_kw={"class": "form-control", "id": "controlChannelLink"},
    )
    action_type = SelectField(
        "Событие",
        choices=[
            ("stream.online", "Стрим онлайн"),
        ],
        render_kw={"class": "form-control", "id": "controlChannelActionType"},
    )

    action_text = TextAreaField(
        "Текст для уведомления",
        default="{{ channel_name }} начал стрим! Заходи: {{ channel_link }}!",
        validators=[DataRequired(), Length(min=1, max=512)],
        render_kw={
            "class": "form-control",
            "id": "controlChannelActionText",
            "rows": 4,
        },
    )
    bot = SelectField(
        "Выберите бота",
        validators=[DataRequired()],
        choices=[],
        default=1,
        render_kw={"class": "form-control", "id": "controlChannelBot"},
    )
    is_active = BooleanField(
        "Активен", render_kw={"class": "form-control", "id": "checkIsActive"}
    )
