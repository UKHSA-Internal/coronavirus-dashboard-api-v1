#!/usr/bin python3

"""
Exceptions for the API
----------------------

Objects in this module contain a ``code`` property that provide the appropriate
HTTP status code for a specific exception. The also contain a ``message`` property
that provides additional information and guidance - either generic or specific
depending on the exception.

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       23 May 2020
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from http import HTTPStatus
from string import Template
from difflib import SequenceMatcher
from typing import Iterable

# 3rd party:

# Internal:
from .constants import DATA_TYPES

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'APIException',
    'InvalidQueryParameter',
    'ExceedsMaxParameters',
    'InvalidStructureParameter',
    'IncorrectQueryValueType',
    'ValueNotAcceptable',
    'InvalidStructure',
    'InvalidQuery',
    'RequestTooLarge',
    'NotAvailable',
    "UnauthorisedRequest",
    "StructureTooLarge",
    "InvalidFormat",
    "BadPagination",
    "MissingFilter"
]


def get_closest_match(value: str, options: Iterable[str]) -> str:
    """
    Finds the closest match to ``value`` in ``options``.

    Parameters
    ----------
    value: str
        Value whose closest match needs to be found.

    options: Iterable[str]
        Options with which to compare ``value``.

    Returns
    -------
    str
        Closest match to ``value`` from ``options``.
    """
    matcher = SequenceMatcher()
    matcher.set_seq1(value)
    max_ratio = 0
    max_ratio_name = str()

    for item in options:
        matcher.set_seq2(item)
        item_ratio = matcher.ratio()
        if item_ratio > max_ratio:
            max_ratio = item_ratio
            max_ratio_name = item

    return max_ratio_name


class APIException(RuntimeError):
    message = str()
    code: HTTPStatus

    def __init__(self, **kwargs):
        self.message = Template(self.message).substitute(**kwargs)


class InvalidQueryParameter(APIException):
    message = (
        "Query parameter '$name' ($name $operator $value) is invalid. "
        "Did you mean '$closest_match'?"
    )
    code = HTTPStatus.UNPROCESSABLE_ENTITY

    def __init__(self, *, name: str, operator: str, value: str, **kwargs):
        super().__init__(
            name=name,
            operator=operator,
            value=value,
            closest_match=get_closest_match(name, DATA_TYPES),
            **kwargs
        )


class ExceedsMaxParameters(APIException):
    message = (
        f"Number of query parameters exceed the maximum of $max_params allowed. "
        "Current query includes $current_total parameters: $parameters"
    )
    code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    def __init__(self, *, max_params: int, current_total: int, parameters: str, **kwargs):
        super().__init__(
            max_params=max_params,
            current_total=current_total,
            parameters=parameters,
            **kwargs
        )


class InvalidStructureParameter(APIException):
    message = (
        "Invalid parameter '$name' in the requested $structure_format structure. "
        "Did you mean '$closest_match'?"
    )
    code = HTTPStatus.NOT_FOUND

    def __init__(self, *, name: str, structure_format: str, **kwargs):
        super().__init__(
            name=name,
            structure_format=structure_format,
            closest_match=get_closest_match(name, DATA_TYPES),
            **kwargs
        )


class IncorrectQueryValueType(APIException):
    message = (
        "The value in query expression '$expression' is invalid. "
        "Expected a $expectation value, got '$actual' instead. See the API "
        "documentations for additional information."
    )
    code = HTTPStatus.NOT_ACCEPTABLE

    def __init__(self, *, expression: str, expectation: str, actual: str, **kwargs):
        super().__init__(
            expression=expression,
            expectation=expectation,
            actual=actual,
            **kwargs
        )


class ValueNotAcceptable(APIException):
    message = (
        "The value in query expression '$expression' does not match the expected "
        "pattern. The value for this '$key' must match the regular expression pattern "
        "'$pattern'. See the API documentations for additional information."
    )
    code = HTTPStatus.EXPECTATION_FAILED

    def __init__(self, *, expression: str, key: str, pattern: str, **kwargs):
        super().__init__(expression=expression, key=key, pattern=pattern, **kwargs)


class InvalidStructure(APIException):
    message = (
        "Invalid structure. The structure must be a flat (non-nested) JSON object. "
        "Make sure you use double quotation marks in the structure."
    )
    code = HTTPStatus.EXPECTATION_FAILED


class InvalidQuery(APIException):
    message = (
        "Invalid Query: the query is either empty or does not conform to the correct "
        "pattern. See the API documentations for additional information."
    )
    code = HTTPStatus.PRECONDITION_FAILED


class RequestTooLarge(APIException):
    message = (
        'You may only include $allowed_max $param_name per request. '
        'Please see the API documentations for additional information.'
    )
    code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    def __init__(self, *, allowed_max: int, param_name: str):
        super().__init__(allowed_max=allowed_max, param_name=param_name)


class StructureTooLarge(APIException):
    message = (
        'You may only request a maximum number of $max_allowed metrics per '
        'request. Current number of metrics in your structure: $current_count '
        '- please reduce the number of metrics and try again.'
    )
    code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    def __init__(self, *, max_allowed: int, current_count: int):
        super().__init__(max_allowed=max_allowed, current_count=current_count)


class NotAvailable(APIException):
    message = (
        "The request was fulfilled. There is currently no data available."
    )
    code = HTTPStatus.NO_CONTENT


class UnauthorisedRequest(APIException):
    message = (
        "Request for unauthorised access to value '$value' ($name $operator $value) "
        "is denied."
    )
    code = HTTPStatus.UNAUTHORIZED


class InvalidFormat(APIException):
    message = (
        "Invalid format: 'latestBy' parameter can only be used "
        "when 'format=json' or 'format=xml'."
    )
    code = HTTPStatus.BAD_REQUEST


class BadPagination(APIException):
    message = (
        "Bad pagination: 'latestBy' parameter cannot be used in conjunction with "
        "the 'page' parameter."
    )
    code = HTTPStatus.BAD_REQUEST


class MissingFilter(APIException):
    message = (
        "Missing filter: The 'areaType' filter is mandatory, but not defined."
    )
    code = HTTPStatus.BAD_REQUEST
