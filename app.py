import os
import json
from flask import Flask, request, json, abort, session, app
import requests
from requests.auth import HTTPBasicAuth

import sentry_sdk
from sentry_sdk import capture_message, capture_exception
from sentry_sdk.integrations.flask import FlaskIntegration


app = Flask(__name__)
# app.secret_key = os.environ.get("FLASK_SECRET_KEY")
jira_api_token = os.environ.get("JIRA_API_TOKEN")
sentry_api_token = os.environ.get("SENTRY_API_TOKEN")
sentry_sdk.init(
    dsn=os.environ.get("DSN"),
    integrations=[FlaskIntegration()],
    environment="production",
)
@app.route("/")
def trigger_issue():
    try:
        a_problem_happened() # change this each time to make a new issue
    except Exception as e:
        capture_exception(e)
    return 'h-hello?', 200


@app.route('/webhook', methods=['POST'])
def webhook():
    data = json.loads(request.data)

    if data['action'] != 'created':
        return

    issue_id = data['data']['issue']['id']
    issue_details = get_sentry_issue(issue_id)
    link = issue_details["permalink"]
    title = issue_details["title"]
    short = issue_details["shortId"]
    details = issue_details["metadata"] # not exactly what I want though ... okay for a hackjob

    post_jira_issue(link, title, short, details)
    return 'OK'

def post_jira_issue(link, title, short, details):
    ### Post a Jira ticket when a Sentry issue is created
    # https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-post

    url = u'https://hellboi2020.atlassian.net/rest/api/3/issue/'
    auth = HTTPBasicAuth("colleen@sentry.io", jira_api_token)
    headers = {
       "Accept": "application/json",
       "Content-Type": "application/json"
    }
    payload = {
    "fields": {
       "project":
       {
          "key": "HEK"
       },
       "summary": title,
        "description": {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Sentry Issue: "
                        },
                        {
                            "type": "text",
                            "text": short,
                            "marks": [
                                {
                                    "type": "link",
                                    "attrs": {
                                        "href": link
                                    }
                                }
                            ]
                        }
                    ]
                },
                {
                    "type": "paragraph",
                    "content": []
                },
                {
                    "type": "codeBlock",
                    "attrs": {},
                    "content": [
                        {
                            "type": "text",
                            "text": details["value"]
                        }
                    ]
                }
            ]
        },
       "issuetype": {
          "name": "Bug"
       }
   }
}
    payload = json.dumps(payload)
    r = requests.post(url=url, headers=headers, data=payload, auth=auth)
    return r

def get_sentry_issue(issue_id):
    url = u'https://sentry.io/api/0/issues/{}/'.format(issue_id)
    headers = {'Authorization': u'Bearer {}'.format(sentry_api_token)}

    resp = requests.get(url, headers=headers)
    return resp.json()

if __name__== '__main__':
    app.run(debug=True)