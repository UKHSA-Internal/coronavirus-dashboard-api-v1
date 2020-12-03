#!/usr/bin python3

"""
API Response
------------

Utilities that are used to prepare and format the API response.

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       23 May 2020
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from functools import wraps
from gzip import compress
from json import dumps
from typing import Callable, Any
from datetime import datetime

# 3rd party:
from azure.functions import HttpResponse, HttpRequest


# Internal:
from .types import APIFunction

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'format_response'
]


def format_response(func: Callable[[HttpRequest], Any]) -> APIFunction:
    """
    Decorator function to process the output of the main API entry point.

    The function, formatted as a tuple of ``(HTTPStatus, dict)`` is dumped
    as JSON, compressed using GZIP, then returned as a `HTTPResponse` with
    the appropriate HTTP status code and headers.

    Headers attached to the response are as follows:

        Content-Type: application/vnd.api_v1+json
        Content-Encoding: gzip
        Cache-Control: max-age=60

    Parameters
    ----------
    func: APIFunction
        A function that returns the following:

            HTTPStatus

    Returns
    -------
    APIFunction
        Decorated function
    """
    @wraps(func)
    def inner(req: HttpRequest) -> HttpResponse:
        code, response, raw_query = func(req)
        data = dumps(response, separators=(",", ":"))
        gzipped_data = compress(data.encode())

        headers = {
            "Content-Type": "application/vnd.phe_internal+json; charset=utf-8",
            "Content-Encoding": "gzip",
        }

        if code < 400:
            headers.update({
                "Cache-Control": "max-age=60",
                "Content-Location": f"/v1/data?{raw_query}",
            })

        return HttpResponse(
            body=gzipped_data,
            status_code=int(code),
            headers=headers
        )

    return inner
