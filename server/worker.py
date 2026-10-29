"""Server-side alert evaluation and scheduled provider synchronization.
Run separately: python -m server.worker; use process manager/cron in production.
"""
import asyncio, logging, os
from datetime import datetime, timezone
from .db import connect,init_db
from .main import run_sync
from .security import now,make_id

logging.basicConfig(level=logging.INFO)
log=logging.getLogger('worker')

def process_followups():
    """One in-app reminder per application/due date; no fake external email or push delivery."""
    count=0
    today=datetime.now(timezone.utc).date().isoformat()
    with connect() as c:
        due=c.execute("""SELECT id,user_id,title,company,follow_up_at FROM applications
          WHERE follow_up_at IS NOT NULL AND substr(follow_up_at,1,10)<=?
          AND status NOT IN ('offer','withdrawn','rejected')""",(today,)).fetchall()
        for a in due:
            due_date=a['follow_up_at'][:10]
            inserted=c.execute('INSERT OR IGNORE INTO followup_reminders VALUES(?,?,?)',(a['id'],due_date,now()))
            if inserted.rowcount:
                c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(
                    make_id(),a['user_id'],None,'Application follow-up due: '+a['title'][:90],
                    a['company']+' · Due '+due_date,now(),None))
                count+=1
    return count

def process_alerts():
    count=0
    with connect() as c:
        alerts=c.execute("SELECT * FROM alerts WHERE enabled=1 AND frequency!='off'").fetchall()
        for a in alerts:
            query=a['query'].strip().lower();location=a['location'].strip().lower()
            candidates=c.execute("SELECT id,title,company,location,description FROM jobs WHERE status='active' ORDER BY first_seen_at DESC LIMIT 1000").fetchall()
            for j in candidates:
                haystack=(j['title']+' '+j['company']+' '+j['description']).lower()
                if query and query not in haystack:continue
                if location and location not in j['location'].lower():continue
                try:
                    c.execute('INSERT INTO alert_deliveries VALUES(?,?,?)',(a['id'],j['id'],now()))
                except Exception:continue # unique constraint prevents repeat, other errors will rollback on connection close only if unhandled
                c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',
                          (make_id(),a['user_id'],j['id'],'Job match: '+j['title'][:130],j['company']+' · '+j['location'],now(),None))
                count+=1
    return count

async def sync_sources():
    with connect() as c:
        providers=[dict(x) for x in c.execute('SELECT * FROM providers WHERE enabled=1')]
    for p in providers:
        try:
            result=await run_sync(p)
            log.info('Synced %s: %s',p['id'],result)
        except Exception as exc:log.error('Sync failed %s: %s',p['id'],exc)

async def main():
    init_db()
    while True:
        await sync_sources()
        total=process_alerts()
        log.info('Queued %s new job alerts and %s follow-ups',total,process_followups())
        await asyncio.sleep(int(os.getenv('SYNC_INTERVAL_SECONDS','3600')))

if __name__=='__main__':asyncio.run(main())
