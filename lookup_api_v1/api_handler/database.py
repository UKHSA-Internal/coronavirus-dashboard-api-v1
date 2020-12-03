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
import logging
from typing import NamedTuple
from os import getenv
from hashlib import blake2b

# 3rd party:
from azure.cosmos import cosmos_client

# Internal:
from .ordering import format_ordering
from .structure import format_structure
from .settings import DBQueries
from .queries import QueryParser
from .types import StructureType, QueryResponseType, OrderingType

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'get_data'
]


class Credentials(NamedTuple):
    host = getenv('AzureCosmosHost')
    key = getenv('AzureCosmosKey')
    db_name = getenv('AzureCosmosDBName')
    collection = getenv('AzureCosmosDestinationsCollection')


client = cosmos_client.CosmosClient(
    url=Credentials.host,
    credential={'masterKey': Credentials.key},
    user_agent="CosmosDBDotnetQuickstart",
    user_agent_overwrite=True
)

db = client.get_database_client(Credentials.db_name)
container = db.get_container_client(Credentials.collection)


def get_data(tokens: QueryParser, ordering: OrderingType) -> QueryResponseType:
    """
    Retrieves the data from the database.

    Parameters
    ----------
    tokens: QueryParser
        Query tokens, as constructed by ``queries.QueryParser``.

    ordering: OrderingType
        Ordering expression as a string.

    Returns
    -------
    QueryResponseType
        List of items retrieved from the database in response to ``tokens``, structured
        as defined by ``structure``, and ordered as defined by ``ordering``.
    """
    ordering_script = format_ordering(ordering)

    clause_script = tokens.clause_script
    arguments = tokens.arguments

    query = DBQueries.get_query.substitute(
        template=tokens.structure,
        clause_script=clause_script,
        ordering=ordering_script
    )

    # ToDo: Remove debug logging.
    logging.info(f"DB Query: {query}")
    logging.info(f"Query arguments: {tokens.arguments}")

    items = container.query_items(
        query=query,
        parameters=arguments,
        partition_key='general',
        # enable_cross_partition_query=True
    )

    results = list(items)

    logging.info(f"Response length: {len(results)}")

    return results
