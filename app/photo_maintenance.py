"""Retry physical erasure without resurrecting deleted report data."""
import re

def cleanup_photos(connect,directory):
    with connect() as c:
        # One worker owns each queue row; unlink(missing_ok) tolerates retries.
        rows=c.execute('SELECT filename FROM photo_cleanup ORDER BY filename LIMIT 100 FOR UPDATE SKIP LOCKED').fetchall()
        for row in rows:
            name=row['filename']
            if not re.fullmatch(r'[a-f0-9]{32}\.jpg',name): continue
            try:(directory/name).unlink(missing_ok=True)
            except OSError:continue
            c.execute('DELETE FROM photo_cleanup WHERE filename=%s',(name,))
