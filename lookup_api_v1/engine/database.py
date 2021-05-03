#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from hashlib import blake2b
from json import dumps
from os import getenv
from urllib.parse import urlparse

# 3rd party:
from azure.cosmos.cosmos_client import CosmosClient
from azure.functions import HttpRequest
from pandas import read_json

# Internal:
from .ordering import format_ordering
from .. import instance_settings
from .queries import QueryParser
from ..types import QueryResponseType, OrderingType, QueryData, QueryArguments
from .exceptions import NotAvailable
from .structure import get_assurance_query

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'get_data'
]

ENVIRONMENT = getenv("API_ENV", "PRODUCTION")


DB_KWS = dict(
    url=instance_settings.DatabaseCredentials.host,
    credential={'masterKey': instance_settings.DatabaseCredentials.key}
)


client = CosmosClient(**DB_KWS)
db = client.get_database_client(instance_settings.DatabaseCredentials.db_name)
container = db.get_container_client(instance_settings.DatabaseCredentials.data_collection)


def process_head(filters: str, ordering: OrderingType,
                 arguments: QueryArguments) -> QueryResponseType:

    ordering_script = format_ordering(ordering)

    query = instance_settings.DBQueries.exists.substitute(
        clause_script=filters,
        ordering=ordering_script
    )

    logging.info(f"DB Query: {query}")
    logging.info(f"Query arguments: {arguments}")

    items = container.query_items(
        query=query,
        parameters=arguments,
        partition_key='general',
        max_item_count=1000
    )

    try:
        results = list(items)
    except KeyError:
        raise NotAvailable()

    if not len(results):
        raise NotAvailable()

    return list()


def process_get(filters: str, ordering: OrderingType, arguments: QueryArguments,
                structure: str, formatter: str) -> QueryResponseType:

    ordering_script = format_ordering(ordering)

    query = instance_settings.DBQueries.data_query.substitute(
        template=structure,
        clause_script=filters,
        ordering=ordering_script
    )

    logging.info(f">>>> DB Query: {query}")
    logging.info(f"Query arguments: {arguments}")

    items = container.query_items(
        query=query,
        parameters=arguments,
        partition_key='general',
        max_item_count=2000
    )

    try:
        results = list(items)
    except (KeyError, IndexError, StopIteration):
        raise NotAvailable()

    logging.info(f"Response length: {len(results)}")

    if formatter != 'csv':
        response = {
            'length': len(results),
            'data': results
        }

        return response

    if not len(results):
        raise NotAvailable()

    df = read_json(
        dumps(results),
        orient="values" if isinstance(results[0], list) else "records"
    )

    return df.to_csv(float_format="%.12g", index=None)


def get_data(request: HttpRequest, tokens: QueryParser, ordering: OrderingType,
             formatter: str) -> QueryResponseType:
    """
    Retrieves the data from the database.

    Parameters
    ----------
    request: HttpRequest

    tokens: QueryParser
        Query tokens, as constructed by ``queries.QueryParser``.

    ordering: OrderingType
        Ordering expression as a string.

    formatter: str

    Returns
    -------
    QueryResponseType
        List of items retrieved from the database in response to ``tokens``, structured
        as defined by ``structure``, and ordered as defined by ``ordering``.
    """
    query_data: QueryData = tokens.query_data
    arguments = query_data.arguments
    filters = query_data.query
    structure = tokens.structure
    extra_queries = get_assurance_query(structure)
    filters += extra_queries

    if request.method == "HEAD":
        return process_head(filters, ordering, arguments)

    elif request.method == "GET":
        return process_get(filters, ordering, arguments, structure, formatter)
