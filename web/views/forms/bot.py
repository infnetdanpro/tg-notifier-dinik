from wtforms import Form, StringField
from wtforms.validators import DataRequired, InputRequired


class NewBotForm(Form):
    bot_name = StringField("Имя бота", validators=[InputRequired("Поле обязательное")])
    bot_key = StringField("Ключ бота", validators=[DataRequired()])
