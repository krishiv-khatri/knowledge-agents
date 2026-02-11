import re
import os
import asyncio
import datetime
import glob
import logging
from os import path
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Union
from office365.runtime.auth.client_credential import ClientCredential
from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext
from office365.sharepoint.files.collection import FileCollection
from office365.sharepoint.files.file import File
from urllib.parse import quote
from common.api.http.client import ApiClient

class SharepointApiClient(ApiClient):
    """
    The sharepoint API client is the thin wrapper for the office365 API.

    Note that the office365 API does not natively SUPPORT asyncio. 
    
    Therefore most of API are simply wrapped by using `run_in_executor` which the performance might not be good enough

    Since
    --------
    0.0.3
    """
    def __init__(self, site_url: str, credential: Union[UserCredential, ClientCredential]) -> None:
        """
        Args:
            site_url (str): The sharepoint URL
            credential (Union[UserCredential, ClientCredential]): The credential type, either user or client ID/secret
            
        Since
        --------
        0.0.3 (Revamped at 0.0.7)
        """
        super().__init__(site_url)
        self._credential = credential
        if isinstance(credential, ClientCredential):
            raise NotImplementedError("Client credential are not yet supported")

    async def test_oauth(self) -> bool:
        """
        Test whether the sharepoint connectivity is ok or not

        Return
                
        Since
        --------
        0.0.7
        """
        try:
            # Initialize client context with client credentials
            ctx = ClientContext(self._base_url).with_credentials(self._credential)
            # Test authentication by retrieving the web title
            web = ctx.web
            ctx.load(web)
            self._aexecute_query(ctx)
            self.logger.info(f"Authentication successful! Site title: ")
            return True
        except Exception as e:
            self.logger.info(f"Authentication failed: {str(e)}")
            return False

    async def aget_all_page_properties(self) -> Dict[str, Dict]: # type: ignore
        """
        DEPRECATED

        Since
        --------
        0.0.3
        """
        result = []

        for func_spec_path in glob.glob("data/func_spec/**/Functional Spec*.docx", recursive=True):
            stem = Path(func_spec_path).stem
            if "Archive" in func_spec_path or "TBD" in func_spec_path or "XX" in func_spec_path:
                print(f"Skipping {stem}")
                continue
            else:
                print(stem)
                result.append({ "page_id": func_spec_path, "title": stem, "last_modified": 0 })
        return result
    
    async def list_folder_contents(self, folder_relative_url: str, recursive: bool, exclude_regex: str = "", include_regex: str = "", limit: int = 100) -> AsyncGenerator[Dict, None]:
        """
        (UNSTABLE) List files and subfolders in a specific SharePoint folder.

        Args:
            folder_relative_url (str): The server-relative URL of the folder (e.g., "/sites/your-site/Shared Documents/FolderName").
            recursive (bool): 
            exclude_regex (str): 
            include_regex (str):
            limit (int): 

        Return:

        Since
        --------
        0.0.7 
        """
        # Initialize the client context with credentials
        ctx = ClientContext(self._base_url).with_credentials(self._credential)

        # Access the folder by its server-relative URL
        folder = ctx.web.get_folder_by_server_relative_url(folder_relative_url)

        # Load files and subfolders
        files = folder.files
        subfolders = folder.folders
        ctx.load(files)
        ctx.load(subfolders)
        # Execute the query to fetch data
        await self._aexecute_query(ctx)

        self.logger.info(f"{'INGEST':15} Sharepoint relative URL: {folder_relative_url}")

        is_debug = self.logger.isEnabledFor(logging.DEBUG)

        exclude_re = re.compile(exclude_regex)
        include_re = re.compile(include_regex)

        # Sharepoint file has following basic properties that we can use
        # Print files        
        for file in files:
            function_spec_result: List[File] = []
            full_url = quote(file.properties['ServerRelativeUrl'])
            #print(full_url)
            if exclude_re.match(full_url):
                if is_debug:
                    self.logger.debug(f"{'SKIPPED':15} --> <name: {file.name} DUE to exclude regex rule <rule: {exclude_regex}>")
            elif include_re.match(full_url):
                if is_debug:
                    mod_date: datetime.datetime = file.properties['TimeLastModified']
                    self.logger.debug(f"{'INCLUDED':15} --> <name: {file.name}, last_mod:{mod_date.strftime('%m/%d/%Y %H:%M:%S')}> DUE to include regex rule rule <rule: {include_regex}>")
                function_spec_result.append(file)

            function_spec_result.sort(key=lambda file : file.name, reverse=True)
            if len(function_spec_result) > 0:
                unique_id = function_spec_result[0].properties['UniqueId']
                ingest_file_name = function_spec_result[0].properties['Name']
                ingest_full_url = quote(function_spec_result[0].properties['ServerRelativeUrl'])

                mod_date: datetime.datetime = function_spec_result[0].properties['TimeLastModified']
                self.logger.info(f"{'INGEST':15} --> <name: {ingest_file_name}, last_mod:{mod_date.strftime('%m/%d/%Y %H:%M:%S')}>")
                self.logger.info(f"{'INGEST':15} --> <unique_id: {unique_id}, full_url:{full_url}>")
                yield { "page_id": unique_id, "url": f"{self._base_url}{ingest_full_url}?web=1", "title": ingest_file_name, "last_modified": mod_date.isoformat() }
            #print(f"- {file.properties['Name']} (Size: {file.properties['Length']} bytes)")

        # Print subfolders
        # print("\nSubfolders in the folder:")
        cnt = 0
        for subfolder in subfolders:
            if cnt > limit:
                return

            self.logger.info(f"{'INGEST':15} SCAN:{subfolder}>")
            #if is_debug:
            if exclude_re.match(subfolder.name):
                if is_debug:
                    self.logger.debug(f"{'SKIPPED':15} -> <name: {subfolder_file.name} DUE to exclude regex rule <rule: {exclude_regex}>")

            subfolder_files: FileCollection = subfolder.get_files(recursive)
            ctx.load(subfolder_files)
            # Execute the query to fetch data
            await self._aexecute_query(ctx)
            #print(f"- {subfolder.properties['Name']}")
            await asyncio.sleep(1)
            
            function_spec_result: List[File] = []
            for subfolder_file in subfolder_files:
                full_url = quote(subfolder_file.properties['ServerRelativeUrl'])
                if exclude_re.match(full_url):
                    if is_debug:
                        self.logger.debug(f"{'SKIPPED':15} --> <name: {subfolder_file.name} DUE to exclude regex rule <rule: {exclude_regex}>")
                elif include_re.match(full_url):
                    if is_debug:
                        mod_date: datetime.datetime = subfolder_file.properties['TimeLastModified']
                        self.logger.debug(f"{'INCLUDED':15} --> <name: {subfolder_file.name}, last_mod:{mod_date.strftime('%m/%d/%Y %H:%M:%S')}> DUE to include regex rule rule <rule: {include_regex}>")
                    function_spec_result.append(subfolder_file)
            
            # Sort by desending order, larger version number comes first
            function_spec_result.sort(key=lambda file : file.name, reverse=True)
            if len(function_spec_result) > 0:
                unique_id = function_spec_result[0].properties['UniqueId']
                ingest_file_name = function_spec_result[0].properties['Name']
                ingest_full_url = quote(function_spec_result[0].properties['ServerRelativeUrl'])
                mod_date: datetime.datetime = function_spec_result[0].properties['TimeLastModified']
                self.logger.info(f"{'INGEST':15} --> <name: {ingest_file_name}, last_mod:{mod_date.strftime('%m/%d/%Y %H:%M:%S')}>")
                self.logger.info(f"{'INGEST':15} --> <unique_id: {unique_id}, full_url:{full_url}>")
                yield { "page_id": unique_id, "url": f"{self._base_url}{ingest_full_url}?web=1", "title": ingest_file_name, "last_modified": mod_date.isoformat() }
            self.logger.info(f"{'INGEST':15} SCAN:{subfolder} <spec found: {1 if len(function_spec_result) > 0 else 0}> DONE")
            cnt += 1

    async def aget_page_content(self, unique_id: str) -> str:
        """
        Fetch the HTML content of a page by ID using body.storage.

        Returns the HTML string.

        Since
        --------
        0.0.7
        """
        try:
            loop = asyncio.get_running_loop()
            ctx = ClientContext(self._base_url).with_credentials(self._credential)
            f: File = ctx.web.get_file_by_id(unique_id)
            local_file_path = os.path.join("data", "sharepoint", unique_id + ".docx")
            #print(local_file_path)
            def download_file_to_localpath():
                with open(local_file_path, "wb") as local_file:
                    f.download(local_file).execute_query()
                #print(f"Downloaded {local_file}")
                return local_file_path

            return await loop.run_in_executor(None, download_file_to_localpath)
        except Exception as e:
            self.logger.error(f"{'DOWNLOAD'} <unique_id: {unique_id}>", exc_info=e)

    async def _aexecute_query(self, ctx: ClientContext):
        """
        Run the office365 query asynchronously using asyncio `run_in_executor`

        Args:
           ctx (ClientContext): 

        TODO: Performance improvement as it is not native asyncio

        Since
        --------
        0.0.7 
        """
        loop = asyncio.get_running_loop()

        def execute_query_impl():
            ctx.execute_query()

        return await loop.run_in_executor(None, execute_query_impl)