from typing import List
from pydantic import BaseModel, Field, RootModel

class IngestConfig(BaseModel):
    """
    Since
    --------
    0.0.7
    """
    relative_url: str = Field(title="The sharepoint site url. It must start with /site")
    """
    The sharepoint site url. It must start with /site

    Since
    --------
    0.0.7
    """
    recursive: bool = Field(title="Whether we want to do scan the subfolder", default=True)
    """
    The boolean flag whether all subfolder under the `url` specified by `relative_url` will be scanned

    Since
    --------
    0.0.7
    """
    include_regex: List[str] = Field(title="The regex for searching which documents need to be included", default="(.*)\.docx")
    """
    The regular expression for searching which oducments need to be included

    Since
    --------
    0.0.7
    """
    exclude_regex: List[str] = Field(title="The regex for searching which documents need to be included", default="")
    """
    The regular expression for searching which oducments need to be excluded

    Since
    --------
    0.0.7
    """

class IngestConfigCollection(RootModel[List[IngestConfig]]):
    """
    Since
    --------
    0.0.7
    """