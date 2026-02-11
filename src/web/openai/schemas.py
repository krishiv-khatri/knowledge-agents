from datetime import datetime
from typing import Dict, List, Optional
from typing_extensions import Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from web.openai.models import OpenAISetting

class OpenAIUpdateable(BaseModel):
    """
    The base model which include all fields which are updatable

    """

    model: Optional[str] = Field(
        default=None,
        description="The model name used for the chat, use the default model if not specified",
    )
    """
    The model name used for the chat, use the default model if not specified        
    
    Since 
    -----
    0.0.1
    """
    locale: Optional[Literal["en-US", "zh-HK", "zh-CN"]] = Field(
        default=None,
        description="The locale for the chat conversation, use default language (English) if not specified",
    )
    """
    The model language used for the chat, use default language (English) if not specified
    
    Since 
    -----
    0.0.1
    """
    config: Optional[Dict[str, str]] = Field(default={})
    """
    Extra configuration to pass information. 
    
    Since 
    -----
    0.0.1
    """


class OpenAIRequest(OpenAIUpdateable):
    model_config = ConfigDict(populate_by_name=True)
    """
    The report type that this OpenAI request want to 
    
    Since 
    -----
    0.0.1
    """
    labels: Dict[str, str] = Field(default={})
    """
    The label data are the set of data for filtering which installation you want to generate the chat
    
    Since 
    -----
    0.0.1
    """

    def is_rag(self) -> bool:
        """
        Whether this request has enabled RAG or not

        Since
        -----
        0.0.1
        """
        return self.config.get("rag", False)

    def is_convert_to_html(self) -> bool:
        """
        Whether this request converted to HTML. It is usually used by prompt

        Since
        -----
        0.0.1
        """
        return self.config.get("convert_to_html", False)

    @property
    def safe_locale(self) -> str:
        """
        Return the locale code of this request. Return 'en-US' if locale is not specified

        Since
        -----
        0.0.1
        """
        return self.locale if self.locale else "en-US"


class OpenAISettingModel(BaseModel):
    """
    The OpenAI setting model holds the OpenAI Key used for GPT service.

    Only 3.5-turbo and 4 are supported.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(
        alias="name", title="The unique setting key to identify the OpenAPI setting"
    )
    """
    The unique setting key to identify the OpenAPI setting
    
    Since
    -----
    0.0.1
    """
    provider: Literal["openai", "azure-openai", "echo-llm", "nvidia-ai"] = Field(
        alias="provider",
        title="The OpenAI provider",
        description="Right now it support openAI, AzureOpenAI, NvidiaAI",
    )
    """
    The LLM service provider, right now it support OpenAI and AzureOpenAI only.
    
    Since
    -----
    0.0.1
    """
    model: str = Field(alias="model", title="The GPT model you want to run with")
    """
    The LLM model, either 'gpt-3.5-turbo', 'gpt-4', 'gpt-4o-mini'
    
    Since
    -----
    0.0.1
    """
    api_key: str = Field(
        alias="apiKey",
        title="The ChatGPT API key",
        description="The key should start with 'sk-Pmed...'",
    )
    """
    The LLM API key, The key should start with 'sk-Pmed...' if you are using OpenAI.
    
    Since
    -----
    0.0.1
    """
    chat_timeout_in_seconds: int = Field(
        default=60, alias="chatTimeoutInSeconds", max=240
    )
    """
    The service will consider as timeout if GPT does not provide any feedback to us.
    
    Since
    -----
    0.0.1
    """
    extra_configs: Dict[str, str] = Field(
        alias="extraConfigs",
        default={},
        title="The extra configuration for creating the provider stub",
    )
    """
    LLM service specific configuration.
    
    For azure LLM, you need to fill the following in order to work.
    1. `api_version`
    2. `azure_endpoint`
    3. `azure_deployment`
    
    Since
    -----
    0.0.1
    """

    def as_sql_model(self) -> OpenAISetting:
        """
        Convert to ORM model for persistence
        """
        return OpenAISetting(**self.model_dump())


class OpenAISettingUpdateModel(OpenAISettingModel):

    created_at: datetime = Field(title="The create datetime for the setting")
    """
    When is the setting has been created
    
    Since
    -----
    0.0.1
    """
    updated_at: datetime = Field(title="The update datetime for the setting")
    """
    When is the setting has been updated
    
    Since
    -----
    0.0.1
    """