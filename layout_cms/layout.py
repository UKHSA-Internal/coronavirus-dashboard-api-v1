#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from json import dumps
from os.path import join as join_path, split as split_path, splitext
from asyncio import get_event_loop, Lock
from http import HTTPStatus
from typing import NoReturn
from re import compile as re_compile, DOTALL, VERBOSE, MULTILINE

# 3rd party:
from azure.functions import HttpRequest, HttpResponse
from yaml import load as load_yaml, FullLoader

# Internal:
try:
    # Imports within the Function
    from __app__.github_utils import process_github_files
    from __app__.github_utils.types import CallbackType, FileFetcherType
    from __app__.storage import StorageClient
    from __app__ import processor_settings
except ImportError:
    # Local alternative
    from github_utils import process_github_files
    from github_utils.types import CallbackType, FileFetcherType
    from storage import StorageClient
    import processor_settings

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'process_layouts'
]


STORAGE_CONTAINER = "publicdata"
STORAGE_PATH = "assets/cms"

REPOSITORY_NAME = "coronavirus-dashboard-layouts"
REPOSITORY_BASE = f"{REPOSITORY_NAME}-{processor_settings.GITHUB_BRANCH}"
REPOSITORY_BASE_PATH = join_path(REPOSITORY_BASE, "Layouts")
REPOSITORY_ARCHIVE_URL = f"{REPOSITORY_NAME}/archive/{processor_settings.GITHUB_BRANCH}.zip".lower()


EXCLUDED_ITEMS = [
    "README.md",
    "LICENSE",
    ".github_utils",
    ".gitignore"
]


DEV_ONLY_BLOCK_PATTERN = re_compile(r"""
    (
        (\s*[#\s]*){{\s*StartDevOnlyBlock\s*}}
        .+?
        (\2){{\s*EndDevOnlyBlock\s*}}
    )
""", flags=VERBOSE | DOTALL)


DEV_ONLY_LINE_PATTERN = re_compile(r"""
    ^(
        .*[#].*
        {{\s*DevOnly\s*}}
        .*
    )$
""", flags=VERBOSE | MULTILINE)


async def prepare_data(data: str) -> str:
    """
    Prepares YAML files by applying the relevant ``DevOnly`` rules,
    the converts the data into JSON and produces a minified JSON
    as output.

    Parameters
    ----------
    data: str
        Raw YAML data to be processed.

    Returns
    -------
    str
        Minified JSON data.
    """
    if processor_settings.ENVIRONMENT != processor_settings.DEV_ENV:
        data = DEV_ONLY_BLOCK_PATTERN.sub("", data)
        data = DEV_ONLY_LINE_PATTERN.sub("", data)

    if processor_settings.ENVIRONMENT != processor_settings.DEV_ENV and "devonly" in data.lower():
        raise RuntimeError("Contains unauthorised materials")

    data = load_yaml(data, Loader=FullLoader)

    return dumps(data, separators=processor_settings.JSON_SEPARATORS)


async def process_and_upload_data(path: str, get_file_data: FileFetcherType,
                                  container: str, base_path: str) -> NoReturn:
    """
    Uploads processed files to the storage using the correct
    caching and ``content-type`` specs.

    Parameters
    ----------
    path: str
        Path (within the storage container) in which the
        file is to be stored.

    get_file_data: FileFetcherType

    base_path: str

    container: str
        Storage container in which the file is to be stored.

    Returns
    -------
    NoReturn
    """
    _, file_name = split_path(path)
    # Files are stored as JSON - the extension must be updated:
    file_name, _ = splitext(file_name)
    file_name = f"{file_name}.json"

    blob_path = str.join(processor_settings.URL_SEPARATOR, [STORAGE_PATH, file_name])

    raw_data = await get_file_data(path, base_path)
    data = await prepare_data(raw_data)

    # Uploading the data
    with StorageClient(container=container, path=blob_path) as client:
        async with Lock():
            client.upload(data=data)

process_and_upload_data: CallbackType = process_and_upload_data


async def process_layouts(req: HttpRequest) -> HttpResponse:
    logging.info(f"--- Web hook has triggered the function. Starting the process...")

    event_loop = get_event_loop()

    try:
        task = process_github_files(
            repository_url=REPOSITORY_ARCHIVE_URL,
            callback=process_and_upload_data,
            excluded=EXCLUDED_ITEMS,
            base_path=REPOSITORY_BASE_PATH,
            container=STORAGE_CONTAINER
        )

        event_loop.create_task(task)

    except Exception as err:
        logging.exception(err)
        return HttpResponse(status_code=int(HTTPStatus.INTERNAL_SERVER_ERROR))

    return HttpResponse(status_code=int(HTTPStatus.OK))


if __name__ == "__main__":
    # Local test
    from asyncio import gather

    loop = get_event_loop()

    proc = process_layouts(HttpRequest(method="POST", url="", body=b''))
    loop.run_until_complete(gather(proc))

