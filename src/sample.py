"""
Sample script demonstrating how to query Jira for current issues.

This is a standalone utility that can be used to test your Jira API connectivity
and verify your credentials before running the full multi-agent system.

Usage:
    1. Set JIRA_BASE_URL and JIRA_API_TOKEN environment variables (or in .env).
    2. Run: python src/sample.py
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "https://jira.example.com")
API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
LIMIT = 5
HEADERS = {"Accept": "application/json", "Authorization": f"Bearer {API_TOKEN}"}


def get_current_issues():
    """Fetch current Jira issues for the configured project version."""
    query = {
        'jql': 'ORDER BY priority DESC, key DESC, assignee ASC',
        'maxResults': '100',
        'fields': 'id,key,summary,description,components,comments,issuetype,priority,labels,status,updated',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    result = json.loads(response.text)
    issues = []
    for issue in result["issues"]:
        issues.append({
            "key": issue["key"],
            "title": issue["fields"]["summary"],
            "components": issue["fields"]["components"],
            "priority": issue["fields"]["priority"]["name"],
            "labels": issue["fields"]["labels"],
            "status": issue["fields"]["status"]["name"],
            "updated": issue["fields"]["updated"]
        })
    return issues


if __name__ == "__main__":
    issues = get_current_issues()
    with open("data.json", "w") as f:
        f.write(json.dumps(issues, indent=4))
    print(f"Fetched {len(issues)} issues. Output written to data.json.")
