import os
import json
import requests
from requests.auth import HTTPBasicAuth
from flask import Flask, app, json, jsonify, request

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

app = Flask(__name__)
jira_api_token = os.environ.get("JIRA_API_TOKEN")
sentry_api_token = os.environ.get("SENTRY_API_TOKEN")
sentry_org_slug = os.environ.get("SENTRY_SLUG")
sentry_app_id = os.environ.get("SENTRY_APP_INSTALL_ID")
sentry_sdk.init(
    dsn=os.environ.get("DSN"),
    integrations=[FlaskIntegration()],
    environment="production",
)
@app.route("/")
def trigger_issue():
    try:
        okaydontbreakkkkk() # change this each time to make a new issue
    except Exception as e:
        sentry_sdk.capture_exception(e)
    return 'h-hello?', 200

@app.route('/linking', methods=['POST'])
def linking():
    data = json.loads(request.data)
    response_text = json.loads(data["fields"]["title"])
    response = {
        "webUrl": "https://hellboi2020.atlassian.net/browse/{}".format(response_text["key"]),
        "project": "HEK",
        "identifier": response_text["key"][4:]
    }
    return jsonify(response)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = json.loads(request.data)

    if data['action'] != 'created':
        return

    issue_id = data['data']['issue']['id']
    create_link(issue_id) # pretend to submit the UI element thing
    return 'OK'

def post_jira_issue(link, title, short, body, platform):
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
                    "attrs": {
                        "language": platform
                    },
                    "content": [
                        {
                            "type": "text",
                            "text": body
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
    return r.text

def get_sentry_issue(issue_id):
    url = u'https://sentry.io/api/0/issues/{}/'.format(issue_id)
    headers = {'Authorization': u'Bearer {}'.format(sentry_api_token)}

    resp = requests.get(url, headers=headers)
    return resp.json()

def get_issue_event(issue_id):
    url = u'https://sentry.io/api/0/issues/{}/events/'.format(issue_id)
    headers = {'Authorization': u'Bearer {}'.format(sentry_api_token)}

    resp = requests.get(url, headers=headers)
    return resp.json()

def get_event_info(event_id):
    url = u'https://sentry.io/api/0/organizations/{}/eventids/{}/'.format(sentry_org_slug, event_id)
    headers = {'Authorization': u'Bearer {}'.format(sentry_api_token)}

    resp = requests.get(url, headers=headers)
    return resp.json()

def create_link(issue_id):
    issue_details = get_sentry_issue(issue_id)
    link = issue_details["permalink"]
    title = issue_details["title"]
    short = issue_details["shortId"]

    event_id = get_issue_event(issue_id)[0]['eventID']
    event_info = get_event_info(event_id)

    platform = event_info["event"]["platform"]
    exception = event_info["event"]["entries"][0]["data"]["values"][0]["value"]
    filenames = []
    line_numbers = []
    functions = []
    for frame in event_info["event"]["entries"][0]["data"]["values"][0]["stacktrace"]["frames"]:
        filenames.append(frame["filename"])
        line_numbers.append(frame["lineNo"])
        functions.append(frame["function"])

    body = exception + "\n\n"
    for a, b, c in zip(filenames, line_numbers, functions):
        body += "File \"{}\", line {}, in {} \n".format(a, b, c)
        target_line = [i[1] for i in event_info["event"]["entries"][0]["data"]["values"][0]["stacktrace"]["frames"][0]["context"] if i[0] == b]
        body += target_line[0] + "\n"

    response_text = post_jira_issue(link, title, short, body, platform)
    print("response text: ", response_text)


    url = u'https://sentry.io/api/0/sentry-app-installations/{}/external-issues/'.format(sentry_app_id)
    # TODO: I dont think non-Sentry people would know their app install id
    headers = {'Authorization': u'Bearer {}'.format(sentry_api_token)}
    payload = {
        "action": "create", 
        "groupId": issue_id, 
        "uri": "/linking",
        "title": response_text
    }
    r = requests.post(url=url, headers=headers, data=payload)

    return r

if __name__== '__main__':
    app.run(debug=True)