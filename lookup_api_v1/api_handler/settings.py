#!/usr/bin python3

"""
Constants
---------

Constants, which are used globally in the API service.

.. warning::
    Do not include secrets in this module. Use environment variables
    instead.

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       23 May 2020
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import re
from datetime import datetime
from typing import Set, Callable, Dict, Pattern, NamedTuple, Any
from string import Template

# 3rd party:

# Internal:
from .types import OrderingType, Transformer

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'MAX_QUERY_PARAMS',
    'DATE_PARAMS',
    'DEFAULT_STRUCTURE',
    'AUTHORISED_ORDERING_PARAMS',
    'DEFAULT_ORDERING',
    'DATA_TYPES',
    'TypePatterns',
    'DBQueries',
    'STRING_TRANSFORMATION',
    'MAX_DATE_QUERIES',
]

MAX_DATE_QUERIES = 1

MAX_QUERY_PARAMS: int = 5

DATE_PARAMS: Set[str] = set()

DEFAULT_STRUCTURE: Dict[str, Any] = {
    "areaType": "areaType",
    "areaCode": "areaCode",
    "areaName": "areaName",
    "destinations": "destinations",
    "parent": "parent",
    "children": "children"
}

AUTHORISED_ORDERING_PARAMS: Set[str] = {
    'areaType',
    'areaCode',
    'areaName'
}

DEFAULT_ORDERING: OrderingType = [
    {"by": "type", "ascending": True},
    {"by": "areaType", "ascending": True},
    {"by": "areaName", "ascending": True},
    {"by": "areaCode", "ascending": True},
]


TypePatterns: Dict[Callable[[str], Any], Pattern] = {
    str: re.compile(r"[a-z]+", re.IGNORECASE),
    int: re.compile(r"\d{1,7}"),
    float: re.compile(r"[0-9.]{1,8}"),
    datetime: re.compile(r"\d{4}-\d{2}-\d{2}")
}

STRING_TRANSFORMATION = {
    'areaType': Transformer(value_fn=str.lower, param_fn="LOWER({})".format),
    'areaCode': Transformer(value_fn=str.upper, param_fn=str),
    'areaName': Transformer(value_fn=str.lower, param_fn="LOWER({})".format),
    'DEFAULT': Transformer(value_fn=lambda x: x, param_fn=lambda x: x)
}


class DBQueries(NamedTuple):
    # noinspection SqlResolve,SqlNoDataSourceInspection
    get_query = Template("SELECT VALUE $template FROM c WHERE $clause_script $ordering")


DATA_TYPES: Dict[str, Callable[[str], Any]] = {
    'type': str,
    'areaType': str,
    'areaCode': str,
    'areaName': str,
    'destinations': list,
    'parent': dict,
    'children': list
}
