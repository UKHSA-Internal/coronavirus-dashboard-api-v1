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
from string import Template
from typing import Match, List, Callable
from json import dumps
from datetime import datetime
import re

# 3rd party:

# Internal:
from .exceptions import InvalidStructureParameter, InvalidStructure
from .constants import DATA_TYPES
from .types import StructureType

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'format_structure',
    'get_assurance_query'
]


async def get_formatter(template_format: str) -> Callable[[Match], str]:
    """
    Creates a string template for the structure based on ``template_format``.

    The function is a closure to retain the structure for future processing and
    substitution via regular expressions. It is structured so that it can be
    used with the RegEx patterns defined in ``format_structure``.

    If ``template_format='JSON'``, the template will be:

        {
            `new_name`: c.parameter_name,
            ...
        }

    If ``template_format='Array'``, the template will be:

        [
            c.parameter_name,
            ...
        ]

    .. note::
        Values of ``template_format`` are case-sensitive.

    Raises
    ------
    InvalidStructure
        If the template format is invalid - i.e. not one of ``JSON`` or ``Array``.

    InvalidStructureParameter
        If the requested parameter does is invalid (does not exist in ``DATA_TYPES``).

    Parameters
    ----------
    template_format: str
        Either ``'JSON'`` or ``'Array'``.

    Returns
    -------
    Callable[[Match], str]
    """
    format_templates = {
        "JSON": f"'$new_name': $db_name",
        "Array": f"$db_name"
    }

    try:
        template = Template(format_templates[template_format])
    except KeyError:
        raise InvalidStructure()

    def format_struct(match: Match) -> str:
        db_name = match.group('db_name')
        try:
            if DATA_TYPES[db_name] is datetime and db_name != 'date':
                db_name = f"SUBSTRING(c.{db_name}, 0, 10)"
            else:
                db_name = f"c.{db_name}"

            params = {
                **match.groupdict(),
                'db_name': f"({db_name} ?? null)"
            }

            return template.substitute(**params)

        except KeyError:
            raise InvalidStructureParameter(
                name=match.group('db_name'),
                structure_format=template_format
            )

    return format_struct


async def format_structure(struct: StructureType) -> str:
    """
    Formats the requested structure and prepares it for use in database
    query.

    Parameters
    ----------
    struct: dict, list
        Structure the be used in the response.

    Raises
    ------
    InvalidStructure
        When the structure is neither an Array (``list``) nor a JSON (``dict``).

    Returns
    -------
    str
        Formatted response structure ready to be used in the database query.
    """
    struct_json = dumps(struct)

    if isinstance(struct, dict):
        formatter = await get_formatter("JSON")
        pattern = re.compile(
            r'"(?P<new_name>[a-z2860]{2,40})":\s*"(?P<db_name>[a-z2860]{2,40})"',
            re.IGNORECASE
        )
    elif isinstance(struct, list):
        formatter = await get_formatter("Array")
        pattern = re.compile(r'"(?P<db_name>[a-z2860]{2,40})"', re.IGNORECASE)
    else:
        raise InvalidStructure()

    return pattern.sub(formatter, struct_json)


async def get_assurance_query(struct: str) -> str:
    pattern = re.compile(r'c\.(?P<db_name>[a-z2860_]+)', re.IGNORECASE)

    excluded = {
        "areaname",
        "areacode",
        "date",
        "areatype",
        "releasetimestamp "
    }

    query = [
        f'IS_DEFINED(c.{match.group("db_name")}) '
        for match in pattern.finditer(struct)
        if match.group("db_name").lower() not in excluded
    ]

    query_str = str.join("OR ", query)
    return f" AND ({query_str})" if query_str else str()
