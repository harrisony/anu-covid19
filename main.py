import requests
from bs4 import BeautifulSoup, NavigableString
from flask import Flask
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

ANU_COVID_LEVELS = {'NORMAL', 'LOW', 'MEDIUM', 'HIGH', 'EXTREME'}

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
            case.string += s.get_text() # string should work too
            s.extract() #decompose causes issues

    app.logger.debug(f"Date: {case}")
    casedict = {'date': case.get_text(strip=True)}
    if case.get_text() == case.parent.get_text():
        app.logger.debug("normal details extraction")
        details = case.parent.find_next_sibling('p').get_text().strip()
        # details = c.find_next_sibling('p').get_text().strip()
    else:
        app.logger.info("strong embedded in p")
        case.clear() # clear the strong with the date
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

    content = BeautifulSoup(r.text, features="html.parser").select_one('[property="content:encoded"]')
    # app.logger.debug(f"BeautifulSoup: {content}")

    cases_heading = content.select_one('strong')

    for elem in itertools.takewhile(
        lambda x: cases_heading.parent != x, content.children
    ):
        if isinstance(elem, NavigableString):
            elem.extract()
        else:
            elem.decompose()

    app.logger.debug(f"case: {cases_heading}")

    ccount = cases_heading.parent.find_next_sibling('p')
    case_count = re.match(r'.*(\d+)$', ccount.string).group(1)
    app.logger.info(f"number of cases: {ccount}. {case_count}")
    cases_heading.parent.decompose()
    ccount.decompose()

    cases = content.select('strong')
    # app.logger.debug(f"Selecting rest of cases: {cases}")

    response = {
        "count": int(case_count),
        "cases": list(
            filter(None.__ne__, (process(xi) for xi in content.select("strong")))
        ),
    }
    return json.dumps(response)

@app.route('/alert-level')
def process_alert():
    r = requests.get(ANU_COVID_LEVEL)
    app.logger.info(f"Requested {ANU_COVID_LEVEL} with {r}")

    content = BeautifulSoup(r.text, features="html.parser").select_one('.anu-fotorama')
    app.logger.debug(f"BeautifulSoup: {content}")
    # 'COVIDSafe Campus Alert - LOW'

    level_text =  content.select_one('img').get('alt')
    level_graphic =  content.select_one('img').get('src')
    print(level_graphic)
    app.logger.info(f"fotorama: {level_text}")

    level = level_text.split()[-1]

    if level not in ANU_COVID_LEVELS:
        raise Exception("COVIDSafe Campus Alert level error")

    return {'alert_level': level.title(), 'alert_graphic': level_graphic}


