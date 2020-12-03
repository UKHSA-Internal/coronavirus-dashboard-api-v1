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
    NamedTuple, Callable, Tuple
)

# 3rd party:
from azure.functions import HttpResponse

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
    'APIFunction',
    'StringOrNumber'
]


StructureType = Union[Dict[str, Any], List[str]]


Numeric = Union[int, float]

StringOrNumber = Union[Numeric, str]

QueryArgument = Dict[str, Union[str, Numeric]]

QueryArguments = List[QueryArgument]


QueryResponseType = List[StructureType]


OrderingType = List[Dict[str, Union[str, bool]]]


APIFunction = Callable[[Tuple[Any], Dict[str, Any]], HttpResponse]


class Transformer(NamedTuple):
    value_fn: Callable[[str], str]
    param_fn: Union[Callable[[str], str], str.format]
