# Do not change any thing in this file. It is copied from common library

import json
import logging
from urllib import parse
import aiohttp
from typing import AsyncGenerator, Dict, List, Union
from common.std import Result

class HttpFailException(Exception):
    

    def __init__(self, status_code: int, content: str):
        self._status_code = status_code
        self._content = content

class BasicAuth:

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def as_aiohttp_auth(self):
        return aiohttp.BasicAuth(self._username, self._password) if self._username else None

    def as_aiohttp_header(self) -> Dict:
        return None

class ApiKeyAuthToken:

    def __init__(self, apiKey: str) -> None:
        self._apiKey = apiKey

    def as_aiohttp_auth(self):
        return None

    def as_aiohttp_header(self) -> Dict:
        return {"x-apiKey": self._apiKey}

class OAuth2AccessToken:

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    def as_aiohttp_auth(self):
        return None

    def as_aiohttp_header(self) -> Dict:
        return {"Authorization": "Bearer " + self._access_token}


class ApiClient:
    """
    Initialize the `ApiClient`
    """

    def __init__(self, context_path: str) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self._base_url = context_path
        self._auth: BasicAuth = BasicAuth("", "")

    def basic_auth(self, username: str, password: str):
        """
        Args:
            username (str): The username of grafana user
            password (str): The password of grafana user
        """
        # Initial client session
        self._auth = BasicAuth(username, password)

    def oauth2_access_token_auth(self, access_token: str):
        """
        Args:
            access_token (str): The OAuth2 access token
        """
        # Initial client session
        self._auth = OAuth2AccessToken(access_token)

    def apikey_auth(self, api_key: str):
        """
        Args:
            access_token (str): The OAuth2 access token
        """
        # Initial client session
        self._auth = ApiKeyAuthToken(api_key)        

    async def json_get(self, context_path: str, payload: Dict = {}, client_headers: Dict = {}) -> Result[str]:
        """
        Helper HTTP GET method

        Args:
            context_path (str): The context path relative to the base URL
            payload (Dict): The payload to post
            client_headers: The extra header information to pass into the request
        """
        headers = {
            "Accept": "application/json"
        }        
        extra_header = self._auth.as_aiohttp_header()
        if extra_header:
            headers.update(extra_header)
            
        if client_headers:
            headers.update(client_headers)

        # Initial client session
        async with aiohttp.ClientSession(
                base_url=self._base_url,
                auth=self._auth.as_aiohttp_auth()) as session:
            self.logger.debug("%12s url:<%s/%s>", "REQ-GET", self._base_url, context_path)
            self.logger.debug("%12s headers:<%s>", " ===> ", headers)
            # Post the session auth URL
            async with session.get(f"{context_path}?{parse.urlencode(payload)}", headers=headers, verify_ssl=False) as resp:
                self.logger.debug("%12s resp status:<%d>", " ===> ", resp.status)
                content_type: str = resp.headers["content-type"]
                content: str = None
                if "text/html" in content_type:
                    content = await resp.text()
                else:
                    content = await resp.json()

                if resp.status != 200:
                    return Result.from_error(HttpFailException(resp.status, content))
                else:
                    return Result.from_ok(content)

    async def json_post(self, context_path: str, payload: Union[Dict, str] = {}, client_headers: Dict = {}, params: Dict = {}) -> Result[str]:
        """
        Helper HTTP post method

        Args:
            context_path (str): The context path relative to the base URL
            payload (Dict): The payload to post
        """
        headers = {
            "Accept": "application/json"
        }
        extra_header = self._auth.as_aiohttp_header()
        if extra_header:
            headers.update(extra_header)

        if client_headers:
            headers.update(client_headers)

        # Initial client session
        async with aiohttp.ClientSession(
                base_url=self._base_url,
                auth=self._auth.as_aiohttp_auth()) as session:

            # Post the session auth URL
            kwargs = {}
            if isinstance(payload, Dict) or isinstance(payload, List):
                kwargs['json'] = payload
                self.logger.debug("%12s json payload:<%s>", " ===> ", payload)
            elif isinstance(payload, str):
                kwargs['data'] = payload
                self.logger.info("%12s data payload:<%s>", " ===> ", payload)
                
            actual_context_path = f"{context_path}?{parse.urlencode(params)}" if params else context_path
            
            self.logger.info("%12s url:<%s/%s>", "REQ-JSONPATH", self._base_url, actual_context_path)
            self.logger.info("%12s param:<%s>", "REQ-PARAM", params)
            self.logger.info("%12s payload:<%s>", "REQ-PAYLOAD", payload)
            self.logger.info("%12s headers:<%s>", " ===> ", headers)

            async with session.post(
                actual_context_path, headers=headers, verify_ssl=False, **kwargs
            ) as resp:
                self.logger.debug("%12s resp status:<%d>", " ===> ", resp.status)                
                if resp.status != 500:
                    pass

                content: str = await self.__fetch_content(resp)
                print("Content:", content)

                if resp.status >= 300:
                    return Result.from_error(HttpFailException(resp.status, content))
                else:
                    return Result.from_ok(content)
                
    async def json_post_raw(self, log_type: str, context_path: str, payload: Union[Dict, str] = {}, client_headers: Dict = {}):
        """
        Helper HTTP JSON post method and return the aiohttp Client response for caller to handle directly 

        Args:
            context_path (str): The context path relative to the base URL
            payload (Dict): The payload to post
        """
        headers = {
            "Accept": "application/json"
        }
        extra_header = self._auth.as_aiohttp_header()
        if extra_header:
            headers.update(extra_header)
            
        if client_headers:
            headers.update(client_headers)

        # Initial client session
        async with aiohttp.ClientSession(
            base_url=self._base_url,
            auth=self._auth.as_aiohttp_auth()) as session:

            self.logger.debug("%15s url:<%s/%s>", log_type, self._base_url, context_path)
            self.logger.debug("%15s headers:<%s>", " ===> ", headers)
            
            # Post the session auth URL
            kwargs = {}
            if isinstance(payload, Dict) or isinstance(payload, List):
                kwargs['json'] = payload
                self.logger.debug("%15s json payload:<%s>", " ===> ", payload)
            elif isinstance(payload, str):
                kwargs['data'] = payload
                self.logger.debug("%15s data payload:<%s>", " ===> ", payload)

            async with session.post(
                context_path, headers=headers, verify_ssl=False, **kwargs
            ) as resp:
                self.logger.debug("%15s resp status:<%d>", " ===> ", resp.status)                
                if resp.status != 500:
                    pass
                yield resp

    async def form_post(self, context_path: str, payload: Union[Dict, str] = {}) -> Result[str]:
        """
        Helper HTTP Form post method

        Args:
            context_path (str): The context path relative to the base URL
            payload (Dict): The payload to post
        """
        headers = {
            "Accept": "application/x-www-form-urlencoded"
        }
        extra_header = self._auth.as_aiohttp_header()
        if extra_header:
            headers.update(extra_header)

        # Initial client session
        async with aiohttp.ClientSession(
                base_url=self._base_url,
                auth=self._auth.as_aiohttp_auth()) as session:

            self.logger.info("%12s url:<%s/%s>", "REQ-FORMPOST", self._base_url, context_path)
            self.logger.debug("%12s headers:<%s>", " ===> ", headers)
            # Post the session auth URL
            kwargs = {}
            kwargs['data'] = payload
            
            self.logger.debug("%12s json payload:<%s>", " ===> ", payload)

            async with session.post(
                context_path, headers=headers, verify_ssl=False, **kwargs
            ) as resp:
                self.logger.debug("%12s resp status:<%d>", " ===> ", resp.status)
                if resp.status != 500:
                    pass

                content: str = await self.__fetch_content(resp)
                # print("Content:", content)

                if resp.status >= 300:
                    return Result.from_error(HttpFailException(resp.status, content))
                else:
                    return Result.from_ok(content)
                

    async def json_patch(self, context_path: str, payload: Union[Dict, str] = {}, client_headers: Dict = {}) -> Result[str]:
        """
        Helper HTTP post method

        Args:
            context_path (str): The context path relative to the base URL
            payload (Dict): The payload to post
        """
        headers = {
            "Accept": "application/json"
        }
        extra_header = self._auth.as_aiohttp_header()
        if extra_header:
            headers.update(extra_header)
                        
        if client_headers:
            headers.update(client_headers)

        # Initial client session
        async with aiohttp.ClientSession(
                base_url=self._base_url,
                auth=self._auth.as_aiohttp_auth()) as session:

            self.logger.debug("%12s url:<%s/%s>", "REQ-PATCH",
                              self._base_url, context_path)
            # Post the session auth URL

            kwargs = {}
            if isinstance(payload, Dict) or isinstance(payload, List):
                kwargs['json'] = payload
            elif isinstance(payload, str):
                kwargs['data'] = payload

            async with session.patch(
                context_path, headers=headers, verify_ssl=False, **kwargs
            ) as resp:
                # print(f"URL: {self._base_url}/{context_path}")
                # print("Json:", payload)
                # print("Status:", resp.status)
                # print(resp.headers)

                if resp.status != 500:
                    pass

                content: str = await self.__fetch_content(resp)

                # print("Content:", content)

                if resp.status >= 300:
                    return Result.from_error(HttpFailException(resp.status, content))
                else:
                    return Result.from_ok(content)

    async def json_delete(self, context_path: str, payload: Dict = {}, client_headers: Dict = {}) -> Result[str]:
        """
        Helper HTTP delete method

        Args:
            context_path (str): The context path relative to the base URL
            payload (Dict): The payload to delete
        """
        headers = {
            "Accept": "application/json"
        }
        extra_header = self._auth.as_aiohttp_header()
        if extra_header:
            headers.update(extra_header)
            
        if client_headers:
            headers.update(client_headers)

        # Initial client session
        async with aiohttp.ClientSession(
                base_url=self._base_url,
                auth=self._auth.as_aiohttp_auth()) as session:
            # Post the session auth URL
            async with session.delete(
                context_path, verify_ssl=False, headers=headers, json=payload
            ) as resp:
                # print("Json:", payload)
                # print("Status:", resp.status)

                if resp.status != 500:
                    pass

                content: str = await self.__fetch_content(resp)

                if resp.status >= 300:
                    return Result.from_error(HttpFailException(resp.status, content))
                else:
                    return Result.from_ok(content)

    def __get_content_type(self, headers: Dict):
        content_type = headers.get("Content-type", None)
        return content_type if content_type else headers.get("content-type", None)

    async def __fetch_content(self, resp: aiohttp.ClientResponse) -> str:
        clen = int(resp.headers["Content-Length"]
                   ) if "Content-Length" in resp.headers else -1
        
        
        content_type: str = self.__get_content_type(resp.headers)
        if resp.status != 500:
            pass
        
        self.logger.debug("%12s resp content length:<%d>", " ===> ", clen)
        self.logger.debug("%12s resp content type:<%s>", " ===> ", content_type)        

        if clen != 0:
            if content_type and ("text/html" in content_type or "text/plain" in content_type):
                content = await resp.text()
            else:
                content = await resp.json()
        else:
            content = ""
            
        if (clen < 1024):
            self.logger.debug("%12s resp content :<%s>", " ===> ", content)   
        else:
            self.logger.debug("%12s content not printed due to too large", " ===> ")   
                        
        return content
