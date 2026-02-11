from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from web.doc import default_response
from web.openai.models import OpenAISetting
from web.openai.schemas import OpenAISettingModel, OpenAISettingUpdateModel
from web.openai.dependencies import require_openai_setting
from web.persistence.dependencies import require_session
from web.types import ErrResponse, OkResponse

router = APIRouter(prefix="/api/v1")

tags = ["openai"]

CREATE_SETTING_OK_RESPONSE = OkResponse(status="ok", message="ok", data="ok")


@router.post(
    f"/openai",
    tags=tags,
    include_in_schema=True,
    responses={
        status.HTTP_200_OK: {
            "model": OkResponse[str],
            "content": {
                "application/json": {"example": CREATE_SETTING_OK_RESPONSE.model_dump()}
            },
        },
        **default_response,
    },
)
async def create_setting(
    setting: OpenAISettingModel, async_session: AsyncSession = Depends(require_session)
):
    """
    Enable the OpenAI feature to the data integrator system.

    Since
    --------
    0.0.1
    """
    orm = setting.as_sql_model()
    async_session.add(orm)
    await async_session.commit()
    return CREATE_SETTING_OK_RESPONSE


MISSING_OPENAI_CONFIG_RESPONSE = ErrResponse(
    status="fail",
    code=12000,
    message="There is no OpenAI configuration setup. Please consult admin for enabling OpenAI binding",
    errors=[],
)


@router.get(
    f"/openai",
    tags=tags,
    include_in_schema=True,
    responses={
        status.HTTP_200_OK: {"model": OkResponse[OpenAISettingUpdateModel]},
        status.HTTP_425_TOO_EARLY: {
            "model": ErrResponse,
            "content": {
                "application/json": {
                    "example": MISSING_OPENAI_CONFIG_RESPONSE.model_dump()
                }
            },
        },
        **default_response,
    },
)
async def get_setting(openai_setting: OpenAISetting = Depends(require_openai_setting)):
    """
    Get the default OpenAI setting binded to this API server.

    Since
    --------
    0.0.1
    """
    result = openai_setting.as_dict()
    # Maskout the api_key
    result["api_key"] = "*******"
    # TODO:
    extra_config = result["extra_configs"]
    if extra_config:
        result["extraConfigs"] = openai_setting.extra_configs
    else:
        result["extraConfigs"] = {}

    if result:
        return OkResponse(status="ok", data=OpenAISettingUpdateModel(**result))
    else:
        # Will not happen as it will throw HTTP425 is openai setting is missing
        pass
