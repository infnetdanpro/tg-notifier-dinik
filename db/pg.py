from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import config

Base = declarative_base()


engine = create_engine(config.db_url)

# # # sync connection
db_session = sessionmaker(bind=engine)()
