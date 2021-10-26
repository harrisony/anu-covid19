import datetime
import requests
from bs4 import BeautifulSoup, NavigableString
from flask import Flask, jsonify, redirect
import re
import os
import itertools
import copy

import sentry_sdk
from json2xml import json2xml
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=os.environ['SENTRY_DSN'],
    integrations=[FlaskIntegration()]
)

app = Flask(__name__)

ANU_COVIDSAFE_LEVEL = 'https://www.anu.edu.au/covid-19-advice/how-were-responding-to-covid-19/campus-alert-system'
ANU_RESIDENCE_LEVEL = 'https://www.anu.edu.au/covid-19-advice/how-were-responding-to-covid-19/information-for-students/residential-students-on'

ANU_COVIDSAFE_LEVELS = {'NORMAL', 'LOW', 'MEDIUM', 'HIGH', 'EXTREME'}



def alert_new(box):
    regex = '|'.join([x.lower() for x in ANU_COVIDSAFE_LEVELS])
    text = box.select_one('p').get_text(strip=True).lower()
    r = re.search(regex, text)
    if r:
        return r.group(0).upper()
    raise Exception("COVIDSafe Campus Alert level error", text)


@app.route('/alert-level')
def process_alert():
    r = requests.get(ANU_COVIDSAFE_LEVEL)
    app.logger.info(f"Requested {ANU_COVIDSAFE_LEVEL} with {r}")

    content = BeautifulSoup(r.text, features="html.parser")

    last_update = content.select_one('meta[property="article:modified_time"]').get('content')
    box = content.select_one('[property="content:encoded"]').select_one('div')

    if box.select_one('h2').text != "Current alert level":
        app.logger.warn("page has changed again?", box)
    box.select_one('h2').decompose()

    level = alert_new(box)

    if level not in ANU_COVIDSAFE_LEVELS:
        raise Exception("COVIDSafe Campus Alert level error", level)

    return jsonify(alert_level=level.title(), last_updated=last_update, details=box.text.strip())

@app.route('/latest-anuobserver-live')
def latest_anuobserver():
    CATEGORY = 'https://anuobserver.org/wp-json/wp/v2/posts?categories=306'
    r = requests.get(CATEGORY)
    for post in r.json():
        if 'covid' in post['slug']:
            return redirect(post['link'])




@app.route('/chs-community-checkin-news')
def checkin_news():
    r = requests.get('https://chs-community-checkin-api.azurefd.net/api/v1/content', headers={'x-api-key': 'bm5VTzh0SkZ6b1ZGVzVEb3hSSmNpbEN0Tjdvd0l6ZDE='})
    d = r.json()
    return json2xml.Json2xml(d).to_xml()