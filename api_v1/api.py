#!/usr/bin python3

"""
Entry point
-----------

Main API entry point function.

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       23 May 2020
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from urllib.parse import unquote_plus, urlparse
from typing import Any
from http import HTTPStatus

# 3rd party:
from azure.functions import HttpRequest, HttpResponse

# Internal:
from .api_handler import (
    APIException, DEFAULT_ORDERING,
    QueryParser, get_data, format_response
)

try:
    from __app__.storage import StorageClient
except ImportError:
    from storage import StorageClient

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'api'
]


@format_response
async def api_handler(req: HttpRequest, lastUpdateTimestamp: str, seriesDate: str) -> Any:
    """
    API main entry point.

    Parameters
    ----------
    req: HttpRequest

    lastUpdateTimestamp: str

    seriesDate: str

    Returns
    -------
    Any
        HttpResponse via the decorator.

        Direct output is a tuple of HTTPStatus code and a dictionary
        containing the response.
    """
    url = urlparse(req.url)

    ordering = DEFAULT_ORDERING

    query = unquote_plus(url.query)
    logging.info(query)

    formatter = 'json'

    try:
        tokens = QueryParser(query, lastUpdateTimestamp)
        formatter = await tokens.formatter

        logging.debug(tokens)

        response = await get_data(
            req,
            tokens,
            ordering,
            formatter,
            lastUpdateTimestamp,
            seriesDate
        )

        return HTTPStatus.OK, response, url.query, formatter

    except APIException as err:
        response = {
            "response": err.message,
            "status_code": err.code,
            "status": getattr(err.code, 'phrase')
        }
        return err.code, response, url.query, formatter

    except Exception as e:
        # A generic exception may contain sensitive data and must
        # never be included in the response.
        err = HTTPStatus.INTERNAL_SERVER_ERROR
        response = {
            "response": (
                "An internal error occurred whilst processing your request, please "
                "try again. If the problem persists, please report as an issue and "
                "include your request."
            ),
            "status_code": err,
            "status": getattr(err, 'phrase')
        }

        logging.warning(e)

        return err, response, url.query, formatter


async def api(req: HttpRequest, lastUpdateTimestamp: str, seriesDate: str) -> HttpResponse:
    response = await api_handler(req, lastUpdateTimestamp, seriesDate)

    return response
