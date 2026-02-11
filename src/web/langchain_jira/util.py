import base64
from collections import defaultdict
import io
from typing import Dict, List
from fastapi import Depends
import requests
import json
from datetime import datetime, timedelta
import copy
from PIL import Image
import warnings
from urllib3.exceptions import InsecureRequestWarning

# Suppress only the InsecureRequestWarning
warnings.simplefilter('ignore', InsecureRequestWarning)

import os

# Jira connection settings - loaded from environment variables.
# Set JIRA_BASE_URL and JIRA_API_TOKEN in your .env or environment before running.
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "https://jira.example.com")
API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
LIMIT = 5

HEADERS = {"Accept": "application/json", "Authorization": f"Bearer {API_TOKEN}"}

# Default Jira project key - override via JIRA_PROJECT env var if needed.
PROJECT = os.getenv("JIRA_PROJECT", "MYPROJECT")

def get_all_issue_fields():
    warnings.warn('#get_all_issue_fields has been deprecated', DeprecationWarning, stacklevel=2)
    query = {
        'jql': f'project = {PROJECT}',
        'maxResults': f'{LIMIT}',
        'fields': 'id,key,summary,description,components,comment,issuetype,priority,labels,status,attachment',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    # print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))

def get_issue_payload(issue_key):
    query = {
        'jql': f'key = {issue_key}',
        'maxResults': '1',
        'fields': 'id,key,summary,description,components,comment,issuetype,priority,labels,status,attachment',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    # print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))
    result = json.loads(response.text)
    return result

def get_issue(issue_key):
    query = {
        'jql': f'key = {issue_key}',
        'maxResults': '1',
        'fields': 'id,key,summary,description,components,comment,issuetype,priority,labels,status,attachment',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))
    result = json.loads(response.text)
    return {"id": result["issues"][0]["id"],
            "title": result["issues"][0]["fields"]["summary"],
            "description": result["issues"][0]["fields"]["description"],
            "components": result["issues"][0]["fields"]["components"],
            "labels": result["issues"][0]["fields"]["labels"],
            "priority": result["issues"][0]["fields"]["priority"]["name"],
            "comments": get_comments(issue_key),
            "status": result["issues"][0]["fields"]["status"]["name"]
        }

def get_issues_by_component(component):
    query = {
        'jql': f'component = "{component}" AND status IN ("Development To-Do", "Development In-Progress", "Work in Progress") ORDER BY status DESC',
        'maxResults': '50',
        'fields': 'id,key,summary,status,created,description,updated,components,originalEstimate,remainingEstimate,timespent,timetracking',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    # print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))
    result = json.loads(response.text)
    issues = []
    for issue in result["issues"]:
        issues.append({
            "key": issue["key"],
            "title": issue["fields"]["summary"],
            "description": issue["fields"]["description"],
            "components": issue["fields"]["components"],
            "labels": issue["fields"]["labels"],
            "priority": issue["fields"]["priority"]["name"],
            "comments": get_comments(issue["key"]),
            "status": issue["fields"]["status"]["name"]
        })
    return issues

def get_current_issues():
    query = {
        'jql': f'status IN ("Development To-Do", "Development In-Progress", "Work in Progress") AND issuetype NOT IN ("Epic") ORDER BY status DESC',
        'maxResults': '1',
        'fields': 'id,key,summary,description,components,comments,issuetype,priority,labels,status',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    # print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))
    result = json.loads(response.text)
    issues = []
    for issue in result["issues"]:
        issues.append({
            "key": issue["key"],
            "title": issue["fields"]["summary"],
            "description": issue["fields"]["description"],
            "components": issue["fields"]["components"],
            "priority": issue["fields"]["priority"]["name"],
            "labels": issue["fields"]["labels"],
            "comments": get_comments(issue["key"], True),
            "status": issue["fields"]["status"]["name"]
        })
    #print(issues)
    return issues

def get_user(username):
    query = {
    'username': username
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/user"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    try:
        print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))
        result = json.loads(response.text)
    except Exception as e:
        print(response)
        print(e)

def get_issue_changelogs_by_component(component):
    """
    Function used to get all tickets that belong to a component with changelog histories.
    """
    query = {
        'jql': f'component = "{component}" ORDER BY status DESC',
        'maxResults': '100',
        'fields': 'id,key,summary,status,description,created,updated,components,originalEstimate,remainingEstimate,timespent,timetracking',
        'expand': 'changelog'
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
    result = json.loads(response.text)
    # Optionally persist changelogs to a local file for debugging
    # with open("changelogs_output.json", "w", encoding="utf-8") as f:
    #     json.dump(result, f, sort_keys=True, indent=4, separators=(",", ": "))
    return result

def update_issue(issue_key, payload):
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}"
    response = requests.put(url, json=payload, headers=HEADERS, verify=False)

    if response.status_code == 204:
        print("Issue updated successfully.")
    else:
        print(f"Failed to update issue: {response.status_code}")
        print(response.text)
    print(response.text)

def create_issue(payload):
    url = f"{JIRA_BASE_URL}/rest/api/2/issue"
    response = requests.post(url, json=payload, headers=HEADERS, verify=False)

    if response.status_code in [200, 201, 204]:
        print("Issue created successfully.")
        print("Response:", response.json())
        return response.json()
    else:
        print(f"Failed to create issue: {response.status_code}")
        print(response.text)

def check_available_fields():
    url = f"{JIRA_BASE_URL}/rest/api/2/field"
    response = requests.get(url, headers=HEADERS, verify=False)
    data = response.json()

    # Write to a new file
    with open("jira_fields.json", "w", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, indent=4, separators=(",", ": "))

    print("JSON data has been written to jira_fields.json")

def get_comments(issue_key, reverse: bool = False):
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment"
    response = requests.get(url, headers=HEADERS, verify=False)
    # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

    comments = json.loads(response.text)["comments"]
    # Sort comments by created timestamp
    comments.sort(key=lambda x: datetime.fromisoformat(
        x["created"].replace("+0000", "+00:00")
    ), reverse=True)
    output = []

    for comment in comments:
        author = comment["author"]["displayName"]
        created = comment["created"].replace("+0000", "+00:00")
        
        # Parse and format timestamp
        dt = datetime.fromisoformat(created)
        formatted_date = dt.strftime("%B %d, %Y at %I:%M %p") + " UTC"
        
        # Clean up body text
        body = comment["body"].replace("\r\n", "\n").strip()
        
        # Create formatted comment
        formatted_comment = f"[{author} ({formatted_date})]:\n{body}"
        output.append(formatted_comment)

        print(comment)

    return "\n\n---\n\n".join(output)

def group_issues_by_date(issues):
    """
    Build a dictionary mapping date strings (YYYY-MM-DD) to lists of ticket states as of that date.

    Args:
        jira_issues (dict): JSON response from Jira API with 'issues' and expanded 'changelog'.

    Returns:
        dict: {date_str: [ticket_state_dict, ...], ...}
    """
    date_ticket_dict = defaultdict(list)

    for issue in issues.get('issues', []):
        fields = issue.get('fields', {})
        changelog = issue.get('changelog', {}).get('histories', [])

        # Track fields that have changes and their initial values from 'fromString'
        initial_values = {}

        for history in changelog:
            for item in history.get('items', []):
                field = item.get('field')
                if field not in initial_values and 'fromString' in item:
                    initial_values[field] = item['fromString']

        # Build the initial state using initial_values or fallback to final field values
        state = {
            'id': issue.get('id'),
            'key': issue.get('key'),
            'summary': initial_values.get('summary', fields.get('summary')),
            'status': "Open",
            'description': initial_values.get('description', fields.get('description')),
            'comments': "",
            'created': fields.get('created'),
            'updated': fields.get('updated'),
            'components': [initial_values.get('Component')] if initial_values.get('Component') is not None else [c.get('name') for c in fields.get('components', [])],
            'epic_link': initial_values.get('Epic Link', fields.get('customfield_10008')),
        }

        # Build change_points: list of (date, state) tuples
        change_points = []
        created_date = datetime.strptime(fields['created'][:10], "%Y-%m-%d")

        # if state.get('status') != 'Open': #TODO: Remove when no status filtering needed
        change_points.append((created_date, copy.deepcopy(state)))

        for history in sorted(changelog, key=lambda h: h['created']):
            change_date = datetime.strptime(history['created'][:10], "%Y-%m-%d")
            state['updated'] = history['created']
            for item in history.get('items', []):
                field = item.get('field')
                if field == 'status':
                    state['status'] = item.get('toString')
                elif field == 'summary':
                    state['summary'] = item.get('toString')
                elif field == 'description':
                    state['description'] = item.get('toString')
                elif field == 'Component':
                    state['components'] = [item.get('toString')] if item.get('toString') else []
                elif field == 'Epic Link':
                    state['epic_link'] = item.get('toString')
                elif field == 'Comment':
                    state['comments'] += f"[{history.get('author').get('displayName')} ({history.get('created')})]:\n{item.get('from')}"
            
            # Add condition to truncate description if status is 'Open' and description is too long
            if state.get('status') == 'Open' and state.get('description') and len(state['description']) > 500:
                state['description'] = state['description'][:500] + "\ncontinued..."
            
            if state.get('status') != 'Open': #TODO: Remove when no status filtering needed
                change_points.append((change_date, copy.deepcopy(state)))

        # Fill every day from created to last change
        min_date = change_points[0][0]
        max_date = change_points[-1][0]
        date = min_date
        idx = 0
        while date <= max_date:
            while idx + 1 < len(change_points) and change_points[idx + 1][0] <= date:
                idx += 1
            date_ticket_dict[date.strftime("%Y-%m-%d")].append(copy.deepcopy(change_points[idx][1]))
            date += timedelta(days=1)
    # print(json.dumps(date_ticket_dict, sort_keys=True, indent=4, separators=(",", ": ")))
    # Optionally persist progress data to a local file for debugging
    # with open("progress_output.json", "w", encoding="utf-8") as f:
    #     json.dump(date_ticket_dict, f, sort_keys=True, indent=4, separators=(",", ": "))
    return dict(date_ticket_dict)

def get_image(url):
    response = requests.get(url, headers=HEADERS, verify=False)
    image = Image.open(io.BytesIO(response.content)).convert('RGB')
    # Resize image to fit within MAX_SIZE while maintaining aspect ratio
    MAX_SIZE = (512, 512)
    image.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    base64_str = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/png;base64,{base64_str}"

def get_current_issues_v2(start_at: int = 0):
    query = {
        'jql': f'status IN ("Open", "Development To-Do", "Development In-Progress", "Work in Progress") AND issuetype NOT IN ("Epic") ORDER BY updated DESC',
        'startAt': start_at,
        'maxResults': '50',
        'fields': 'id,key,summary,description,components,comments,issuetype,priority,labels,status,updated',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    print(f"{url}, params: {query}")
    # print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))
    result = json.loads(response.text)
    issues = []
    for issue in result["issues"]:
        dt_updated = format_jira_timestamp_to_dt(issue['fields']['updated'])
        issues.append({
            "key": issue["key"],
            "title": issue["fields"]["summary"],
            "description": issue["fields"]["description"],
            "comments": get_comments_v2(issue["key"], True),
            "updated": dt_updated.isoformat(),
            "updated_epoch": dt_updated.timestamp()
        })
    return issues


def get_issue_v2(issue_key) -> Dict:
    query = {
        'jql': f'key = {issue_key}',
        'maxResults': '1',
        'fields': 'id,key,summary,description,components,comments,issuetype,priority,labels,status,updated',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)    
    #print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))
    result = json.loads(response.text)
    if len(result["issues"]) <= 0:
        return None
    else:        
        issues = result["issues"][0]
        dt_updated = format_jira_timestamp_to_dt(issues['fields']['updated'])
        return {
            "key": issue_key,
            "title": issues["fields"]["summary"],
            "description": issues["fields"]["description"],
            #"components": issues["fields"]["components"],
            #"labels": issues["fields"]["labels"],
            "priority": issues["fields"]["priority"]["name"],
            "comments": get_comments_v2(issue_key),
            "status": issues["fields"]["status"]["name"],
            "updated": dt_updated.isoformat(),
            "updated_epoch": int(dt_updated.timestamp())
        }

def get_comments_v2(issue_key, reverse: bool = False) -> List[Dict]:
    url = f"{JIRA_BASE_URL}/rest/api/2/issue/{issue_key}/comment"
    response = requests.get(url, headers=HEADERS, verify=False)
    # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
    comments = json.loads(response.text)["comments"]
    #print(comments)
    # Sort comments by created timestamp
    comments.sort(key=lambda x: datetime.fromisoformat(
        x["created"].replace("+0000", "+00:00")
    ), reverse=False)

    trimmed_comments = []
    for comment in comments:
        id = comment['id']
        author = comment["author"]["displayName"]
        # Parse the timestamp
        # Use %z for UTC offset, but we need to handle the +0000 format
        dt_created = datetime.strptime(comment["created"], "%Y-%m-%dT%H:%M:%S.%f%z")
        # Convert to ISO 8601 format
        iso_format = dt_created.isoformat()
        # Parse and format timestamp
        #dt = datetime.fromisoformat(created)
        #formatted_date = dt.strftime("%B %d, %Y at %I:%M %p") + " UTC"
        # Clean up body text
        body = comment["body"].replace("\r\n", "\n").strip()
        # Create formatted comment
        #formatted_comment = f"[{author} ({formatted_date})]:\n{body}"
        #output.append(formatted_comment)

        trimmed_comments.append({
            "comment_id": id,
            "author": author,
            "timestamp": iso_format,
            "comment": body
        })

    #return "\n\n---\n\n".join(output)
    return trimmed_comments

def get_all_issues(start_at: int = 0):
    query = {
        'jql': f'project = "{PROJECT}" AND issuetype NOT IN ("Epic") ORDER BY updated DESC',
        'startAt': start_at,
        'maxResults': '100',
        'fields': 'id,key,summary,description,components,comment,attachment,issuetype,priority,labels,status,updated,created',
    }
    url = f"{JIRA_BASE_URL}/rest/api/2/search"
    response = requests.get(url, params=query, headers=HEADERS, verify=False)
    print(f"{url}, params: {query}")
    print(print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": "))))
    result = json.loads(response.text)
    issues = []
    for issue in result["issues"]:
        dt_created = format_jira_timestamp_to_dt(issue['fields']['created'])
        dt_updated = format_jira_timestamp_to_dt(issue['fields']['updated'])
        issues.append({
            "id": int(issue["id"]),
            "key": issue["key"],
            "title": issue["fields"]["summary"],
            "description": issue["fields"]["description"],
            "comments": get_comments_v2(issue["key"], True),
            "created": dt_created.isoformat(),
            "created_timestamp": dt_created.date(),
            "updated": dt_updated.isoformat(),
            "updated_timestamp": dt_updated.date(),
            "attachments": issue["fields"]["attachment"]
        })
    return issues

def format_jira_timestamp_to_dt(timestamp: str) -> datetime:
    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z")
    return dt