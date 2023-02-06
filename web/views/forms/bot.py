from wtforms import Form, StringField, TextAreaField
from wtforms.validators import DataRequired, InputRequired


class NewBotForm(Form):
    bot_name = StringField(
        "Имя бота",
        validators=[InputRequired("Поле обязательное")],
        render_kw={"class": "form-control", "id": "exampleFormControlInput1"},
    )
    bot_key = StringField(
        "Ключ бота",
        validators=[DataRequired()],
        render_kw={"class": "form-control", "id": "exampleFormControlInput2"},
    )
    bot_channels = TextAreaField(
        "Список чатов для пересылки",
        validators=[DataRequired()],
        render_kw={
            "class": "form-control",
            "id": "exampleFormControlInput3",
            "rows": "3",
        },
    )
