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

ANU_COVID_NEWS = 'https://www.anu.edu.au/covid-19-advice/confirmed-covid19-cases-in-our-community'
ANU_COVIDSAFE_LEVEL = 'https://www.anu.edu.au/covid-19-advice/how-we%E2%80%99re-responding-to-covid-19/university-covid-19-guidelines/campus-alert-system'
ANU_RESIDENCE_LEVEL = 'https://www.anu.edu.au/covid-19-advice/how-were-responding-to-covid-19/information-for-students/residential-students-on'

ANU_COVIDSAFE_LEVELS = {'NORMAL', 'LOW', 'MEDIUM', 'HIGH', 'EXTREME'}


@app.route('/community-cases')
def handle_news():
    r = requests.get(ANU_COVID_NEWS)
    app.logger.info(f"Requested {ANU_COVID_NEWS} with {r}")

    page = BeautifulSoup(r.text, features="html.parser")
    content = page.select_one('[property="content:encoded"]')
    # app.logger.debug(f"BeautifulSoup: {content}")

    infobox = content.select_one('div.bg-uni25').extract()
    last_update_meta = page.select_one('meta[property="article:modified_time"]').get('content')
    last_update = infobox.select_one('h4').text

    ccount = content.select('div.box-solid strong')

    #Total number of reported ANU cases in the ACT: 3
    #Total number of reported ANU cases outside of the ACT: 5
    act = re.search(r'(\d+)', ccount[0].text.strip()).group(0)
    outside = re.search(r'(\d+)', ccount[1].text.strip()).group(0)

    response = {
        "last_updated_meta": last_update_meta,
        "last_updated_official": last_update,
        "count": int(act),
        "outside": int(outside)
    }
    return jsonify(response)


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


@app.route('/residence-level')
def process_residence():
    r = requests.get(ANU_RESIDENCE_LEVEL)

    content = BeautifulSoup(r.text, features="html.parser")

    last_update = content.select_one('meta[property="article:modified_time"]').get('content')
    box = content.select_one('[property="content:encoded"]').select_one('.msg-info')
    box.select_one('h2').decompose()

    link_box = box.find_all('p')[-1]
    if link_box.text == 'This page provides an overview of current restrictions, and you can access the updated\xa0protocols here.\xa0':
        link_box.decompose()

    level = box.select_one('strong')
    # 'level 1 restrictions' (stay at home orders)
    lre = re.search(r"'(.*?)' \((.*?)\)", level.get_text(strip=True)).groups()
    level = lre[0].title().replace('Restrictions', '').strip()
    detail = lre[1].title()

    return jsonify(alert_level=level, detail=detail,  last_updated=last_update, details=box.text.strip())


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