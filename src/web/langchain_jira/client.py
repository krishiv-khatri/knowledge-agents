import copy
import json
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from common.api.http.client import ApiClient
from common.std import Result

class JiraApiClient(ApiClient):
    """

    Since
    --------
    0.0.6
    """

    def __init__(self, context_path: str, personal_access_token: str) -> None:
        """
        Args:
            context_path: The context base URL like `https://jira.example.com/`
            personal_access_token: The token for accessing the Jira API

        Since
        --------
        0.0.6
        """
        super().__init__(context_path)
        self._headers = {"Accept": "application/json", "Authorization": f"Bearer {personal_access_token}"}

    def get_issue_changelogs_by_component(self, component):
        """
        Function used to get all tickets that belong to a component with changelog histories.
        """
        query = {
            'jql': f'component = "{component}" ORDER BY status DESC',
            'maxResults': '100',
            'fields': 'id,key,summary,status,description,created,updated,components,originalEstimate,remainingEstimate,timespent,timetracking',
            'expand': 'changelog'
        }
        url = f"{self._base_url}/rest/api/2/search"
        response = requests.get(url, params=query, headers=self._headers, verify=False)
        # print(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        result = json.loads(response.text)
        return result
    
    def group_issues_by_date(self, issues):
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
        return dict(date_ticket_dict)