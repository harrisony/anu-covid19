import datetime
import requests
from bs4 import BeautifulSoup, NavigableString
from flask import Flask, jsonify, redirect
import re
import os
import itertools
import copy

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=os.environ['SENTRY_DSN'],
    integrations=[FlaskIntegration()]
)

app = Flask(__name__)

ANU_COVID_NEWS = 'https://www.anu.edu.au/covid-19-advice/confirmed-covid19-cases-in-our-community'
ANU_COVID_LEVEL = 'https://www.anu.edu.au/covid-19-advice/campus-community/covid-safe-campus'

# I mean I thought the levels were the names not the colours but *shrugs*
ANU_COVID_LEVELS = {'NORMAL', 'LOW', 'MEDIUM', 'HIGH', 'EXTREME',
                    'GREEN', 'BLUE', 'AMBER', 'ORANGE', 'RED',
                    'BLUE PLUS MASKS'}
ANU_COVID_RISKS = {'GREEN': 'Normal', 'BLUE': 'Low', 'AMBER': 'Medium', 'ORANGE': 'High', 'RED': 'Extreme',
                   'BLUE PLUS MASKS': 'Low'}


def process_2020(case):
    app.logger.debug(f"PROCESSING: {case}")
    app.logger.debug(f"\twith parent {case.parent}")

    if case.parent is None:  # This occurs with the 'strong p'
        return

    p_strong = case.parent.find_all('strong')
    if len(p_strong) > 1:
        app.logger.info(f"Merging strongs: {p_strong}")
        p_strong.pop(0)
        for s in p_strong:
            case.string += s.get_text()  # string should work too
            s.extract()  # decompose causes issues

    app.logger.debug(f"Date: {case}")
    casedict = {'date': case.get_text(strip=True)}
    if case.get_text() == case.parent.get_text():
        app.logger.debug("normal details extraction")
        details = case.parent.find_next_sibling('p').get_text().strip()
        # details = c.find_next_sibling('p').get_text().strip()
    else:
        app.logger.info("strong embedded in p")
        case.clear()  # clear the strong with the date
        details = case.parent.get_text().strip()
        app.logger.debug(details)

    # This hurts...but so does COVID.
    # Updates casedict with the details of the case (who, what, when, where, why, etc)
    # They're in the form `Actions: Contract tracing and separated by new lines

    casedict = dict(casedict, **dict(
        [(i[0].strip().replace(' ', '_'), i[1].strip()) for i in (p.split(':') for p in details.split('\n'))]
    ))

    # As at 9 Apr, they seem to skip Actions and just have further details

    app.logger.info(casedict)
    return casedict

def process(cases):

    date_cases = []
    date = ''
    for case in cases.find_all('p'):
        if len(case.get_text(strip=True)) == 0:
            case.decompose()
            continue
        try:
            date = datetime.datetime.strptime(case.get_text(strip=True), "%d %B %Y")
            continue
        except ValueError:
            app.logger.debug(f"content: {case}")
            pass
        app.logger.debug(f"Date: {date}")
        casedict = {'date': date.strftime("%d %B %Y")}
        details = case.get_text().strip()
        # This hurts...but so does COVID.
        # Updates casedict with the details of the case (who, what, when, where, why, etc)
        # They're in the form `Actions: Contract tracing and separated by new lines

        casedict = dict(casedict, **dict(
            [(i[0].strip().replace(' ', '_'), i[1].strip()) for i in (p.split(':') for p in details.split('\n'))]
        ))
        date_cases.append(casedict)

    # As at 9 Apr, they seem to skip Actions and just have further details

    return date_cases


@app.route('/community-cases')
def handle_news():
    r = requests.get(ANU_COVID_NEWS)
    app.logger.info(f"Requested {ANU_COVID_NEWS} with {r}")

    page = BeautifulSoup(r.text, features="html.parser")
    content = page.select_one('[property="content:encoded"]')
    # app.logger.debug(f"BeautifulSoup: {content}")

    infobox = content.select_one('div.bg-uni25').extract()
    last_update_meta = page.select_one('meta[property="article:modified_time"]').get('content')
    last_update = infobox.select_one('h3').text

    ccount = content.select_one('div.bg-uni25').extract()

    case_count = re.search(r'(\d+)$', ccount.text.strip()).group(0)
    app.logger.info(f"number of cases: {ccount.get_text(strip=True)}. {case_count}")
    # cases_heading.parent.decompose()
    # ccount.decompose()

    cases_heading = content.select_one('strong')

    # TODO: why is this needed
    for elem in itertools.takewhile(
            lambda x: cases_heading.parent != x, content.children
    ):
        if isinstance(elem, NavigableString):
            elem.extract()
        else:
            elem.decompose()

    app.logger.debug(f"case: {cases_heading}")

    # Remove heading now
    content.select_one('strong', text='Details').parent.decompose()

    c_2021 = copy.copy(content)
    [e.decompose() for e in c_2021.find('h3', text='2020').previous_sibling.find_next_siblings()]
    c_2021.find('h3', text='2021').decompose()
    cases = process(c_2021)

    c_2020 = copy.copy(content)
    [e.decompose() for e in c_2020.find('h3', text='2020').find_previous_siblings()]
    c_2020.select_one('h3').decompose()
    cases.extend(
        filter(None.__ne__, (process_2020(xi) for xi in c_2020.select("strong")))
    )

    app.logger.warn(f"Expected casees: {int(case_count)}. Actual: {len(cases)}")

    response = {
        "last_updated_meta": last_update_meta,
        "last_updated_official": last_update,
        "count": int(case_count),
        "cases": cases,
    }
    return jsonify(response)


def alert_new(box):
    regex = '|'.join([x.lower() for x in ANU_COVID_LEVELS])
    text = box.select_one('p').get_text(strip=True).lower()
    r = re.search(regex, text)
    if r:
        return r.group(0).upper()
    raise Exception("COVIDSafe Campus Alert level error", text)


@app.route('/alert-level')
def process_alert():
    r = requests.get(ANU_COVID_LEVEL)
    app.logger.info(f"Requested {ANU_COVID_LEVEL} with {r}")

    content = BeautifulSoup(r.text, features="html.parser")

    last_update = content.select_one('meta[property="article:modified_time"]').get('content')
    box = content.select_one('[property="content:encoded"]').select_one('div')

    if box.select_one('h2').text != "Current alert level":
        app.logger.warn("page has changed again?", box)
    box.select_one('h2').decompose()

    level = alert_new(box)

    risk = ANU_COVID_RISKS.get(level)

    if level not in ANU_COVID_LEVELS:
        raise Exception("COVIDSafe Campus Alert level error", level)

    return jsonify(alert_level=level.title(), risk=risk, last_updated=last_update, details=box.text.strip())


@app.route('/latest-anuobserver-live')
def latest_anuobserver():
    CATEGORY = 'https://anuobserver.org/wp-json/wp/v2/posts?categories=306'
    r = requests.get(CATEGORY)
    for post in r.json():
        if 'covid' in post['slug']:
            return redirect(post['link'])
