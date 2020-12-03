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

# 3rd party:

# Internal:
from .settings import DATA_TYPES
from .types import OrderingType

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'format_ordering'
]


def format_ordering(orders: OrderingType) -> str:
    """

    Parameters
    ----------
    orders: OrderType

    Returns
    -------
    str
    """
    result = list()

    for item in orders:
        if item["by"] not in DATA_TYPES:
            # ToDo: Convert to a valid error message.
            raise ValueError(
                f"Unauthorised ordering parameter '{item['by']}' - "
                f"choice are: { str.join(', ', DATA_TYPES) }"
            )
        token = f"c.{item['by']} {'ASC' if item['ascending'] else 'DESC'}"
        result.append(token)

    return f"ORDER BY {str.join(', ', result)}"
