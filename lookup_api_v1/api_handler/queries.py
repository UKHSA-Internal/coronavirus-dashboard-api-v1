#!/usr/bin python3

"""
<Description of the programme>

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       23 May 2020
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from datetime import datetime
import re
from hashlib import blake2b
from typing import Tuple, Union
from json import loads
from urllib.parse import unquote_plus, unquote

# 3rd party:

# Internal:
from .settings import (
    DATA_TYPES, TypePatterns, MAX_QUERY_PARAMS,
    STRING_TRANSFORMATION, MAX_DATE_QUERIES,
    DEFAULT_STRUCTURE,
    DATE_PARAMS
)

from .exceptions import (
    IncorrectQueryValueType, InvalidQueryParameter,
    ExceedsMaxParameters, InvalidQuery, ValueNotAcceptable,
    RequestTooLarge
)

from .types import QueryArguments, StringOrNumber

from .structure import format_structure

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'QueryParser'
]


def convert_value_type(name: str, operator: str, value: str) -> StringOrNumber:
    """
    Converts ``value`` to the type expected by the database.

    The function additionally ensures that the value conforms to the expected
    pattern and is authorised for disclosure.

    Parameters
    ----------
    name: str
        Raw parameter name (left of the operator).

    operator: str
        Expression operator.

    value: str
        Raw expression value (right of the operator).

    Raises
    ------
    ValueNotAcceptable
        ``value`` does not match the expected pattern.

    InvalidQueryParameter
        Query parameter does not exist in the database. If it does, then it may
        not have been defined in `DATA_TYPES` and is therefore excluded.

    IncorrectQueryValueType
        Parameter value is not of the expected type, and cannot be converted.

    Returns
    -------
    StringOrNumber
        Value, formatted as required by the database.
    """
    expression = f'{name} {operator} {value}'

    try:
        dtype = DATA_TYPES[name]
        pattern = TypePatterns[dtype]
        found = pattern.search(value)

        if not found:
            # Value does not match the expected pattern.
            raise ValueNotAcceptable(
                expression=expression,
                key=name,
                pattern=pattern.pattern
            )

        # Value matches the pattern - if it is a date, we
        # do not change the type and return the existing
        # str value; otherwise we return value that is
        # converted to the appropriate type (e.g. str, int)
        # because the database query is sensitive to str,
        # int or floating point formats.
        if dtype is datetime:
            return f"{value}T00:00:00.000000Z"
        else:
            return dtype(value)

    except KeyError:
        raise InvalidQueryParameter(
            name=name,
            operator=operator,
            value=value
        )

    except TypeError:
        raise IncorrectQueryValueType(
            expression=expression,
            expectation=type(dtype).__name__,
            actual=value
        )


class QueryParser:
    """
    Parses the URL queries and provides instance attributes that may be
    fed to the database.

    The instance properties are:

    Properties
    ----------
    clause_script: str
        String value, prepared to be inserted in front of the ``WHERE`` clause.

    arguments: QueryArguments
        A list of dictionaries, formatted as follows:

            {
                'name': '@nameUsedInQuery',
                'value': [Queried value]
            }
    """

    pattern = re.compile(
        r'^(?P<argument>.*)$',
        flags=re.IGNORECASE
    )

    structure_pattern = re.compile(
        r'(&?structure=(.+))(&|$)',
        flags=re.IGNORECASE
    )
    filter_pattern = re.compile(
        r'filters=([^&]+)(&|$)',
        flags=re.IGNORECASE
    )
    latest_by = re.compile(
        r'(&?latestBy=([a-z]{2,40}))(&|$)',
        flags=re.IGNORECASE
    )
    format_as = re.compile(
        r'(&?format=(json|csv|xml))(&|$)',
        flags=re.IGNORECASE
    )
    token_pattern = re.compile(
        r'''
            (
                (?P<name>[a-z]{2,40})
                (?P<operator>[<>!]?=?)
                (?P<value>[a-z0-9.\-\s"]{1,50})
                (?P<connector>[;|]?)
            )
        ''',
        flags=re.VERBOSE | re.IGNORECASE
    )

    def __init__(self, query: str):
        """
        Parameters
        ----------
        query: str
            URL query string.
        """
        self._query = query
        self._token = str()
        self.structure: str = self.extract_structure()
        self.arguments, self.clause_script = self._process()

    def extract_structure(self) -> str:
        structure = DEFAULT_STRUCTURE
        found = self.structure_pattern.search(self._query)

        if found:
            raw_json = found.group(2)
            self._query = self._query.replace(found.group(1), str())
            unquoted = unquote_plus(raw_json)
            structure = loads(unquoted)

        return format_structure(structure)

    def extract_content(self, content: str) -> Tuple[QueryArguments, str]:
        """

        Parameters
        ----------
        content: str

        Raises
        ------
        ExceedsMaxParameters

        InvalidQuery

        Returns
        -------
        Tuple[QueryArguments, str]
        """
        query = str()
        arguments = list()
        param_names = list()

        filters = self.filter_pattern.search(content)

        if filters is None:
            filters_value = str()
        else:
            filters_value = unquote(unquote_plus(filters.group(1)))

        for args in self.token_pattern.finditer(filters_value):
            name, operator, value = (
                args.group("name"),
                args.group("operator"),
                args.group("value")
            )

            param_names.append(name)

            transformer = STRING_TRANSFORMATION['DEFAULT']
            transformer = STRING_TRANSFORMATION.get(name, transformer)

            value = convert_value_type(name, operator, value)
            param_name = transformer.param_fn(f'c.{name}')

            hash_key = blake2b(args.group(0).encode(), digest_size=6).hexdigest()

            query += f'{param_name} {operator} @{name}{hash_key}'

            arguments.append({
                "name": f'@{name}{hash_key}',
                "value": transformer.value_fn(value),
            })

            connector = args.group("connector")
            if connector == ";":
                query += " AND "
            elif connector == "|":
                query += " OR "

        current_total = len(arguments)

        if current_total > MAX_QUERY_PARAMS:
            raise ExceedsMaxParameters(
                current_total=current_total,
                max_params=MAX_QUERY_PARAMS,
                parameters=str(param_names)
            )
        elif not current_total:
            raise InvalidQuery()

        query += " AND c.type = @type"
        arguments.append({
            "name": "@type",
            "value": "general"
        })

        return arguments, query

    def _process(self) -> Tuple[QueryArguments, str]:
        """

        Returns
        -------
        Tuple[QueryArguments, str]
        """
        extract = str()
        args = self.pattern.match(self._query)
        if args is not None:
            extract = args.group('argument')

        return self.extract_content(extract)
