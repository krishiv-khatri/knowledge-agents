import glob
import logging
import os
import pathlib
from fastapi import FastAPI, status

from web.types import ErrResponse

default_response = {
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrResponse},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrResponse},
}

default_oauth2_protected_response = {
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ErrResponse, "description": "Unauthorized"},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrResponse},
}


def load_app_doc(prefix: str, app: FastAPI, fallback=True):
    """
    Since
    ------
    0.0.1
    """
    path = os.path.join(
        os.path.dirname(__file__), "_redoc", "app", prefix, "**", "README.md"
    )
    logging.info(
        f"================ Redoc App Route Discovery ({prefix}) ================== "
    )
    logging.info(f"Path: {path} ")
    for api_description_path in glob.glob(path, recursive=True):
        with open(api_description_path, "r") as f:
            path = pathlib.Path(api_description_path)
            logging.info(api_description_path)
            if not app.description:
                app.description = f.read()

    if fallback:
        load_app_doc("default", app, False)


def load_tag_doc(prefix: str, api: FastAPI):
    """
    Since
    ------
    0.0.1
    """
    path = os.path.join(
        os.path.dirname(__file__), "_redoc", "tags", prefix, "**", "README.md"
    )
    logging.info(f"================ Redoc Tag Discovery ({prefix}) ================== ")
    logging.info(f"Path: {path} ")
    openapi_tags = []
    for api_description_path in glob.glob(path, recursive=True):
        with open(api_description_path, "r") as f:
            path = pathlib.Path(api_description_path)
            logging.info(api_description_path)
            openapi_tags.append({"name": path.parent.stem, "description": f.read()})
            # print(api_description_path)

    def sorted_fn(item):
        logging.info(item)
        if "name" in item:
            if item["name"] == "oauth2":
                # logging.info("Return sorted 0")
                return 0
            else:
                hash_val = hash(item["name"])
                # logging.info(f"Return sorted {hash_val}")
                return abs(hash_val)
        else:
            # logging.info(f"Return sorted -1")
            return -1

    # logging.info(openapi_tags)
    openapi_tags = sorted(openapi_tags, key=sorted_fn)
    # logging.info(openapi_tags)
    api.openapi_tags = openapi_tags


def load_api_doc(prefix: str, api: FastAPI, fallback=True):
    """
    Since
    ------
    0.0.1
    """
    path = os.path.join(
        os.path.dirname(__file__), "_redoc", "api", prefix, "**", "README.md"
    )

    logging.info(
        f"================ Redoc Route Discovery ({prefix}) ================== "
    )
    logging.info(f"Path: {path} ")
    for api_description_path in glob.glob(path, recursive=True):
        with open(api_description_path, "r") as f:
            path = pathlib.Path(api_description_path)
            logging.info(api_description_path)

            for route in api.routes:
                if route.name == path.parent.stem:
                    logging.info(f"{route.name} try match {path.parent.stem}")
                    if not route.description:
                        route.description = f.read()

            # print(api_description_path)
    if fallback:
        load_api_doc("default", api, False)
