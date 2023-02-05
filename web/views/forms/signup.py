from wtforms import EmailField, Form, PasswordField
from wtforms.validators import DataRequired, EqualTo, InputRequired


class SignupForm(Form):
    email = EmailField("Email", validators=[DataRequired()])
    password = PasswordField(
        "New Password",
        [
            InputRequired(),
            EqualTo(
                "confirm_password", message="Passwords must match with Confirm password"
            ),
        ],
    )
    confirm_password = PasswordField("Repeat Password")
