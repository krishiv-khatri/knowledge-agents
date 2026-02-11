from typing import Optional
from sqlalchemy import Engine

from web.openai.models import OpenAISetting
from sqlalchemy.orm import Session

class OpenAISettingRepo:
    """
    The SQLAlchemy repository for open AI setting

    Since
    --------
    0.0.1 Stable
    """

    def __init__(self, engine: Engine):
        """

        Since
        --------
        0.0.1 Stable
        """
        self._engine = engine

    def find_default_setting(self) -> OpenAISetting:
        """
        Find the default open AI setting

        Since
        --------
        0.0.1 Stable
        """
        with Session(self._engine) as session:
            sql = session.query(OpenAISetting).where(OpenAISetting.default)
            found: OpenAISetting = sql.first()
            return found

    def find_setting_by_model(self, model: str) -> Optional[OpenAISetting]:
        """
        Find the open provider setting based on the given `model`.

        Args:
            model (str): The model name like 'Qwen/Qwen3-32B-AWQ'

        Since
        --------
        0.0.8
        """
        with Session(self._engine) as session:
            sql = session.query(OpenAISetting).where(OpenAISetting.model == model)
            found: OpenAISetting = sql.first()
            return found
