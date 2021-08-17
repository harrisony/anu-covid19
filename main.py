import requests
from bs4 import BeautifulSoup, NavigableString
from flask import Flask, jsonify, redirect
import re
import os
import json
import itertools

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


def process(case):
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
        [(i[0].strip(), i[1].strip()) for i in (p.split(':') for p in details.split('\n'))]
    ))

    # As at 9 Apr, they seem to skip Actions and just have further details

    app.logger.info(casedict)
    return casedict


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

    case_count = re.match(r'.*(\d+)$', ccount.text.strip()).group(1)
    app.logger.info(f"number of cases: {ccount}. {case_count}")
    # cases_heading.parent.decompose()
    # ccount.decompose()


    # Strip the junk
    # [<h3><strong>Details</strong></h3>,
    # <h3>2021</h3>,
    # <h3 class="nounderline"><strong>2020</strong></h3>]

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


    # Remove Year Headings
    for e in content.find_all('h3'):
        if e.text.isnumeric():
            e.decompose()

    # Remove 2021 nil
    [x.decompose() for x in content.find_all('p', text='Nil.')]

    #Remove heading now
    content.select_one('strong', text='Details').decompose()

    cases = list(
            filter(None.__ne__, (process(xi) for xi in content.select("strong")))
        )

    app.logger.warn(f"Expected casees: {int(case_count)}. Actual: {len(cases)}")

    response = {
        "last_updated": last_update_meta,
        "count": int(case_count),
        "cases": cases,
    }
    return jsonify(response)


@app.route('/alert-level')
def process_alert():
    r = requests.get(ANU_COVID_LEVEL)
    app.logger.info(f"Requested {ANU_COVID_LEVEL} with {r}")

    content = BeautifulSoup(r.text, features="html.parser")
    app.logger.debug(f"BeautifulSoup: {content}")

    box = content.select_one('[property="content:encoded"]').select_one('div')

    if box.select_one('h2').text != "Current alert level":
        app.logger.warn("page has changed again?", box)

    level_text = box.select_one('p strong')
    last_update = content.select_one('meta[property="article:modified_time"]').get('content')

    level = level_text.text
    level = level.upper().split("-")[0].strip()
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
