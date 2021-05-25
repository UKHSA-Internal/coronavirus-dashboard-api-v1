#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from http import HTTPStatus
from os import getenv

# 3rd party:
from azure.functions import HttpRequest, HttpResponse
import asyncpg

# Internal:

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'probe'
]


class Connection:
    def __init__(self, conn_str=getenv("POSTGRES_CONNECTION_STRING")):
        self.conn_str = conn_str
        self._connection = asyncpg.connect(self.conn_str, statement_cache_size=0, timeout=60)

    def __await__(self):
        yield from self._connection.__await__()

    def __aenter__(self):
        return self._connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self._connection.close()


async def probe(req: HttpRequest) -> HttpResponse:
    logging.info("Processing healthcheck request")
    try:
        async with Connection() as conn:
            result = await conn.fetchrow("SELECT 1 AS healthcheck")
        # result = db_client.query(QUERY, params=list()).pop()

        if result.get("healthcheck", None) is not None:
            if req.method == "GET":
                return HttpResponse("ALIVE", status_code=HTTPStatus.OK.real)

            return HttpResponse(None, status_code=HTTPStatus.NO_CONTENT.real)

        raise RuntimeError("Heath probe DB response was empty.")

    except Exception as err:
        logging.exception(err)
        raise err
