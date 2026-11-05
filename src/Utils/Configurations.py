import os

import psycopg
from .config_local import POSTGRES_PASSWORD

class ConfigurationParams:
    host = "localhost"
    port = 5432
    username = "postgres"
    password = POSTGRES_PASSWORD
    database = "nyc_mobility"

    @classmethod
    def connect(cls):
        return psycopg.connect(
            host=cls.host,
            port=cls.port,
            user=cls.username,
            password=cls.password,
            dbname=cls.database,
        )