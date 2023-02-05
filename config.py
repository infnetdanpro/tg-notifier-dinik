import os

from dotenv import load_dotenv

load_dotenv(".env", verbose=True)


class Config:
    db_url = os.environ.get(
        "DB_DSN",
        "postgresql://postgres:postgres@localhost:5432/dbdinik",
    )
    PROJECT_PATH = os.getcwd()
    UPLOAD_FOLDER = ["web", "static", "user_uploads"]
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
    EVENTSUB_URL = "https://8cc2-62-4-55-19.eu.ngrok.io"
    APP_ID = "4d8t7cbll7i3bg3ddc533pibisxvaj"
    APP_SECRET = "re91qzx97uyb7gpbnprnz0bu9qj4j1"


config = Config()
