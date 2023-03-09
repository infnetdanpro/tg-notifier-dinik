from wtforms import Form, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length


class NewBotForm(Form):
    bot_name = StringField(
        "Имя бота",
        validators=[InputRequired("Поле обязательное"), Length(min=1, max=128)],
        render_kw={"class": "form-control", "id": "exampleFormControlInput1"},
    )
    bot_key = StringField(
        "Ключ бота",
        validators=[DataRequired(), Length(min=1, max=128)],
        render_kw={"class": "form-control", "id": "exampleFormControlInput2"},
    )
    bot_channels = TextAreaField(
        "Список чатов для пересылки",
        validators=[DataRequired(), Length(min=1, max=1024)],
        render_kw={
            "class": "form-control",
            "id": "exampleFormControlInput3",
            "rows": "3",
        },
    )
