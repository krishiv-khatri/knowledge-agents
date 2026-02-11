
## Steps to Retrieve a SharePoint Document

### Step 1: Register an App in Azure Active Directory

If using app-based authentication (recommended for automation), follow these steps:

1. Log in to the [Azure Portal](https://portal.azure.com).
2. Navigate to **Microsoft Entra ID > App Registrations > New registration**.
3. Provide a name (e.g., "Knowledge Agents Integration"), select "Accounts in this organizational directory only," and register.
4. Note the **Application (client) ID** from the app's overview page.
5. Go to **Certificates & Secrets**, create a new client secret, and copy the secret value.
6. Add permissions:
   1. Go to **API permissions > Add a permission > Microsoft Graph > Application permissions**.
   2. Add `Files.Read.All` and `Sites.Read.All` (or other required permissions).
   3. Click **Grant admin consent** for your organization.
   4. Alternatively, for user-based authentication, you only need a username and password with appropriate SharePoint permissions.

### Step 2: Configure the Application

Add your SharePoint credentials to `conf/config.yml`:

```yaml
sharepoint:
  url: https://yourcompany.sharepoint.com/sites/YourSite
  client_id: <your_azure_client_id>
  client_secret: <your_azure_client_secret>
  email: your_email@example.com
  credential_method: user  # or "client" for app-based auth
```

Or set environment variables (for standalone scripts):

```bash
export SHAREPOINT_SITE_URL=https://yourcompany.sharepoint.com/sites/YourSite
export SHAREPOINT_CLIENT_ID=your-client-id
export SHAREPOINT_CLIENT_SECRET=your-client-secret
```

### Step 3: Configure Document Ingestion

In `conf/config.yml`, specify the SharePoint folders and file patterns to ingest:

```yaml
sharepoint:
  ingest:
    - relative_url: /sites/YourSite/Shared Documents/Path/To/Your/Docs
      recursive: true
      include_regex:
        - (.*)\.docx$
      exclude_regex:
        - (.*)Archive(.*)
      vectorstore_collection_name: sharepoint_docs
```

### Step 4: Test Connectivity

Run the SharePoint OAuth test script:

```bash
python src/web/langchain_sharepoint/test.py
```

### Step 5: Trigger Ingestion

Once the application is running, SharePoint documents will be ingested according to the scheduler configuration, or you can trigger manual ingestion via the API.
