"""Documented Greenhouse/Lever public posting read adapters. Permission to
republish data commercially must be checked by the operator per source."""
import httpx, html, re, hashlib
from urllib.parse import urlparse

def clean_html(raw):
    text=re.sub(r'<(script|style)[^>]*>.*?</\1>',' ',raw or '',flags=re.I|re.S)
    text=re.sub(r'<[^>]+>',' ',text)
    return re.sub(r'\s+',' ',html.unescape(text)).strip()[:30000]

def clean_https(url):
    value=str(url or '')
    parsed=urlparse(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Only public HTTPS job links are accepted')
    return value

async def fetch_jobs(kind,slug):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}',slug):
        raise ValueError('Invalid provider slug')
    if kind=='greenhouse':
        api=f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true'
        host='boards.greenhouse.io'
    elif kind=='lever':
        api=f'https://api.lever.co/v0/postings/{slug}?mode=json'
        host='jobs.lever.co'
    else: raise ValueError('Unsupported job provider')
    async with httpx.AsyncClient(timeout=18,follow_redirects=False,headers={'User-Agent':'CareerRadarPro/0.1 (job-feed-client)'}) as client:
        response=await client.get(api)
        response.raise_for_status()
        payload=response.json()
    rows=payload.get('jobs',[]) if kind=='greenhouse' else payload
    if not isinstance(rows,list): raise ValueError('Unexpected feed format')
    out=[]
    for item in rows[:2000]:
        try:
            if kind=='greenhouse':
                link=clean_https(item.get('absolute_url'))
                if urlparse(link).hostname not in ('boards.greenhouse.io','job-boards.greenhouse.io','boards.eu.greenhouse.io'):
                    continue
                title=item.get('title') or ''
                location=(item.get('location') or {}).get('name','')
                description=clean_html(item.get('content'))
                identifier=str(item['id'])
                date=item.get('updated_at')
            else:
                link=clean_https(item.get('hostedUrl'))
                if urlparse(link).hostname!='jobs.lever.co': continue
                title=item.get('text') or ''
                categories=item.get('categories') or {}
                location=categories.get('location') or ''
                description=clean_html(item.get('descriptionPlain') or item.get('description'))
                identifier=str(item['id'])
                date=None
            if not title.strip() or not identifier: continue
            source=f'{kind}:{slug}'
            job_id=hashlib.sha256(f'{source}:{identifier}'.encode()).hexdigest()[:32]
            out.append({'id':job_id,'source':source,'external_id':identifier,
                        'company':slug.replace('-',' ').title(), 'title':title[:250],
                        'location':location[:250],'country':'','work_type':'Not specified',
                        'description':description,'url':link,'posted_at':date})
        except (KeyError,ValueError,TypeError,AttributeError): continue
    return out
