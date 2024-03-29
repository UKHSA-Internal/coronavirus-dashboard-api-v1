#!/usr/bin python3

"""
Response structure
------------------

Utilities to verify and format the structure of response arrays.

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       23 May 2020
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from json import loads
import re

# 3rd party:

# Internal:
from .exceptions import InvalidStructure
from .constants import DATA_TYPES
from .types import StructureType

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'format_structure'
]


metric_names = set(DATA_TYPES)


async def format_structure(struct: str) -> StructureType:
    """
    Formats the requested structure and prepares it for use in database
    query.

    Parameters
    ----------
    struct: str
        Structure to be used in the response.

    Raises
    ------
    InvalidStructure
        When the structure is neither a ``list`` nor a ``dict``.

    Returns
    -------
    Union[Dict[str, Any], List[str]]
        Formatted response structure ready to be used in the database query.
    """
    struct_json = loads(struct)

    if isinstance(struct_json, dict) and \
            any(isinstance(value, (list, dict)) for value in struct_json.values()):
        raise InvalidStructure()

    pattern = re.compile(r'(?P<db_name>[a-z2356780]{2,75})', re.IGNORECASE)

    logging.info(set(struct_json) - metric_names)

    if isinstance(struct_json, list):
        if len(set(struct_json) - metric_names):
            raise InvalidStructure()
        return struct_json

    if isinstance(struct_json, dict):
        metrics = set(struct_json.values())

        if len(metrics - metric_names):
            raise InvalidStructure()

        if not all(map(pattern.match, struct_json)):
            raise InvalidStructure()
    else:
        raise InvalidStructure()

    return struct_json
