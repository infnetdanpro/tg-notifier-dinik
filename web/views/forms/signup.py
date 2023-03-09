from wtforms import EmailField, Form, PasswordField
from wtforms.validators import DataRequired, EqualTo, InputRequired, Length


class SignupForm(Form):
    email = EmailField("Email", validators=[DataRequired(), Length(min=1, max=128)])
    password = PasswordField(
        "New Password",
        [
            InputRequired(),
            EqualTo(
                "confirm_password", message="Passwords must match with Confirm password"
            ),
            Length(min=3),
        ],
    )
    confirm_password = PasswordField("Repeat Password")
