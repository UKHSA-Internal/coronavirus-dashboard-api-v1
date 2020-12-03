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
from os import getenv
from datetime import datetime
from typing import Set, Callable, Dict, Pattern, NamedTuple, Any, List
from string import Template

# 3rd party:

# Internal:
try:
    from .types import OrderingType, Transformer
except ImportError:
    from lookup_api_v1.types import OrderingType, Transformer

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

PARTITION_KEY = ''

DEFAULT_STRUCTURE: Dict[str, Any] = {
    "areaType": "areaType",
    "areaCode": "areaCode",
    "areaName": "areaName",
    "destinations": "destinations",
    "parent": "parent",
    "children": "children"
}

RESPONSE_TYPE = {
    "xml": "application/vnd.PHE-COVID19.v1+json; charset=utf-8",
    "json": "application/vnd.PHE-COVID19.v1+json; charset=utf-8",
    "csv": "text/csv; charset=utf-8"
}


AUTHORISED_ORDERING_PARAMS: Set[str] = {
    'areaType',
    'areaCode',
    'areaName'
}

RESTRICTED_PARAMETER_VALUES: Dict[str, List[str]] = dict()

PAGINATION_PATTERN: Pattern = re.compile(r'(page=(\d{,3}))')

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

REPORT_DATE_PARAM_NAME = None

MAX_ITEMS_PER_RESPONSE = 1000


class DatabaseCredentials(NamedTuple):
    host = getenv('AzureCosmosHost')
    key = getenv('AzureCosmosKey')
    db_name = getenv('AzureCosmosDBName')
    data_collection = 'lookup'


class DBQueries(NamedTuple):
    # noinspection SqlResolve,SqlNoDataSourceInspection
    data_query = Template("""\
SELECT  VALUE $template 
FROM    c 
WHERE   c.type = @type
    AND $clause_script 
$ordering
""".replace("\n", " "))

    # Query assumes that the data is ordered (descending) by date.
    # noinspection SqlResolve,SqlNoDataSourceInspection
    latest_date_for_metric = Template("")

    # noinspection SqlResolve,SqlNoDataSourceInspection
    exists = Template("""\
SELECT  TOP 1 VALUE (1)
FROM    c 
WHERE   c.type = @type
    AND $clause_script 
$ordering
    """.replace("\n", " "))


DATA_TYPES: Dict[str, Callable[[str], Any]] = {
    'type': str,
    'areaType': str,
    'areaCode': str,
    'areaName': str,
    'destinations': list,
    'parent': dict,
    'children': list
}
