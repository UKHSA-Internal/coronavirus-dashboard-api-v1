import site
import pathlib

test_dir = pathlib.Path(__file__).resolve().parent
root_path = test_dir.parent.parent
site.addsitedir(root_path)

import asyncio
import unittest
from pprint import pprint

from api_v1.api import api
from api_v1.api_handler.constants import DATA_TYPES
from api_v1.api_handler.queries import QueryParser


class TestApiHandlerFunctions(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.last_update = '2023-05-25T16:48:09.9161315Z'
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()

    async def test_QueryParser_all_metrics(self):
        for i, metric in enumerate(set(DATA_TYPES)):
            query = (
                'filters=areaType=nation;areaName=England'
                '&latestBy={metric}'
                '&structure={'
                f'"date":"date","value":"{metric}"'
                '}&format=csv'
            )
            tokens = QueryParser(query, self.last_update)
            structure = await tokens.structure()

            assert structure['value'] == metric

    async def test_QueryParser_attributes(self):
        metric = 'cumVaccinationSpring23UptakeByVaccinationDatePercentage75plus'
        query = (
            'filters=areaType=nation;areaName=England'
            '&latestBy={metric}'
            '&structure={'
            f'"date":"date","value":"{metric}"'
            '}&format=csv'
        )

        tokens = QueryParser(query, self.last_update)
        raw_filters = [
            {'identifier': 'areaType', 'operator': '=', 'value': 'nation'},
            {'identifier': 'areaName', 'operator': '=', 'value': 'England'}
        ]

        assert tokens.last_update == self.last_update
        assert tokens.formatter == "csv"
        assert tokens.raw_filters == raw_filters
        assert tokens.query_data.arguments == ['nation', 'england']
        assert tokens.query_data.query == 'AND area_type = $2 AND LOWER(area_name) = $3'
        assert tokens.query_data.area_type == 'nation'
        assert tokens.page_number == None


if __name__ == '__main__':
    asyncio.run(unittest.main())