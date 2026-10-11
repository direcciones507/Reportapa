"""Read-only aggregate inventory; no names, phone numbers, photo contents or secrets."""
import json,os,shutil
from pathlib import Path
import psycopg

def main():
    directory=Path(os.environ['PHOTO_DIR'])
    disk=shutil.disk_usage(directory)
    sizes=[p.stat().st_size for p in directory.glob('*.jpg') if p.is_file()]
    with psycopg.connect(os.environ['DATABASE_URL']) as c:
        c.execute('SET TRANSACTION READ ONLY')
        c.execute("SET LOCAL statement_timeout='5s'")
        count=c.execute('SELECT count(*) FROM reports').fetchone()[0]
        dbbytes=c.execute('SELECT pg_database_size(current_database())').fetchone()[0]
        tablebytes=c.execute("SELECT pg_total_relation_size('reports')").fetchone()[0]
        maxconn=int(c.execute('SHOW max_connections').fetchone()[0])
        active=c.execute('SELECT count(*) FROM pg_stat_activity').fetchone()[0]
        waiting=c.execute('SELECT count(*) FROM pg_locks WHERE NOT granted').fetchone()[0]
    print(json.dumps({'reports':count,'database_bytes':dbbytes,'reports_with_indexes_bytes':tablebytes,
        'max_connections':maxconn,'current_connections':active,'waiting_locks':waiting,
        'photo_volume_bytes':disk.total,'photo_volume_used_bytes':disk.used,'photo_volume_free_bytes':disk.free,
        'photos':len(sizes),'photo_bytes':sum(sizes),'photo_average_bytes':sum(sizes)/len(sizes) if sizes else None,
        'photo_max_bytes':max(sizes) if sizes else None,'photo_reserve_bytes':32*1024*1024},indent=2))

if __name__=='__main__':main()
