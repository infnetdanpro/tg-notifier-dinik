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
    EVENTSUB_URL = os.getenv("PROJECT_DOMAIN", "https://1dc4-62-4-36-186.ngrok.io")

    # client id
    APP_ID = "4d8t7cbll7i3bg3ddc533pibisxvaj"
    # client secret
    APP_SECRET = "re91qzx97uyb7gpbnprnz0bu9qj4j1"
    SERVER_NAME = os.getenv("PROJECT_DOMAIN", "https://1dc4-62-4-36-186.ngrok.io")


config = Config()
