#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from datetime import datetime
import re
from hashlib import blake2b
from typing import Tuple, Union, Awaitable, List
from json import JSONDecodeError
from urllib.parse import unquote_plus, unquote

# 3rd party:

# Internal:
from .constants import (
    DATA_TYPES, TypePatterns, MAX_QUERY_PARAMS,
    STRING_TRANSFORMATION, MAX_DATE_QUERIES,
    REPORT_DATE_PARAM_NAME, DEFAULT_STRUCTURE,
    DATE_PARAMS, RESTRICTED_PARAMETER_VALUES,
    PAGINATION_PATTERN, MAX_STRUCTURE_LENGTH
)

from .exceptions import (
    IncorrectQueryValueType, InvalidQueryParameter,
    ExceedsMaxParameters, InvalidQuery, ValueNotAcceptable,
    RequestTooLarge, UnauthorisedRequest, StructureTooLarge,
    InvalidStructure
)

from .types import QueryArguments, StringOrNumber, QueryData

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

    pattern = re.compile(r'^(?P<argument>.*)$')

    structure_pattern = re.compile(r'(&?structure=([^&]+))&?')

    filter_pattern = re.compile(r'filters=([^&]+)(&|$)')

    latest_by = re.compile(r'(&?latestBy=([a-z2356780]{2,75}))&?', re.I)

    format_as = re.compile(r'(&?format=(json|csv|xml))&?')

    pagination_pattern = PAGINATION_PATTERN

    token_pattern = re.compile(
        r'''
            (
                (?P<name>[a-z]{2,75})
                (?P<operator>[<>!]?=?)
                (?P<value>[a-z0-9,'.\-()\s]{1,75})
                (?P<connector>[;|]?)
            )
        ''',
        flags=re.X | re.I
    )

    def __init__(self, query: str, last_update: str):
        """
        Parameters
        ----------
        query: str
            URL query string.

        last_update: str
            Last update timestamp.
        """
        self._query = query
        self._token = str()
        self.last_update = last_update
        self.structure: Awaitable[str] = self.extract_structure
        self.formatter: Awaitable[str] = self.extract_formatter
        self.raw_filters: List[dict] = list()
        self.only_latest_by: str = self.extract_latest_filter()
        self.query_data = self.extract_content()
        self.page_number = self.get_page_number()

    def get_page_number(self) -> Union[None, int]:
        found = self.pagination_pattern.search(self._query)

        if not found:
            return None

        param = found.group(2)

        self._query = self._query.replace(found.group(1), str())

        return int(param)

    async def extract_formatter(self) -> str:
        found = self.format_as.search(self._query)

        if not found:
            return "json"

        param = found.group(2)

        self._query = self._query.replace(found.group(1), str())

        return param

    async def extract_structure(self):
        structure = DEFAULT_STRUCTURE
        found = self.structure_pattern.search(self._query)

        if found:
            raw_json = found.group(2)
            self._query = self._query.replace(found.group(1), str())

            try:
                structure = unquote_plus(raw_json)
            except JSONDecodeError:
                raise InvalidStructure()

        return await format_structure(structure)

    def extract_latest_filter(self) -> Union[str, None]:
        found = self.latest_by.search(self._query)

        if not found:
            return None

        param = found.group(2)
        self._query = self._query.replace(found.group(1), str())

        if param not in DATE_PARAMS and param not in DATA_TYPES:
            raise InvalidQueryParameter(
                name="latestBy",
                operator="=",
                value=found.group(2)
            )

        return param

    def extract_content(self) -> QueryData:
        """

        Raises
        ------
        ExceedsMaxParameters

        InvalidQuery

        Returns
        -------
        Tuple[QueryArguments, str]
        """
        query = "AND "
        arguments = list()
        param_names = list()

        filters = self.filter_pattern.search(str(self))

        if filters is None:
            filters_value = str()
        else:
            filters_value = unquote(unquote_plus(filters.group(1)))

        area_type = None
        default_transformer = STRING_TRANSFORMATION['DEFAULT']

        for index, args in enumerate(self.get_queries(filters_value), start=2):
            name, operator, value = (
                args.group("name"),
                args.group("operator"),
                args.group("value")
            )

            param_names.append(name)

            transformer = STRING_TRANSFORMATION.get(name, default_transformer)

            if (RESTRICTED_PARAMETER_VALUES.get(name) is not None and
                    value.lower() not in RESTRICTED_PARAMETER_VALUES.get(name, [])):
                raise UnauthorisedRequest(name=name, operator=operator, value=value)

            self.raw_filters.append({
                "identifier": name,
                "operator": operator,
                "value": value
            })

            value = convert_value_type(name, operator, value)
            param_name = transformer.param_fn(name)

            if name == "areaType":
                area_type = value

            query += f'{param_name} {operator} {transformer.input_argument(f"${index}")}'

            arguments.append(transformer.value_fn(value))

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

        return QueryData(arguments=arguments, query=query, area_type=area_type)

    def get_queries(self, filters_value):
        for args in self.token_pattern.finditer(filters_value):
            yield args

    def __str__(self):
        """

        Returns
        -------
        Tuple[QueryArguments, str]
        """
        extract = str()
        args = self.pattern.match(self._query)
        if args is not None:
            extract = args.group('argument')

        return extract
