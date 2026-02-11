from typing import Dict
from common.api.http.client import ApiClient
from common.std import Result

class ConfluenceApiClient(ApiClient):
    """

    Since
    --------
    0.0.1
    """

    def __init__(self, context_path: str, personal_access_token: str) -> None:
        """
        Args:
            context_path: The context base URL like `https://confluence.example.com/`
            personal_access_token: The token for accessing the confluence API

        Since
        --------
        0.0.1
        """
        super().__init__(context_path)
        self._headers = {"Accept": "application/json", "Authorization": f"Bearer {personal_access_token}"}

    async def aget_all_page_properties(self, space: str):
        """
        Fetch all page properties using Confluence REST API v2.
        Returns a list of (id, ).

        Since
        --------
        0.0.1 NOT STABLE, Method name will be changed
        """
        properties = []
        payload: Dict = {
            "start": 0,
            "limit": 1500,
            "cql": f"space={space} AND type=page"
        }
        result: Result[Dict] = await self.json_get("/rest/api/search", payload, self._headers)
        json = result.unwrap()
        for page in json.get("results", []):
            page_id = page["content"]["id"]
            title = page["content"]["title"]
            last_edited = page["lastModified"]
            properties.append((page_id, title, last_edited))
        # TODO: Support pagination again
        # Pagination: look for 'next' link in headers
        # next_link = None
        # if "Link" in response.headers:
        #     import re
        #     match = re.search(r'<([^>]+)>;\s*rel="next"', response.headers["Link"])
        #     if match:
        #         next_link = match.group(1)
        #     if not next_link:
        #         next_link = data.get("_links", {}).get("next")
        #         if next_link and not next_link.startswith("http"):
        #             next_link = f"{CONFLUENCE_BASE_URL}{next_link}"
        # url = next_link
        return properties

    async def aget_page_content(self, page_id: str):
        """
        Fetch the HTML content of a page by ID using body.storage.

        Returns the HTML string.

        Since
        --------
        0.0.1 NOT STABLE, Method name will be changed
        """
        payload: Dict = {
            "expand": "body.storage"
        }
        result: Result[Dict] = await self.json_get(f"/rest/api/content/{page_id}", payload, self._headers)
        json = result.unwrap()
        html = json["body"]["storage"]["value"]
        return html
