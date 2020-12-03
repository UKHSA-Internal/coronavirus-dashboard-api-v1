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
from datetime import datetime
from os import getenv

# 3rd party:
from azure.functions import HttpResponse, HttpRequest


# Internal:
from .types import APIHandlerType, APIFunctionType
from .constants import RESPONSE_TYPE, SELF_URL

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'format_response'
]


NOT_AVAILABLE = "N/A"
SERVER_LOCATION_KEY = "SERVER_LOCATION"
SERVER_LOCATION = getenv(SERVER_LOCATION_KEY, NOT_AVAILABLE)


UNIVERSAL_HEADERS = {
    "Content-Encoding": "gzip",
    "server": "PHE API Service (Unix)",
    "Strict-Transport-Security": "max-age=31536000; includeSubdomains; preload",
    "x-frame-options": "deny",
    "x-content-type-options": "nosniff",
    "x-xss-protection": "1; mode=block",
    "referrer-policy": "origin-when-cross-origin, strict-origin-when-cross-origin",
    "content-security-policy": "default-src 'none'; style-src 'self' 'unsafe-inline'",
    "x-phe-media-type": "PHE-COVID19.v1",
    "PHE-Server-Loc": SERVER_LOCATION
}


def format_response(func: APIHandlerType) -> APIFunctionType:
    """
    Decorator function to process the output of the main API entry point.

    The function, formatted as a tuple of ``(HTTPStatus, dict)`` is dumped
    as JSON, compressed using GZIP, then returned as a `HTTPResponse` with
    the appropriate HTTP status code and headers.

    Headers attached to the response are as follows:

        Content-Type:              [RESPONSE TYPE]
        Content-Encoding:          "gzip"
        server:                    "PHE API Service (Unix)"
        strict-transport-security: "max-age=31536000; includeSubdomains; preload"
        x-frame-options:           "deny"
        x-content-type-options:    "nosniff"
        x-xss-protection:          "1; mode=block"
        referrer-policy:           "origin-when-cross-origin, strict-origin-when-cross-origin"
        content-security-policy:   "default-src 'none'; style-src 'self' 'unsafe-inline'"
        x-phe-media-type:          "PHE-COVID19.v1"

    Parameters
    ----------
    func: APIHandlerType
        A function that returns a tuple structured as follows:

            (HTTPStatus, str)

    Returns
    -------
    APIFunctionType
        Decorated function
    """
    @wraps(func)
    async def inner(req: HttpRequest, lastUpdateTimestamp: str, *args, **kwargs) -> HttpResponse:
        code, response, raw_query, formatter = await func(req, lastUpdateTimestamp, *args, **kwargs)

        if len(lastUpdateTimestamp.split('.')[-1].strip("Z")) == 7:
            lastUpdateTimestamp = lastUpdateTimestamp.replace("0Z", "").replace("5Z", "") + "Z"

        data = response
        if isinstance(response, (list, dict)):
            data = dumps(response, separators=(",", ":"))

        # ToDo: This may be performed in APIM.
        # gzipped_data = data.encode()  # compress(data.encode())
        gzipped_data = compress(data.encode())

        timestamp = datetime.strptime(lastUpdateTimestamp, "%Y-%m-%dT%H:%M:%S.%fZ")

        headers = {
            "Content-Type": RESPONSE_TYPE[formatter],
            **UNIVERSAL_HEADERS
        }

        if 'csv' in RESPONSE_TYPE[formatter] and len(data):
            headers['Content-Disposition'] = (
                f'attachment; filename="data_{timestamp.strftime("%Y-%b-%d")}.csv"'
            )
            headers['X-Content-Type-Options'] = 'nosniff'

        if code < 400:
            headers.update({
                "Cache-Control": "public, max-age=90",
                "Content-Location": f"/v1/data?{raw_query}",
                "Last-Modified": timestamp.strftime("%a, %d %b %Y %H:%M:%S GMT")
            })

        if req.method == "HEAD":
            return HttpResponse(
                status_code=204 if code < 400 else int(code),
                headers=headers
            )

        return HttpResponse(
            body=gzipped_data,
            status_code=int(code),
            headers=headers
        )

    return inner
