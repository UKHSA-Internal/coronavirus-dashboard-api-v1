#!/usr/bin python3

"""
Constants
---------

Constants, which are used globally in the API service.

.. warning::
    Do not include secrets in this module. Use environment variables
    instead.

Author:        Pouria Hadjibagheri <pouria.hadjibagheri@phe.gov.uk>
Created:       23 May 2020
License:       MIT
Contributors:  Pouria Hadjibagheri
"""

from datetime import datetime
from os import getenv

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
from re import IGNORECASE
from re import compile as re_compile
from string import Template
from typing import Any, Callable, Dict, List, NamedTuple, Pattern, Set

# Internal:
from .types import OrderingType, Transformer

# 3rd party:


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Header
__author__ = "Pouria Hadjibagheri"
__copyright__ = "Copyright (c) 2020, Public Health England"
__license__ = "MIT"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    "MAX_QUERY_PARAMS",
    "DATE_PARAMS",
    "DEFAULT_STRUCTURE",
    "AUTHORISED_ORDERING_PARAMS",
    "DEFAULT_ORDERING",
    "DATA_TYPES",
    "TypePatterns",
    "DBQueries",
    "STRING_TRANSFORMATION",
    "MAX_DATE_QUERIES",
    "REPORT_DATE_PARAM_NAME",
    "RESPONSE_TYPE",
    "DATE_PARAM_NAME",
    "RESTRICTED_PARAMETER_VALUES",
    "PAGINATION_PATTERN",
    "MAX_ITEMS_PER_RESPONSE",
    "DEFAULT_LATEST_ORDERING",
    "SELF_URL",
    "MAX_STRUCTURE_LENGTH",
]


ENVIRONMENT = getenv("API_ENV", "PRODUCTION")

RESPONSE_TYPE = {
    "xml": "application/vnd.PHE-COVID19.v1+json; charset=utf-8",
    "json": "application/vnd.PHE-COVID19.v1+json; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}

MAX_ITEMS_PER_RESPONSE = 2500

REPORT_DATE_PARAM_NAME = "releaseTimestamp"

MAX_DATE_QUERIES = 1

MAX_QUERY_PARAMS: int = 5
MAX_STRUCTURE_LENGTH: int = 8
DATE_PARAM_NAME = "date"

DATE_PARAMS: Set[str] = {REPORT_DATE_PARAM_NAME, DATE_PARAM_NAME}

DEFAULT_STRUCTURE: Dict[str, Any] = {
    "areaType": "areaType",
    "areaCode": "areaCode",
    "areaName": "areaName",
    "reportDate": REPORT_DATE_PARAM_NAME,
    "cases": {
        "specimenDate": "specimenDate",
        "dailyLabConfirmedCases": "dailyLabConfirmedCases",
        "previouslyReportedDailyCases": "previouslyReportedDailyCases",
        "changeInDailyCases": "changeInDailyCases",
        "totalLabConfirmedCases": "totalLabConfirmedCases",
        "previouslyReportedTotalCases": "previouslyReportedTotalCases",
        "changeInTotalCases": "changeInTotalCases",
        "dailyTotalLabConfirmedCasesRate": "dailyTotalLabConfirmedCasesRate",
        "casesRateInSevenDays": "casesRateInSevenDays",
    },
    "deaths": {
        "deathReportingDate": "deathReportingDate",
        "dailyChangeInDeaths": "dailyChangeInDeaths",
        "cumulativeDeaths": "cumulativeDeaths",
    },
}

AUTHORISED_ORDERING_PARAMS: Set[str] = {
    REPORT_DATE_PARAM_NAME,
    "date",
    "areaName",
    "areaCode",
    "areaType",
}


DEFAULT_ORDERING: OrderingType = [
    {"by": "releaseTimestamp", "ascending": False},
    {"by": "areaType", "ascending": True},
    {"by": "areaNameLower", "ascending": True},
    {"by": "date", "ascending": False},
]


DEFAULT_LATEST_ORDERING: OrderingType = [
    {"by": "releaseTimestamp", "ascending": False},
    {"by": "date", "ascending": False},
    {"by": "areaType", "ascending": True},
    {"by": "areaNameLower", "ascending": True},
]


PAGINATION_PATTERN: Pattern = re_compile(r"(page=(\d{,3}))")


if ENVIRONMENT == "DEVELOPMENT":
    SELF_URL = str()
elif ENVIRONMENT == "STAGING":
    SELF_URL = "https://api.coronavirus-staging.data.gov.uk"
else:
    SELF_URL = "https://api.coronavirus.data.gov.uk"


TypePatterns: Dict[Callable[[str], Any], Pattern] = {
    str: re_compile(r"[a-z]+", IGNORECASE),
    int: re_compile(r"\d{1,7}"),
    float: re_compile(r"[0-9.]{1,8}"),
    datetime: re_compile(r"\d{4}-\d{2}-\d{2}"),
}

AREA_TYPES = {
    "utla": "utla",
    "ltla": "ltla",
    "region": "region",
    "nhsregion": "nhsRegion",
    "overview": "overview",
    "nation": "nation",
    "nhstrust": "nhsTrust",
}

STRING_TRANSFORMATION = {
    "areaName": Transformer(
        value_fn=str.lower,
        param_fn=lambda n: n.replace("areaName", "LOWER(area_name)"),
        input_argument=lambda a: a,
    ),
    "areaType": Transformer(
        value_fn=lambda x: AREA_TYPES[str.lower(x)],
        param_fn=lambda n: n.replace("areaType", "area_type"),
        input_argument=lambda a: a,
    ),
    "date": Transformer(
        value_fn=lambda x: datetime.strptime(x.split("T")[0], "%Y-%m-%d").date(),
        param_fn=str,
        input_argument="{}".format,
    ),
    "areaCode": Transformer(
        value_fn=str.upper,
        param_fn=lambda n: n.replace("areaCode", "area_code"),
        input_argument=lambda a: a,
    ),
    "DEFAULT": Transformer(
        value_fn=lambda x: x, param_fn=lambda x: x, input_argument=lambda a: a
    ),
}


class DBQueries(NamedTuple):
    # noinspection SqlResolve,SqlNoDataSourceInspection
    data_query = Template(
        """\
SELECT
    area_code             AS "areaCode",
    ref.area_type         AS "areaType",
    area_name             AS "areaName",
    date::VARCHAR         AS date,
    metric,
    CASE
        WHEN (payload ? 'value') THEN (payload -> 'value')
        ELSE payload::JSONB
    END AS value
FROM covid19.time_series_p${partition} AS ts
JOIN covid19.metric_reference  AS mr  ON mr.id = metric_id
JOIN covid19.release_reference AS rr  ON rr.id = release_id
JOIN covid19.area_reference    AS ref ON ref.id = area_id
WHERE
      metric = ANY($$1::VARCHAR[])
  AND rr.released IS TRUE
  $filters
ORDER BY area_id, date DESC
LIMIT $limit OFFSET $offset
"""
    )

    # Query assumes that the data is ordered (descending) by date.
    # noinspection SqlResolve,SqlNoDataSourceInspection
    latest_date_for_metric = Template(
        """\
SELECT
    area_code             AS "areaCode",
    ref.area_type         AS "areaType",
    area_name             AS "areaName",
    date::VARCHAR         AS date,
    metric,
    CASE
        WHEN (payload ? 'value') THEN (payload -> 'value')
        ELSE payload::JSONB
    END AS value
FROM covid19.time_series_p${partition} AS ts
    JOIN covid19.metric_reference  AS mr  ON mr.id = metric_id
    JOIN covid19.release_reference AS rr  ON rr.id = release_id
    JOIN covid19.area_reference    AS ref ON ref.id = area_id
WHERE
      metric = ANY($$1::VARCHAR[])
  AND rr.released IS TRUE
  $filters
  AND date = (
      SELECT MAX(date)
      FROM covid19.time_series_p${partition} AS ts
          JOIN covid19.metric_reference  AS mr  ON mr.id = metric_id
          JOIN covid19.release_reference AS rr  ON rr.id = release_id
          JOIN covid19.area_reference    AS ref ON ref.id = area_id
      WHERE
            rr.released IS TRUE
        AND metric = '$latest_by'
        $filters
  )
ORDER BY area_code, date DESC"""
    )

    # noinspection SqlResolve,SqlNoDataSourceInspection
    exists = Template(
        """\
SELECT TRUE AS exists
FROM covid19.time_series_p${partition} AS ts
    JOIN covid19.metric_reference  AS mr  ON mr.id = metric_id
    JOIN covid19.release_reference AS rr  ON rr.id = release_id
    JOIN covid19.area_reference    AS ref ON ref.id = area_id
WHERE
      metric = ANY($$1::VARCHAR[])
  AND rr.released IS TRUE
  $filters
OFFSET $offset
FETCH FIRST 1 ROW ONLY"""
    )

    count = Template(
        """\
SELECT COUNT(*) AS count
FROM covid19.time_series_p${partition} AS ts
    JOIN covid19.metric_reference  AS mr  ON mr.id = metric_id
    JOIN covid19.release_reference AS rr  ON rr.id = release_id
    JOIN covid19.area_reference    AS ref ON ref.id = area_id
WHERE
      metric = ANY($$1::VARCHAR[])
  AND rr.released IS TRUE
  $filters"""
    )


DATA_TYPES: Dict[str, Callable[[str], Any]] = {
    "hash": str,
    "areaType": str,
    "date": datetime,
    "areaName": str,
    "areaNameLower": str,
    "areaCode": str,
    "covidOccupiedMVBeds": int,
    "covidOccupiedMVBedsWeekly": int,
    "cumAdmissions": int,
    "cumCasesByPublishDate": int,
    "cumPillarFourTestsByPublishDate": int,
    "cumPillarOneTestsByPublishDate": int,
    "cumPillarThreeTestsByPublishDate": int,
    "cumPillarTwoTestsByPublishDate": int,
    "cumTestsByPublishDate": int,
    "hospitalCases": int,
    "hospitalCases_archive": int,
    "hospitalCasesWeekly": int,
    "hospitalCasesWeekly_archive": int,
    "newAdmissions": int,
    "newAdmissions_archive": int,
    "newAdmissionsWeekly": int,
    "newAdmissionsWeekly_archive": int,
    "newCasesByPublishDate": int,
    "newPillarFourTestsByPublishDate": int,
    "newPillarOneTestsByPublishDate": int,
    "newPillarThreeTestsByPublishDate": int,
    "newPillarTwoTestsByPublishDate": int,
    "newTestsByPublishDate": int,
    "plannedCapacityByPublishDate": int,
    "newCasesBySpecimenDate": int,
    "cumCasesBySpecimenDate": int,
    "maleCases": list,
    "femaleCases": list,
    "cumAdmissionsByAge": list,
    "femaleDeaths28Days": list,
    "maleDeaths28Days": list,
    "changeInNewCasesBySpecimenDate": int,
    "previouslyReportedNewCasesBySpecimenDate": int,
    "cumCasesBySpecimenDateRate": float,
    "cumCasesByPublishDateRate": float,
    "release": datetime,
    "newDeathsByDeathDate": int,
    "newDeathsByDeathDateRate": float,
    "newDeathsByDeathDateRollingRate": float,
    "newDeathsByDeathDateRollingSum": int,
    "cumDeathsByDeathDate": int,
    "cumDeathsByDeathDateRate": float,
    "newDeathsByPublishDate": int,
    "cumDeathsByPublishDate": int,
    "cumDeathsByPublishDateRate": float,
    "newDeaths28DaysByDeathDate": int,
    "newDeaths28DaysByDeathDateRate": float,
    "newDeaths28DaysByDeathDateRollingRate": float,
    "newDeaths28DaysByDeathDateRollingSum": int,
    "cumDeaths28DaysByDeathDate": int,
    "cumDeaths28DaysByDeathDateRate": float,
    "newDeaths28DaysByPublishDate": int,
    "cumDeaths28DaysByPublishDate": int,
    "cumDeaths28DaysByPublishDateRate": float,
    "newDeaths60DaysByDeathDate": int,
    "newDeaths60DaysByDeathDateRate": float,
    "newDeaths60DaysByDeathDateRollingRate": float,
    "newDeaths60DaysByDeathDateRollingSum": int,
    "cumDeaths60DaysByDeathDate": int,
    "cumDeaths60DaysByDeathDateRate": float,
    "newDeaths60DaysByPublishDate": int,
    "cumDeaths60DaysByPublishDate": int,
    "cumDeaths60DaysByPublishDateRate": float,
    "newOnsDeathsByRegistrationDate": int,
    "cumOnsDeathsByRegistrationDate": int,
    "cumOnsDeathsByRegistrationDateRate": float,
    "capacityPillarOneTwoFour": int,
    "newPillarOneTwoTestsByPublishDate": int,
    "capacityPillarOneTwo": int,
    "capacityPillarThree": int,
    "capacityPillarOne": int,
    "capacityPillarTwo": int,
    "capacityPillarFour": int,
    "cumPillarOneTwoTestsByPublishDate": int,
    "newPCRTestsByPublishDate": int,
    "cumPCRTestsByPublishDate": int,
    "plannedPCRCapacityByPublishDate": int,
    "plannedAntibodyCapacityByPublishDate": int,
    "newAntibodyTestsByPublishDate": int,
    "cumAntibodyTestsByPublishDate": int,
    "alertLevel": int,
    "transmissionRateMin": float,
    "transmissionRateMax": float,
    "transmissionRateGrowthRateMin": float,
    "transmissionRateGrowthRateMax": float,
    "newLFDTestsBySpecimenDate": int,
    "cumLFDTestsBySpecimenDate": int,
    "newVirusTestsByPublishDate": int,
    "cumVirusTestsByPublishDate": int,
    "newCasesBySpecimenDateDirection": str,
    "newCasesBySpecimenDateChange": int,
    "newCasesBySpecimenDateChangePercentage": float,
    "newCasesBySpecimenDateRollingSum": int,
    "newCasesBySpecimenDateRollingRate": float,
    "newCasesByPublishDateDirection": str,
    "newCasesByPublishDateChange": int,
    "newCasesByPublishDateChangePercentage": float,
    "newCasesByPublishDateRollingSum": int,
    "newCasesByPublishDateRollingRate": float,
    "newAdmissionsDirection": str,
    "newAdmissionsChange": int,
    "newAdmissionsChangePercentage": float,
    "newAdmissionsRollingSum": int,
    "newAdmissionsRollingRate": float,
    "newDeaths28DaysByPublishDateDirection": str,
    "newDeaths28DaysByPublishDateChange": int,
    "newDeaths28DaysByPublishDateChangePercentage": float,
    "newDeaths28DaysByPublishDateRollingSum": int,
    "newDeaths28DaysByPublishDateRollingRate": float,
    "newPCRTestsByPublishDateDirection": str,
    "newPCRTestsByPublishDateChange": int,
    "newPCRTestsByPublishDateChangePercentage": float,
    "newPCRTestsByPublishDateRollingSum": int,
    "newPCRTestsByPublishDateRollingRate": float,
    "newVirusTestsDirection": str,
    "newVirusTestsChange": int,
    "newVirusTestsChangePercentage": float,
    "newVirusTestsRollingSum": int,
    "newVirusTestsRollingRate": float,
    "newCasesByPublishDateAgeDemographics": list,
    "newCasesBySpecimenDateAgeDemographics": list,
    "newDeaths28DaysByDeathDateAgeDemographics": list,
    "variants": list,
    "uniqueCasePositivityBySpecimenDateRollingSum": float,
    "uniquePeopleTestedBySpecimenDateRollingSum": int,
    "newDailyNsoDeathsByDeathDateChange": int,
    "newDailyNsoDeathsByDeathDateChangePercentage": float,
    "newDailyNsoDeathsByDeathDateDirection": str,
    "newDailyNsoDeathsByDeathDateRollingSum": int,
    "newDailyNsoDeathsByDeathDate": int,
    "cumDailyNsoDeathsByDeathDate": int,
    "cumWeeklyNsoDeathsByRegDate": int,
    "cumWeeklyNsoDeathsByRegDateRate": float,
    "newWeeklyNsoDeathsByRegDate": int,
    "cumWeeklyNsoCareHomeDeathsByRegDate": int,
    "newWeeklyNsoCareHomeDeathsByRegDate": int,
    "newPeopleReceivingFirstDose": int,
    "cumPeopleReceivingFirstDose": int,
    "newPeopleReceivingSecondDose": int,
    "cumPeopleReceivingSecondDose": int,
    "cumPeopleVaccinatedFirstDoseByPublishDate": int,
    "cumPeopleVaccinatedSecondDoseByPublishDate": int,
    "newPeopleVaccinatedFirstDoseByPublishDate": int,
    "cumPeopleVaccinatedCompleteByPublishDate": int,
    "newPeopleVaccinatedCompleteByPublishDate": int,
    "newPeopleVaccinatedSecondDoseByPublishDate": int,
    "weeklyPeopleVaccinatedFirstDoseByVaccinationDate": int,
    "weeklyPeopleVaccinatedSecondDoseByVaccinationDate": int,
    "cumPeopleVaccinatedSecondDoseByVaccinationDate": int,
    "newCasesLFDConfirmedPCRBySpecimenDateRollingSum": int,
    "newCasesLFDConfirmedPCRBySpecimenDate": int,
    "newCasesLFDConfirmedPCRBySpecimenDateRollingRate": float,
    "cumCasesLFDOnlyBySpecimenDate": int,
    "cumCasesPCROnlyBySpecimenDate": int,
    "newCasesPCROnlyBySpecimenDateRollingSum": int,
    "newCasesLFDOnlyBySpecimenDateRollingRate": float,
    "newCasesPCROnlyBySpecimenDateRollingRate": float,
    "newCasesLFDOnlyBySpecimenDateRollingSum": int,
    "cumCasesLFDConfirmedPCRBySpecimenDate": int,
    "newCasesPCROnlyBySpecimenDate": int,
    "newCasesLFDOnlyBySpecimenDate": int,
    "newVaccinesGivenByPublishDate": int,
    "cumVaccinesGivenByPublishDate": int,
    "cumVaccinationFirstDoseUptakeByPublishDatePercentage": float,
    "cumVaccinationSecondDoseUptakeByPublishDatePercentage": float,
    "cumVaccinationCompleteCoverageByPublishDatePercentage": float,
    "newPeopleVaccinatedFirstDoseByVaccinationDate": int,
    "cumPeopleVaccinatedFirstDoseByVaccinationDate": int,
    "cumVaccinationSecondDoseUptakeByVaccinationDatePercentage": float,
    "VaccineRegisterPopulationByVaccinationDate": int,
    "newPeopleVaccinatedSecondDoseByVaccinationDate": int,
    "cumPeopleVaccinatedCompleteByVaccinationDate": int,
    "cumVaccinationFirstDoseUptakeByVaccinationDatePercentage": float,
    "cumVaccinationCompleteCoverageByVaccinationDatePercentage": float,
    "newPeopleVaccinatedCompleteByVaccinationDate": int,
    "vaccinationsAgeDemographics": list,
    "cumPeopleVaccinatedThirdDoseByPublishDate": int,
    "newPeopleVaccinatedThirdDoseByPublishDate": int,
    "cumVaccinationBoosterDoseUptakeByPublishDatePercentage": float,
    "cumPeopleVaccinatedThirdInjectionByPublishDate": int,
    "newPeopleVaccinatedThirdInjectionByPublishDate": int,
    "newPeopleVaccinatedBoosterDoseByPublishDate": int,
    "cumVaccinationThirdInjectionUptakeByPublishDatePercentage": float,
    "cumPeopleVaccinatedBoosterDoseByPublishDate": int,
    "cumPeopleVaccinatedAutumn22ByVaccinationDate50plus": int,
    "cumVaccinationAutumn22UptakeByVaccinationDatePercentage50plus": float,
    "newPeopleVaccinatedSpring23ByVaccinationDate75plus": int,
    "cumPeopleVaccinatedSpring23ByVaccinationDate75plus": int,
    "cumVaccinationSpring23UptakeByVaccinationDatePercentage75plus": float,
    "newPeopleVaccinatedAutumn23ByVaccinationDate65plus": int,
    "cumPeopleVaccinatedAutumn23ByVaccinationDate65plus": int,
    "cumVaccinationAutumn23UptakeByVaccinationDatePercentage65plus": float,
    "cumPCRTestsBySpecimenDate": int,
    "newPCRTestsBySpecimenDate": int,
    "newVirusTestsBySpecimenDate": int,
    "newVirusTestsBySpecimenDateChange": int,
    "newVirusTestsBySpecimenDateChangePercentage": float,
    "newVirusTestsBySpecimenDateDirection": str,
    "newVirusTestsBySpecimenDateRollingSum": int,
    # "newVirusTestsBySpecimenDateRollingRate": float,
    "newVirusTestsByPublishDateRollingSum": int,
    "cumVirusTestsBySpecimenDate": int,
    "cumVaccinationThirdInjectionUptakeByVaccinationDatePercentage": float,
    "newPeopleVaccinatedThirdInjectionByVaccinationDate": int,
    "cumPeopleVaccinatedThirdInjectionByVaccinationDate": int,
    "cumFirstEpisodesBySpecimenDate": int,
    "cumFirstEpisodesBySpecimenDateRate": float,
    "cumReinfectionsBySpecimenDate": int,
    "cumReinfectionsBySpecimenDateRate": float,
    "newFirstEpisodesBySpecimenDate": int,
    "newFirstEpisodesBySpecimenDateChange": int,
    "newFirstEpisodesBySpecimenDateChangePercentage": float,
    "newFirstEpisodesBySpecimenDateDirection": str,
    "newFirstEpisodesBySpecimenDateRollingRate": float,
    "newFirstEpisodesBySpecimenDateRollingSum": int,
    "newReinfectionsBySpecimenDate": int,
    "newReinfectionsBySpecimenDateChange": int,
    "newReinfectionsBySpecimenDateChangePercentage": float,
    "newReinfectionsBySpecimenDateDirection": str,
    "newReinfectionsBySpecimenDateRollingRate": float,
    "newReinfectionsBySpecimenDateRollingSum": int,
    "changeInNewDeaths28DaysByDeathDate": int,
    "previouslyReportedNewDeaths28DaysByDeathDate": int,
    "newFirstEpisodesBySpecimenDateAgeDemographics": list,
    "newReinfectionsBySpecimenDateAgeDemographics": list,
    "newCasesPillarOneBySpecimenDate": int,
    "newCasesPillarOneBySpecimenDateDirection": str,
    "newCasesPillarOneBySpecimenDateChange": int,
    "newCasesPillarOneBySpecimenDateChangePercentage": float,
    "newCasesPillarOneBySpecimenDateRollingSum": int,
    "newCasesPillarOneBySpecimenDateRollingRate": float,
    "cumCasesPillarOneBySpecimenDate": int,
    "cumCasesPillarOneBySpecimenDateRate": float,
    "newCasesPillarTwoBySpecimenDate": int,
    "newCasesPillarTwoBySpecimenDateDirection": str,
    "newCasesPillarTwoBySpecimenDateChange": int,
    "newCasesPillarTwoBySpecimenDateChangePercentage": float,
    "newCasesPillarTwoBySpecimenDateRollingSum": int,
    "newCasesPillarTwoBySpecimenDateRollingRate": float,
    "cumCasesPillarTwoBySpecimenDate": int,
    "cumCasesPillarTwoBySpecimenDateRate": float,
    "newDeaths28DaysByDeathDateChange": int,
    "newDeaths28DaysByDeathDateChangePercentage": float,
    "newVirusTestsByPublishDateChange": int,
    "newVirusTestsByPublishDateChangePercentage": float,
}


# Values must be provided in lowercase characters.
# Example:
# { "areaName": ["united kingdom"] }
#
# The API will the refuse the respond to any queries
# whose filter value for a specific parameter is NOT
# in the list.
RESTRICTED_PARAMETER_VALUES: Dict[str, List[str]] = dict()

# if ENVIRONMENT != "DEVELOPMENT":
#     RESTRICTED_PARAMETER_VALUES.update({
#         "areaName": [
#             "united kingdom"
#         ],
#         "areaType": [
#             "overview",
#             "nation",
#             "nhsregion"
#         ]
#     })

if ENVIRONMENT == "DEVELOPMENT":
    DATA_TYPES: Dict[str, Callable[[str], Any]] = {
        "hash": str,
        "areaType": str,
        DATE_PARAM_NAME: datetime,
        "areaName": str,
        "areaNameLower": str,
        "areaCode": str,
        "changeInCumCasesBySpecimenDate": int,
        "changeInNewCasesBySpecimenDate": int,
        "cumPeopleTestedBySpecimenDate": int,
        "covidOccupiedMVBeds": int,
        "covidOccupiedMVBedsWeekly": int,
        "covidOccupiedNIVBeds": int,
        "covidOccupiedOSBeds": int,
        "covidOccupiedOtherBeds": int,
        "cumAdmissions": int,
        "cumAdmissionsByAge": list,
        "cumCasesByPublishDate": int,
        "cumCasesBySpecimenDate": int,
        # 'cumDeathsByDeathDate': int,
        # 'cumDeathsByPublishDate': int,
        "cumDischarges": int,
        "cumDischargesByAge": list,
        "cumNegativesBySpecimenDate": int,
        "cumPeopleTestedByPublishDate": int,
        # 'cumPillarFourPeopleTestedByPublishDate': int,  # Currently excluded.
        "cumPillarFourTestsByPublishDate": int,
        "cumPillarOnePeopleTestedByPublishDate": int,
        "cumPillarOneTestsByPublishDate": int,
        "cumPillarThreeTestsByPublishDate": int,
        "cumPillarTwoPeopleTestedByPublishDate": int,
        "cumPillarTwoTestsByPublishDate": int,
        "cumTestsByPublishDate": int,
        "femaleCases": list,
        # 'femaleDeaths': list,
        "femaleNegatives": list,
        "hospitalCases": int,
        "hospitalCases_archive": int,
        "hospitalCasesWeekly": int,
        "hospitalCasesWeekly_archive": int,
        "maleCases": list,
        # 'maleDeaths': list,
        "maleNegatives": list,
        "malePeopleTested": list,
        "femalePeopleTested": list,
        "newAdmissions": int,
        "newAdmissions_archive": int,
        "newAdmissionsByAge": list,
        "newAdmissionsWeekly": int,
        "newAdmissionsWeekly_archive": int,
        "newCasesByPublishDate": int,
        "newCasesBySpecimenDate": int,
        "newDischarges": int,
        "newNegativesBySpecimenDate": int,
        "newPeopleTestedByPublishDate": int,
        # 'newPillarFourPeopleTestedByPublishDate': int,   # Currently excluded.
        "newPillarFourTestsByPublishDate": int,
        "newPillarOnePeopleTestedByPublishDate": int,
        "newPillarOneTestsByPublishDate": int,
        "newPillarThreeTestsByPublishDate": int,
        "newPillarTwoPeopleTestedByPublishDate": int,
        "newPillarTwoTestsByPublishDate": int,
        "newTestsByPublishDate": int,
        "nonCovidOccupiedMVBeds": int,
        "nonCovidOccupiedNIVBeds": int,
        "nonCovidOccupiedOSBeds": int,
        "nonCovidOccupiedOtherBeds": int,
        "plannedCapacityByPublishDate": int,
        "plannedPillarFourCapacityByPublishDate": int,
        "plannedPillarOneCapacityByPublishDate": int,
        "plannedPillarThreeCapacityByPublishDate": int,
        "plannedPillarTwoCapacityByPublishDate": int,
        "previouslyReportedCumCasesBySpecimenDate": int,
        "previouslyReportedNewCasesBySpecimenDate": int,
        "suspectedCovidOccupiedMVBeds": int,
        "suspectedCovidOccupiedNIVBeds": int,
        "suspectedCovidOccupiedOSBeds": int,
        "suspectedCovidOccupiedOtherBeds": int,
        "totalBeds": int,
        "totalMVBeds": int,
        "totalNIVBeds": int,
        "totalOSBeds": int,
        "totalOtherBeds": int,
        "unoccupiedMVBeds": int,
        "unoccupiedNIVBeds": int,
        "unoccupiedOSBeds": int,
        "unoccupiedOtherBeds": int,
        REPORT_DATE_PARAM_NAME: datetime,
        "newPeopleTestedBySpecimenDate": int,
        "newDeathsByDeathDate": int,
        "newDeathsByDeathDateRate": float,
        "newDeathsByDeathDateRollingRate": float,
        "cumDeathsByDeathDate": int,
        "cumDeathsByDeathDateRate": float,
        "newDeathsByPublishDate": int,
        "cumDeathsByPublishDate": int,
        "cumDeathsByPublishDateRate": float,
        "newDeaths28DaysByDeathDate": int,
        "newDeaths28DaysByDeathDateRate": float,
        "newDeaths28DaysByDeathDateRollingRate": float,
        "cumDeaths28DaysByDeathDate": int,
        "cumDeaths28DaysByDeathDateRate": float,
        "newDeaths28DaysByPublishDate": int,
        "cumDeaths28DaysByPublishDate": int,
        "cumDeaths28DaysByPublishDateRate": float,
        "newDeaths60DaysByDeathDate": int,
        "newDeaths60DaysByDeathDateRate": float,
        "newDeaths60DaysByDeathDateRollingRate": float,
        "cumDeaths60DaysByDeathDate": int,
        "cumDeaths60DaysByDeathDateRate": float,
        "femaleDeaths28Days": list,
        # "femaleDeaths60Days": int,
        "maleDeaths28Days": list,
        # "maleDeaths60Days": int,
        "newDeaths60DaysByPublishDate": int,
        "cumDeaths60DaysByPublishDate": int,
        "cumDeaths60DaysByPublishDateRate": float,
        "newOnsDeathsByRegistrationDate": int,
        "cumOnsDeathsByRegistrationDate": int,
        "cumOnsDeathsByRegistrationDateRate": float,
        "cumCasesBySpecimenDateRate": float,
        "cumCasesByPublishDateRate": float,
        "cumPeopleTestedByPublishDateRate": float,
        "cumAdmissionsRate": float,
        "cumDischargesRate": float,
        "capacityPillarOneTwoFour": int,
        "newPillarOneTwoTestsByPublishDate": int,
        "capacityPillarOneTwo": int,
        "capacityPillarThree": int,
        "capacityPillarOne": int,
        "capacityPillarTwo": int,
        "capacityPillarFour": int,
        "newPillarOneTwoFourTestsByPublishDate": int,
        "newCasesBySpecimenDateRate": float,
        "cumPillarOneTwoTestsByPublishDate": int,
        "newPCRTestsByPublishDate": int,
        "cumPCRTestsByPublishDate": int,
        "plannedPCRCapacityByPublishDate": int,
        "plannedAntibodyCapacityByPublishDate": int,
        "newAntibodyTestsByPublishDate": int,
        "cumAntibodyTestsByPublishDate": int,
        "newDeathsByDeathDateRollingSum": int,
        "newDeaths28DaysByDeathDateRollingSum": int,
        "newDeaths60DaysByDeathDateRollingSum": int,
        "newLFDTestsBySpecimenDate": int,
        "cumLFDTestsBySpecimenDate": int,
        "newVirusTestsByPublishDate": int,
        "newVirusTestsByPublishDateRollingSum": int,
        "cumVirusTestsByPublishDate": int,
        "alertLevel": int,
        "transmissionRateMin": float,
        "transmissionRateMax": float,
        "transmissionRateGrowthRateMin": float,
        "transmissionRateGrowthRateMax": float,
        "newCasesBySpecimenDateDirection": str,
        "newCasesBySpecimenDateChange": int,
        "newCasesBySpecimenDateChangePercentage": float,
        "newCasesBySpecimenDateRollingSum": int,
        "newCasesBySpecimenDateRollingRate": float,
        "newCasesByPublishDateDirection": str,
        "newCasesByPublishDateChange": int,
        "newCasesByPublishDateChangePercentage": float,
        "newCasesByPublishDateRollingSum": int,
        "newCasesByPublishDateRollingRate": float,
        "newAdmissionsDirection": str,
        "newAdmissionsChange": int,
        "newAdmissionsChangePercentage": float,
        "newAdmissionsRollingSum": int,
        "newAdmissionsRollingRate": float,
        "newDeaths28DaysByPublishDateDirection": str,
        "newDeaths28DaysByPublishDateChange": int,
        "newDeaths28DaysByPublishDateChangePercentage": float,
        "newDeaths28DaysByPublishDateRollingSum": int,
        "newDeaths28DaysByPublishDateRollingRate": float,
        "newPCRTestsByPublishDateDirection": str,
        "newPCRTestsByPublishDateChange": int,
        "newPCRTestsByPublishDateChangePercentage": float,
        "newPCRTestsByPublishDateRollingSum": int,
        "newPCRTestsByPublishDateRollingRate": float,
        "newVirusTestsDirection": str,
        "newVirusTestsChange": int,
        "newVirusTestsChangePercentage": float,
        "newVirusTestsRollingSum": int,
        "newVirusTestsRollingRate": float,
        "newOnsCareHomeDeathsByRegistrationDate": int,
        "cumOnsCareHomeDeathsByRegistrationDate": int,
        "newCasesByPublishDateAgeDemographics": list,
        "newCasesBySpecimenDateAgeDemographics": list,
        "newDeaths28DaysByDeathDateAgeDemographics": list,
        "uniqueCasePositivityBySpecimenDateRollingSum": float,
        "uniquePeopleTestedBySpecimenDateRollingSum": int,
        "newPeopleReceivingFirstDose": int,
        "cumPeopleReceivingFirstDose": int,
        "newPeopleReceivingSecondDose": int,
        "cumPeopleReceivingSecondDose": int,
        "newDailyNsoDeathsByDeathDateChange": int,
        "newDailyNsoDeathsByDeathDateChangePercentage": float,
        "newDailyNsoDeathsByDeathDateDirection": str,
        "newDailyNsoDeathsByDeathDateRollingSum": int,
        "cumWeeklyNsoDeathsByRegDate": int,
        "cumWeeklyNsoDeathsByRegDateRate": float,
        "newWeeklyNsoDeathsByRegDate": int,
        "cumWeeklyNsoCareHomeDeathsByRegDate": int,
        "newWeeklyNsoCareHomeDeathsByRegDate": int,
        "newDailyNsoDeathsByDeathDate": int,
        "cumDailyNsoDeathsByDeathDate": int,
        "cumPeopleVaccinatedFirstDoseByPublishDate": int,
        "cumPeopleVaccinatedSecondDoseByPublishDate": int,
        "newPeopleVaccinatedFirstDoseByPublishDate": int,
        "cumPeopleVaccinatedCompleteByPublishDate": int,
        "newPeopleVaccinatedCompleteByPublishDate": int,
        "newPeopleVaccinatedSecondDoseByPublishDate": int,
        "weeklyPeopleVaccinatedFirstDoseByVaccinationDate": int,
        "weeklyPeopleVaccinatedSecondDoseByVaccinationDate": int,
        "cumPeopleVaccinatedSecondDoseByVaccinationDate": int,
        "newCasesPCROnlyBySpecimenDateRollingSum": int,
        "newCasesLFDOnlyBySpecimenDateRollingRate": float,
        "newCasesLFDOnlyBySpecimenDate": int,
        "newCasesLFDConfirmedPCRBySpecimenDate": int,
        "newCasesLFDConfirmedPCRBySpecimenDateRollingRate": float,
        "cumCasesPCROnlyBySpecimenDate": int,
        "newCasesPCROnlyBySpecimenDateRollingRate": float,
        "newCasesLFDOnlyBySpecimenDateRollingSum": int,
        "cumCasesLFDConfirmedPCRBySpecimenDate": int,
        "cumCasesLFDOnlyBySpecimenDate": int,
        "newCasesPCROnlyBySpecimenDate": int,
        "newCasesLFDConfirmedPCRBySpecimenDateRollingSum": int,
        "cumVaccinationFirstDoseUptakeByPublishDatePercentage": float,
        "cumVaccinationSecondDoseUptakeByPublishDatePercentage": float,
        "cumVaccinationCompleteCoverageByPublishDatePercentage": float,
        "newVaccinesGivenByPublishDate": int,
        "cumVaccinesGivenByPublishDate": int,
        "newPeopleVaccinatedFirstDoseByVaccinationDate": int,
        "cumPeopleVaccinatedFirstDoseByVaccinationDate": int,
        "cumVaccinationSecondDoseUptakeByVaccinationDatePercentage": float,
        "VaccineRegisterPopulationByVaccinationDate": int,
        "newPeopleVaccinatedSecondDoseByVaccinationDate": int,
        "cumPeopleVaccinatedCompleteByVaccinationDate": int,
        "cumVaccinationFirstDoseUptakeByVaccinationDatePercentage": float,
        "cumVaccinationCompleteCoverageByVaccinationDatePercentage": float,
        "newPeopleVaccinatedCompleteByVaccinationDate": int,
        "vaccinationsAgeDemographics": list,
        "variants": list,
        "cumPeopleVaccinatedThirdDoseByPublishDate": int,
        "newPeopleVaccinatedThirdDoseByPublishDate": int,
        "cumVaccinationBoosterDoseUptakeByPublishDatePercentage": float,
        "cumPeopleVaccinatedThirdInjectionByPublishDate": int,
        "newPeopleVaccinatedThirdInjectionByPublishDate": int,
        "newPeopleVaccinatedBoosterDoseByPublishDate": int,
        "cumVaccinationThirdInjectionUptakeByPublishDatePercentage": float,
        "cumPeopleVaccinatedBoosterDoseByPublishDate": int,
        "cumPeopleVaccinatedAutumn22ByVaccinationDate50plus": int,
        "cumVaccinationAutumn22UptakeByVaccinationDatePercentage50plus": float,
        "newPeopleVaccinatedSpring23ByVaccinationDate75plus": int,
        "cumPeopleVaccinatedSpring23ByVaccinationDate75plus": int,
        "cumVaccinationSpring23UptakeByVaccinationDatePercentage75plus": float,
        "newPeopleVaccinatedAutumn23ByVaccinationDate65plus": int,
        "cumPeopleVaccinatedAutumn23ByVaccinationDate65plus": int,
        "cumVaccinationAutumn23UptakeByVaccinationDatePercentage65plus": float,
        "cumPCRTestsBySpecimenDate": int,
        "newPCRTestsBySpecimenDate": int,
        "newVirusTestsBySpecimenDate": int,
        "newVirusTestsBySpecimenDateChange": int,
        "newVirusTestsBySpecimenDateChangePercentage": float,
        "newVirusTestsBySpecimenDateDirection": str,
        "newVirusTestsBySpecimenDateRollingSum": int,
        # "newVirusTestsBySpecimenDateRollingRate": float,
        "cumVirusTestsBySpecimenDate": int,
        "cumVaccinationThirdInjectionUptakeByVaccinationDatePercentage": float,
        "newPeopleVaccinatedThirdInjectionByVaccinationDate": int,
        "cumPeopleVaccinatedThirdInjectionByVaccinationDate": int,
        "cumFirstEpisodesBySpecimenDate": int,
        "cumFirstEpisodesBySpecimenDateRate": float,
        "cumReinfectionsBySpecimenDate": int,
        "cumReinfectionsBySpecimenDateRate": float,
        "newFirstEpisodesBySpecimenDate": int,
        "newFirstEpisodesBySpecimenDateChange": int,
        "newFirstEpisodesBySpecimenDateChangePercentage": float,
        "newFirstEpisodesBySpecimenDateDirection": str,
        "newFirstEpisodesBySpecimenDateRollingRate": float,
        "newFirstEpisodesBySpecimenDateRollingSum": int,
        "newReinfectionsBySpecimenDate": int,
        "newReinfectionsBySpecimenDateChange": int,
        "newReinfectionsBySpecimenDateChangePercentage": float,
        "newReinfectionsBySpecimenDateDirection": str,
        "newReinfectionsBySpecimenDateRollingRate": float,
        "newReinfectionsBySpecimenDateRollingSum": int,
        "changeInNewDeaths28DaysByDeathDate": int,
        "previouslyReportedNewDeaths28DaysByDeathDate": int,
        "newFirstEpisodesBySpecimenDateAgeDemographics": list,
        "newReinfectionsBySpecimenDateAgeDemographics": list,
        "newCasesPillarOneBySpecimenDate": int,
        "newCasesPillarOneBySpecimenDateDirection": str,
        "newCasesPillarOneBySpecimenDateChange": int,
        "newCasesPillarOneBySpecimenDateChangePercentage": float,
        "newCasesPillarOneBySpecimenDateRollingSum": int,
        "newCasesPillarOneBySpecimenDateRollingRate": float,
        "cumCasesPillarOneBySpecimenDate": int,
        "cumCasesPillarOneBySpecimenDateRate": float,
        "newCasesPillarTwoBySpecimenDate": int,
        "newCasesPillarTwoBySpecimenDateDirection": str,
        "newCasesPillarTwoBySpecimenDateChange": int,
        "newCasesPillarTwoBySpecimenDateChangePercentage": float,
        "newCasesPillarTwoBySpecimenDateRollingSum": int,
        "newCasesPillarTwoBySpecimenDateRollingRate": float,
        "cumCasesPillarTwoBySpecimenDate": int,
        "cumCasesPillarTwoBySpecimenDateRate": float,
        "newDeaths28DaysByDeathDateChange": int,
        "newDeaths28DaysByDeathDateChangePercentage": float,
        "newVirusTestsByPublishDateChange": int,
        "newVirusTestsByPublishDateChangePercentage": float,
    }
