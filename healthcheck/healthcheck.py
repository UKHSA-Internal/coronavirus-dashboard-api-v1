#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from http import HTTPStatus

# 3rd party:
from azure.functions import HttpRequest, HttpResponse

# Internal: 
try:
    from __app__.database import CosmosDB, Collection
except ImportError:
    from database import CosmosDB, Collection

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'probe'
]


QUERY = """\
SELECT TOP 1 *
FROM c 
WHERE c.type = 'general'\
"""


db_client = CosmosDB(Collection.LOOKUP)


def probe(req: HttpRequest) -> HttpResponse:
    try:
        result = db_client.query(QUERY, params=list()).pop()

        if len(result) > 0:
            if req.method == "GET":
                return HttpResponse("ALIVE", status_code=HTTPStatus.OK.real)

            return HttpResponse(None, status_code=HTTPStatus.NO_CONTENT.real)

        raise RuntimeError("Heath probe DB response was empty.")

    except Exception as err:
        logging.exception(err)
        raise err
