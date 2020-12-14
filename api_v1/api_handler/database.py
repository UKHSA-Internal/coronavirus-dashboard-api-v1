#!/usr/bin python3


# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from hashlib import blake2b
from json import dumps
from os import getenv
from urllib.parse import urlparse
from math import ceil
from functools import lru_cache

# 3rd party:
from azure.cosmos.cosmos_client import CosmosClient
from azure.functions import HttpRequest
from pandas import read_json

# Internal:
from .ordering import format_ordering
from .constants import (
    DBQueries, DATE_PARAM_NAME, DatabaseCredentials,
    PAGINATION_PATTERN, MAX_ITEMS_PER_RESPONSE,
    DEFAULT_LATEST_ORDERING
)
from .queries import QueryParser
from .types import QueryResponseType, OrderingType, QueryData, QueryArguments
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
PREFERRED_LOCATIONS = getenv("AzureCosmosDBLocations", "").split(",")


logger = logging.getLogger('azure')
logger.setLevel(logging.WARNING)

DB_KWS = dict(
    url=DatabaseCredentials.host,
    credential={'masterKey': DatabaseCredentials.key},
    preferred_locations=PREFERRED_LOCATIONS
)

client = CosmosClient(**DB_KWS)
db = client.get_database_client(DatabaseCredentials.db_name)
container = db.get_container_client(DatabaseCredentials.data_collection)


@lru_cache(maxsize=2048)
def get_count(query, date, **kwargs):
    """
    Count is a very expensive DB call, and is therefore cached in the memory.
    """
    try:
        count_items = list(container.query_items(
            query=query,
            parameters=[{"name": name, "value": value} for name, value in kwargs.items()],
            max_item_count=MAX_ITEMS_PER_RESPONSE,
            enable_cross_partition_query=True,
            partition_key=date
        ))
        count = count_items.pop()
    except (IndexError, ValueError):
        raise NotAvailable()

    return count


async def process_head(filters: str, ordering: OrderingType,
                       arguments: QueryArguments, date: str) -> QueryResponseType:

    ordering_script = format_ordering(ordering)

    query = DBQueries.exists.substitute(
        clause_script=filters,
        ordering=await ordering_script
    )

    logging.info(f"DB Query: {query}")
    logging.info(f"Query arguments: {arguments}")

    items = container.query_items(
        query=query,
        parameters=arguments,
        max_item_count=MAX_ITEMS_PER_RESPONSE,
        enable_cross_partition_query=True,
        partition_key=date
    )

    try:
        results = list(items)
    except KeyError:
        raise NotAvailable()

    if not len(results):
        raise NotAvailable()

    return list()


async def process_get(request: HttpRequest, filters: str,
                      ordering: OrderingType, tokens: QueryParser,
                      arguments: QueryArguments, structure: str, formatter: str,
                      max_items: int, date: str) -> QueryResponseType:

    ordering_script = format_ordering(ordering)

    subs = dict(
        template=structure,
        clause_script=filters,
        ordering=await ordering_script,
    )

    query = DBQueries.data_query.substitute(**subs)

    logging.info(f"DB Query: {query}")
    logging.info(f"Query arguments: {arguments}")
    page_number = None

    count_query = DBQueries.count.substitute(**subs)
    arguments_dict = {
        item["name"]: item["value"]
        for item in sorted(arguments, key=lambda v: v["name"])
    }
    count = get_count(count_query, date, **arguments_dict)

    items = container.query_items(
        query=query,
        parameters=arguments,
        max_item_count=MAX_ITEMS_PER_RESPONSE,
        enable_cross_partition_query=True,
        partition_key=date
    )

    if tokens.page_number is not None:
        page_number = int(tokens.page_number)

    try:
        query_hash = blake2b(query.encode(), digest_size=32).hexdigest()
        # paginated_items = list(items.by_page(continuation_token=query_hash))
        paginated_items = items.by_page(continuation_token=query_hash)

        if page_number is not None:
            page = 0
            while page < page_number:
                # for ind, page in enumerate(paginated_items):
                res = next(paginated_items)
                page += 1
                # break
                # results = list(paginated_items[page_number - 1])
            results = list(res)
        else:
            results = list(next(paginated_items))
    except (KeyError, IndexError, StopIteration):
        raise NotAvailable()

    logging.info(f"Response length: {len(results)}")

    if formatter != 'csv':
        response = {
            'length': len(results),
            'maxPageLimit': max_items,
            'data': results
        }

        if page_number is not None:
            total_pages = ceil(count / MAX_ITEMS_PER_RESPONSE)
            prepped_url = PAGINATION_PATTERN.sub("", request.url)
            parsed_url = urlparse(prepped_url)
            url = f"/v1/data?{parsed_url.query}".strip("&")
            response.update({
                "pagination": {
                    'current': f"{url}&page={page_number}",
                    'next': (
                        f"{url}&page={page_number + 1}"
                        if page_number < total_pages else None
                    ),
                    'previous': (
                        f"{url}&page={page_number - 1}"
                        if (page_number - 1) > 0 else None
                    ),
                    'first': f"{url}&page=1",
                    'last': f"{url}&page={total_pages}"
                }
            })
        return response

    if not len(results):
        raise NotAvailable()

    df = read_json(
        dumps(results),
        orient="values" if isinstance(results[0], list) else "records"
    )

    return df.to_csv(float_format="%.20g", index=None)


async def get_latest_available(filters: str, latest_by: str,
                               arguments: QueryArguments, date: str) -> str:

    ordering_script = format_ordering(DEFAULT_LATEST_ORDERING)

    query = DBQueries.latest_date_for_metric.substitute(
        clause_script=filters,
        latest_by=latest_by,
        ordering=await ordering_script
    )

    logging.info(f"Latest query: {query}")
    logging.info(f"Parameters: {arguments}")

    # ToDo: Return data with CSV format.

    latest = container.query_items(
        query=query,
        parameters=arguments,
        max_item_count=MAX_ITEMS_PER_RESPONSE,
        enable_cross_partition_query=True
    )

    try:
        return next(latest)[DATE_PARAM_NAME]
    except (KeyError, IndexError, StopIteration):
        raise NotAvailable()


async def get_data(request: HttpRequest, tokens: QueryParser,
                   ordering: OrderingType, formatter: str, timestamp: str,
                   series_date: str) -> QueryResponseType:
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

    timestamp: str

    series_date: str

    Returns
    -------
    QueryResponseType
        List of items retrieved from the database in response to ``tokens``, structured
        as defined by ``structure``, and ordered as defined by ``ordering``.
    """
    query_data: QueryData = tokens.query_data
    arguments = query_data.arguments
    filters = query_data.query
    structure = await tokens.structure
    extra_queries = await get_assurance_query(structure)
    filters += extra_queries

    date = timestamp
    if ENVIRONMENT in ["PRODUCTION", "DEVELOPMENT"]:
        date = series_date

    max_items = MAX_ITEMS_PER_RESPONSE

    latest_by = await tokens.only_latest_by

    if latest_by is not None:
        param = get_latest_available(
            filters=filters,
            latest_by=latest_by,
            arguments=arguments,
            date=date
        )
        max_items = 1

        name = blake2b(DATE_PARAM_NAME.encode(), digest_size=6).hexdigest()
        name = f"@{ DATE_PARAM_NAME }{ name }"

        filters += f" AND c.{ DATE_PARAM_NAME } = { name }"

        arguments = (
            *arguments,
            {'name': name, 'value': await param}
        )

    arguments = [
        *arguments,
        {"name": "@seriesDate", "value": date}
    ]

    if request.method == "HEAD":
        return await process_head(filters, ordering, arguments, date)

    elif request.method == "GET":
        return await process_get(request, filters, ordering, tokens,
                                 arguments, structure, formatter,
                                 max_items=max_items, date=date)
