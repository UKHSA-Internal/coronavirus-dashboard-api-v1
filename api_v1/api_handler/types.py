#!/usr/bin python3

"""
Type definitions
----------------

Custom type hint definitions used across the API service.

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       23 May 2020
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from typing import (
    Union, Dict, Any, List,
    NamedTuple, Callable, Tuple,
    BinaryIO, Awaitable
)
from http import HTTPStatus

# 3rd party:
from azure.functions import HttpResponse, HttpRequest

# Internal: 
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
__version__ = "0.0.1"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'StructureType',
    'Numeric',
    'QueryArgument',
    'QueryArguments',
    'QueryResponseType',
    'OrderingType',
    'Transformer',
    'APIHandlerType',
    'APIFunctionType',
    'StringOrNumber',
    'ApiResponse',
    'QueryData'
]


StructureType = Union[Dict[str, Any], List[str]]


Numeric = Union[int, float]

StringOrNumber = Union[Numeric, str]

QueryArgument = Dict[str, Union[str, Numeric]]

QueryArguments = Tuple[QueryArgument]


QueryResponseType = Union[
    List[StructureType],
    Dict[str, Union[str, int, List[StructureType]]],
    str
]


OrderingType = List[Dict[str, Union[str, bool]]]


APIHandlerType = Callable[[HttpRequest, str, str], Awaitable[Tuple[HTTPStatus, dict, str, str]]]

APIFunctionType = Callable[[HttpRequest, str], HttpResponse]


class Transformer(NamedTuple):
    value_fn: Callable[[str], str]
    param_fn: Union[Callable[[str], str], str.format]


class ApiResponse(NamedTuple):
    body: BinaryIO
    status_code: int
    headers: dict


class QueryData(NamedTuple):
    arguments: QueryArguments
    query: Any
