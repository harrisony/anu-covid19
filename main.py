import requests
from bs4 import BeautifulSoup
from flask import Flask
import re
import json
app = Flask(__name__)

ANU_COVID = 'https://www.anu.edu.au/news/all-news/confirmed-covid19-cases-in-our-community'


def process(c):
    print(c.string)
    casedict = {'date': c.string}
    if c.get_text() == c.parent.get_text():
        details = c.parent.find_next_sibling('p').get_text().strip()
    else: 
        c.clear() # clear the strong with the date
        details = c.parent.get_text().strip()
    print(casedict)
    casedict = dict(casedict, **dict([(i[0].strip(), i[1].strip()) for i in (p.split(':') for p in details.split('\n'))]))
    print(casedict)
    return casedict

@app.route('/')
def anu_covid():
    r = requests.get('https://www.anu.edu.au/news/all-news/confirmed-covid19-cases-in-our-community')
    content = BeautifulSoup(r.text, features="html.parser").select_one('div.col-main')

    case_num = content.select_one('strong')
    ccount = case_num.parent.find_next_sibling('p')
    ccount = re.match(r'.*(\d+)$', ccount.string).group(1)

    case_num.decompose()

    cases = content.select('strong')
    # assert len(cases) == ccount

    response= {'count': int(ccount), 'cases': list([process(xi) for xi in content.select('strong')])}
    return json.dumps(response)


