from wtforms import EmailField, Form, PasswordField
from wtforms.validators import InputRequired


class LoginForm(Form):
    email = EmailField("Email", validators=[InputRequired()])
    password = PasswordField(
        "Password",
        [InputRequired()],
    )
