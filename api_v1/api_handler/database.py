#!/usr/bin python3


# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from os import getenv
from urllib.parse import urlparse, unquote_plus
from dataclasses import dataclass
from functools import lru_cache
from typing import Awaitable, Union, Iterable, Any, Dict
from datetime import datetime, date

# 3rd party:
import asyncpg

from orjson import dumps, loads, JSONDecodeError

from azure.cosmos.cosmos_client import CosmosClient
from azure.functions import HttpRequest

from pandas import DataFrame

from numpy import ceil

# Internal:
from .constants import (
    DBQueries, DatabaseCredentials, PAGINATION_PATTERN,
    MAX_ITEMS_PER_RESPONSE, DATA_TYPES
)
from .queries import QueryParser
from .types import QueryResponseType, QueryData, ResponseStructure
from .exceptions import NotAvailable

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
PREFERRED_LOCATIONS = getenv("AzureCosmosDBLocations", "").split(",") or None

base_metrics = ["areaCode", "areaType", "areaName", "date"]
single_partition_types = {"utla", "ltla", "nhstrust", "msoa"}

dtypes = DATA_TYPES.copy()
dtypes["date"] = str

type_map: Dict[object, object] = {
    int: float,
    float: float,
    str: str
}

generic_dtypes = {
    metric_name: type_map.get(dtypes[metric_name], object)
    if dtypes[metric_name] not in [int, float] else float
    for metric_name in dtypes
}
integer_dtypes = {type_ for type_, base_type in dtypes.items() if base_type is int}
string_dtypes = {type_ for type_, base_type in dtypes.items() if base_type is str}
json_dtypes = {type_ for type_, base_type in dtypes.items() if base_type in [list, dict]}

logger = logging.getLogger('azure')
logger.setLevel(logging.WARNING)

# DB_KWS = dict(
#     url=DatabaseCredentials.host,
#     credential={'masterKey': DatabaseCredentials.key},
#     preferred_locations=PREFERRED_LOCATIONS,
#     connection_timeout=10000
# )
#
# client = CosmosClient(**DB_KWS)
# db = client.get_database_client(DatabaseCredentials.db_name)
# container = db.get_container_client(DatabaseCredentials.data_collection)


def json_formatter(obj):
    if isinstance(date, (date, datetime)):
        return obj.isoformat()


def log_response(query, arguments):
    """
    Closure for logging DB query information.

    Main function receives the ``query`` and its ``arguments`` and returns
    a function that may be passed to the ``cosmos_client.query_items``
    as the ``response_hook`` keyword argument.
    """
    count = 0

    def process(metadata, results):
        nonlocal count, query

        for item in arguments:
            query = query.replace(item['name'], item['value'])

        custom_dims = dict(
            charge=metadata.get('x-ms-request-charge', None),
            query=query,
            query_raw=query,
            response_count=metadata.get('x-ms-item-count', None),
            path=metadata.get('x-ms-alt-content-path', None),
            parameters=arguments,
            request_round=count
        )

        logging.info(f"DB QUERY: { dumps(custom_dims) }")

    return process


class Connection:
    def __init__(self, conn_str=getenv("POSTGRES_CONNECTION_STRING")):
        self.conn_str = conn_str
        self._connection = asyncpg.connect(self.conn_str, statement_cache_size=0, timeout=60)

    def __await__(self):
        yield from self._connection.__await__()

    def __aenter__(self):
        return self._connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self._connection.close()


@dataclass
class RequestMethod:
    Get: str = "GET"
    Head: str = "HEAD"
    Options: str = "OPTIONS"
    Post: str = "POST"
    Put: str = "PUT"
    Patch: str = "PATCH"


async def get_count(conn, db_args: Iterable[Any], partition_id: str, filters: str):
    """
    Count is a very expensive DB call, and is therefore cached in the memory.
    """
    query = DBQueries.count.substitute(partition=partition_id, filters=filters)

    return await conn.fetchrow(query, *db_args)


def format_data(df: DataFrame, response_metrics: Iterable[str]) -> DataFrame:
    int_response_metrics = set(response_metrics).intersection(integer_dtypes)
    df.loc[:, int_response_metrics] = df[int_response_metrics].astype(object)

    for col in int_response_metrics:
        notnull = df[col].notnull()
        try:
            df.loc[notnull, col] = (
               df
               .loc[notnull, col]
               .str.replace(".0+$", "", regex=True)
               .astype(int)
            )
        except AttributeError:
            df.loc[notnull, col] = (
               df
               .loc[notnull, col]
               .astype(int)
            )

    df = df.where(df.notnull(), None)

    str_response_metrics = set(response_metrics).intersection(string_dtypes)
    df.loc[:, str_response_metrics] = (
        df
        .loc[:, str_response_metrics]
        .apply(lambda column: column.str.strip('"'))
    )

    return df


def set_column_labels(df: DataFrame, structure: ResponseStructure):
    if isinstance(structure, list):
        return df

    response_columns = list(structure.values())
    difference = set(response_columns) - set(df.columns)

    for col in difference:
        df = df.assign(**{col: None})

    df = (
        df
        .loc[:, response_columns]
        .rename(columns=dict(zip(response_columns, structure)))
    )

    return df


def format_response(df: DataFrame, request: HttpRequest, response_type: str,
                    count: int, page_number: int, n_metrics: int, structure: dict,
                    raw_filters: list) -> bytes:
    if response_type == 'csv':
        return df.to_csv(float_format="%.20g", index=False).encode()

    total_pages = int(ceil(count / (MAX_ITEMS_PER_RESPONSE * n_metrics)))
    prepped_url = PAGINATION_PATTERN.sub("", request.url)
    parsed_url = urlparse(prepped_url)
    url = unquote_plus(f"/v1/data?{parsed_url.query}".strip("&"))

    if "latestBy" in prepped_url:
        count = df.shape[0]

    payload = {
        'length': df.shape[0],
        'maxPageLimit': MAX_ITEMS_PER_RESPONSE,
        'totalRecords': count,
        'data': df.to_dict("records"),
        'requestPayload': {
            'structure': structure,
            'filters': raw_filters
        }
    }

    if (latest_by := request.params.get("latestBy")) is None:
        payload.update({
            "pagination": {
                'current': f"{url}&page={page_number}",
                'next': f"{url}&page={page_number + 1}" if page_number < total_pages else None,
                'previous': f"{url}&page={page_number - 1}" if (page_number - 1) > 0 else None,
                'first': f"{url}&page=1",
                'last': f"{url}&page={total_pages}"
            }
        })
        payload['requestPayload']['page'] = page_number
    else:
        payload['requestPayload']['latestBy'] = latest_by

    return dumps(payload, default=json_formatter)


@lru_cache(32)
def get_partition_id(area_type: str, timestamp: str) -> str:
    ts = datetime.fromisoformat(timestamp[:26])

    if area_type.lower() not in single_partition_types:
        area_type = "other"

    partition_id = f"{ts:%Y_%-m_%-d}_{area_type.lower()}"

    return partition_id


async def get_query(request: HttpRequest, latest_by: Union[str, None], partition_id: str,
                    filters: str, page_number: int, n_metrics: int) -> Awaitable[str]:
    if ENVIRONMENT != "DEVELOPMENT":
        # Released metrics only.
        filters += f" AND mr.released IS TRUE"

    if latest_by is not None:
        query = DBQueries.latest_date_for_metric.substitute(
            partition=partition_id,
            filters=filters,
            latest_by=latest_by
        )
    elif request.method == RequestMethod.Get:
        query = DBQueries.data_query.substitute(
            partition=partition_id,
            filters=filters,
            limit=MAX_ITEMS_PER_RESPONSE * n_metrics,
            offset=MAX_ITEMS_PER_RESPONSE * n_metrics * (page_number - 1)
        )
    else:
        query = DBQueries.exists.substitute(
            partition=partition_id,
            filters=filters,
            offset=MAX_ITEMS_PER_RESPONSE * n_metrics * (page_number - 1)
        )

    logging.info(query)
    return query


def to_json(data) -> Union[dict, list]:
    try:
        return loads(data)
    except JSONDecodeError:
        return list()


def format_dtypes(df: DataFrame, column_types: Dict[str, object]) -> DataFrame:
    json_columns = json_dtypes.intersection(column_types)

    df = df.replace('null', None)
    df.loc[:, json_columns] = (
        df
        .loc[:, json_columns]
        .apply(lambda column: column.map(to_json))
    )

    return df.astype(column_types)


async def get_data(request: HttpRequest, tokens: QueryParser, formatter: str,
                   timestamp: str) -> QueryResponseType:
    query_data: QueryData = tokens.query_data
    arguments = query_data.arguments
    filters = query_data.query
    structure = await tokens.structure
    raw_filters = tokens.raw_filters

    if isinstance(structure, dict):
        metrics = list(structure.values())
    else:
        metrics = list(structure)

    if tokens.page_number is not None:
        page_number = int(tokens.page_number)
    else:
        page_number = 1

    n_metrics = len(metrics)

    partition_id = get_partition_id(query_data.area_type, timestamp)

    query = await get_query(
        request=request,
        latest_by=tokens.only_latest_by,
        partition_id=partition_id,
        filters=filters,
        page_number=page_number,
        n_metrics=n_metrics
    )

    db_metrics = set(metrics) - {"areaCode", "areaName", "areaType", "date"}
    db_args = [
        list(db_metrics),
        *arguments
    ]
    logging.info(dumps({"arguments": db_args}, default=json_formatter))

    count = dict()

    async with Connection() as conn:
        if request.method == RequestMethod.Get:
            if tokens.only_latest_by is None:
                count = await get_count(
                    conn,
                    db_args,
                    partition_id=partition_id,
                    filters=filters
                )

                if not count:
                    raise NotAvailable()

            values = await conn.fetch(query, *db_args)
        else:
            values = await conn.fetchrow(query, *db_args)

    count = count.get("count", 0)
    logging.info(query)

    if request.method == RequestMethod.Head:
        if values is None or not values.get('exists', False):
            raise NotAvailable()
        return str()

    elif values is None or not len(values):
        raise NotAvailable()

    df = DataFrame(values, columns=[*base_metrics, "metric", "value"])

    response_metrics = df.metric.unique()
    column_types = {
        metric: generic_dtypes[metric]
        for metric in filter(response_metrics.__contains__, generic_dtypes)
    }

    payload = (
        df
        .pivot_table(values="value", index=base_metrics, columns="metric", aggfunc='first')
        .reset_index()
        .sort_values(["areaCode", "date"], ascending=[True, False])
        .pipe(format_dtypes, column_types=column_types)
        .loc[:, [*base_metrics, *response_metrics]]
        .pipe(format_data, response_metrics=response_metrics)
        .pipe(set_column_labels, structure=structure)
        .pipe(
            format_response,
            request=request,
            response_type=formatter,
            count=count,
            page_number=page_number,
            n_metrics=n_metrics,
            structure=structure,
            raw_filters=raw_filters
        )
    )

    return payload
