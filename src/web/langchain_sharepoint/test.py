"""
SharePoint OAuth connectivity test.

Usage:
    Set environment variables before running:
        SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/YourSite
        SHAREPOINT_CLIENT_ID=your-client-id
        SHAREPOINT_CLIENT_SECRET=your-client-secret

    Then run:
        python src/web/langchain_sharepoint/test.py
"""

import os
from dotenv import load_dotenv
from office365.runtime.auth.client_credential import ClientCredential
from office365.runtime.auth.user_credential import UserCredential
from office365.sharepoint.client_context import ClientContext

load_dotenv()


def test_sharepoint_oauth(site_url, client_id, client_secret):
    """Test SharePoint OAuth authentication with client credentials."""
    try:
        ctx = ClientContext(site_url).with_credentials(ClientCredential(client_id, client_secret))

        web = ctx.web
        ctx.load(web)
        ctx.execute_query()

        print(f"Authentication successful! Site title: {web.properties['Title']}")
        return True

    except Exception as e:
        print(f"Authentication failed: {str(e)}")
        return False


if __name__ == "__main__":
    site_url = os.getenv("SHAREPOINT_SITE_URL", "https://yourcompany.sharepoint.com/sites/YourSite")
    client_id = os.getenv("SHAREPOINT_CLIENT_ID", "")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("ERROR: Set SHAREPOINT_CLIENT_ID and SHAREPOINT_CLIENT_SECRET environment variables.")
        exit(1)

    result = test_sharepoint_oauth(site_url, client_id, client_secret)
    if result:
        print("Connection to SharePoint established successfully.")
    else:
        print("Failed to connect to SharePoint.")
