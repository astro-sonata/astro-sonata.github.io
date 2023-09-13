"""
Python Script to scrape arxiv and output an html file with a table of the most recent
papers by SONATA members
"""
import os
import datetime
import re
import unicodedata
from dateutil import tz
import numpy as np
from arxiv import Search, SortCriterion, SortOrder
import jinja2

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    autoescape=jinja2.select_autoescape(['html', 'xml'])
)

NAME_RE = re.compile(r'^(?P<first>(?:(?P<initial>\w).*)[\. ]+)+(?P<last>\w.*)$')
ALL_INITIALS_RE = re.compile(r'\b\w\.')
INITIAL_RE = re.compile(r'^\w(\.|\s|$)')

def normalize_caseless(text):
    text = re.sub(r'[^\w]', ' ', text)
    # thanks to https://stackoverflow.com/a/29247821
    text = unicodedata.normalize("NFKD", text.casefold())
    text = text.strip()
    return text

def strip_initials(names):
    return ' '.join(ALL_INITIALS_RE.sub('', names).split())

def approximate_name_lookup(name, people):
    # normalize at input boundary so comparisons are simply ==
    normalized_name = normalize_caseless(name)
    name_match = NAME_RE.match(normalized_name)
    if not name_match:
        #log.warn(f"Unable to parse {normalized_name=} with regex")
        return None, 0
    parts = name_match.groupdict()
    first_names = parts['first'].strip()
    first_initial = parts['initial']
    last_name = parts['last'].strip()

    for person_last, person_first in people:
        score = 0
        if person_last == last_name:
            # last name matches, but what about first?
            if person_first == first_names:
                # easy: last name matches, first name(s) match
                score = 2
            elif first_names.startswith(person_first):
                score = 2
            elif first_names in person_first:
                # first_names is a substring of person_first
                # does person_first match after removing initials?
                if strip_initials(person_first).startswith(first_names):
                    score = 2
            elif person_first in first_names:
                # does first_names match after removing initials?
                if strip_initials(first_names).startswith(person_first):
                    score = 2
            elif person_first[0] == first_initial[0]:
                # harder: last name matches, first initial matches
                # check if it's an initial (single letter followed by space, period, or end of string
                re_match = INITIAL_RE.match(first_names)
                if re_match:
                    score = 1
                # otherwise, same first initial, different first name, so no match
            # else: same last name, different first name, no match
        if score:
            return (person_last, person_first), score
    return None, 0

def getSonataMembers():
    '''
    This will eventually scrape the sonata website but for now just use a list of
    people that I create by handx

    Returns:
        List of SONATA Members
    '''

    people = {}
    
    members = np.genfromtxt("sonata-members.txt", dtype=str, delimiter='\n')

    for member in members:

        split = member.split(' ')
        name = (split[-1], split[0]) # do it this way to ignore middle initial
        people[name] = {'position':'', 'role':'', 'image':''}
    
    return members, people # return a list of members as well as people with extra info

def scrapeArxiv(members, people):
    '''
    Scrapes arxiv for papers by any of the sonata members

    Args:
        members [list[str]]: list of sonata members

    Returns:
        pandas dataframe of results
    '''

    # first generate the query
    query = 'cat:astro-ph* AND ('
    for name in members:
        query += f'au:"{name}" OR '

    query = query[:-4]
    query += ')'
    print(query)
    # run the query
    s = Search(query=query,
               sort_by=SortCriterion.SubmittedDate)
    
    # parse the search results and put into a dataframe
    post = []
    nGood = 0
    for r in s.results():

        authors = [a.name for a in r.authors]
        
        good = any(member in authors[:3] for member in members)
        
        if not good: continue
                
        postInfo = {'authors': [(a, approximate_name_lookup(a, people)) for a in authors],
                    'title':r.title,
                    'abstract': r.summary,
                    'area': r.primary_category,
                    'arxiv_id': r.entry_id.rsplit('/',1)[1]}
        post.append(postInfo)

        nGood += 1

        if nGood >= 10:
            break

    return post

def renderHTML(context_dict):
    '''
    Add to the home page. Borrowed from Joseph Long
    https://github.com/joseph-long/arxiv-mailer/blob/c3182218f28bf2c316c3b7678505e166f9eb38ef/mailer.py#L263C1-L269C1

    context_dict [dict] : dictionary of content for the html
    '''

    html_template = env.get_template('mailing.jinja2.html')
    html_mailing = html_template.render(**context_dict)
    return html_mailing

def main():

    outdir = os.path.dirname(os.getcwd())
    outpath = os.path.join(outdir, 'html', 'arxiv-scrape-results.html')
    
    run_time = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    tzmst = tz.gettz('America/Phoenix')
    run_time_local = run_time.astimezone(tzmst)
    
    members, people = getSonataMembers()
    result = scrapeArxiv(members, people)

    context = {
        'people': people,
        'posts': result,
        'run_time': run_time_local
    }
    html  = renderHTML(context)

    with open(outpath, 'w') as f:
        f.write(html)
    
if __name__ == "__main__":
    main()
    
