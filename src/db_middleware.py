# helper functions that perform sql queries directly accessing the database and return results
# that will be used inside functions declared in db.py

import os
from sqlalchemy import create_engine

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)