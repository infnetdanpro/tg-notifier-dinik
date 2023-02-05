from wtforms import EmailField, Form, PasswordField
from wtforms.validators import DataRequired, InputRequired


class LoginForm(Form):
    email = EmailField("Email", validators=[DataRequired()])
    password = PasswordField(
        "Password",
        [InputRequired()],
    )
