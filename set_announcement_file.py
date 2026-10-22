import os
import time
import select
import logging
import shutil
import psycopg2
import psycopg2.extensions
from pathlib import Path

def get_env_value(env_variable):
    try:
        return os.environ[env_variable]
    except KeyError:
        error_msg = 'Set the {} environment variable'.format(env_variable)
        #raise ImproperlyConfigured(error_msg)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

DB_HOST = get_env_value('DB_HOST')
DB_NAME = get_env_value('DB_NAME')
DB_USER = get_env_value('DB_USER')
DB_PASSWORD = get_env_value('DB_PASSWORD')

CATEGORY = 'E beatles-beachboys-elvis'

DB_CONFIG = {
    "host": DB_HOST,
    "port": 5432,
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
}

def connect_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn

def connect_listener():
    conn = psycopg2.connect(**DB_CONFIG)

    # LISTEN must not remain inside an uncommitted transaction.
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    with conn.cursor() as cur:
        cur.execute("LISTEN rds_playback;")

    logging.info("Listening for PostgreSQL notifications on rds_playback")
    return conn

def find_announcement_file(trackid, count):
    target_file = f"{trackid}-{count}~0.mp3"
    
    # 1. Base absolute folder path used to find files on the Linux/WSL side
    source_folder = Path('/mnt/zara/Song Announcements').resolve()
    symlink_path = source_folder / 'ANNOUNCEMENT~0.mp3'

    # Search for the track announcement file
    file_matches = list(source_folder.rglob(target_file))

    if file_matches:
        logging.info(f"Target announcement found: {file_matches[0].name}")
        found_file = file_matches[0].resolve()
    else:
        logging.info("Announcement file not found, fallback to dummy file.")
        dummy_matches = list(source_folder.rglob('DUMMY~0.mp3'))
        
        if not dummy_matches:
            logging.error("Critical error: DUMMY~0.mp3 could not be found in the directory!")
            return None
            
        found_file = dummy_matches[0].resolve()

    # 2. CRITICAL FIX: Calculate the relative path from the symlink's directory
    # This turns '/mnt/zara/Song Announcements/dummy~0.mp3' into just 'dummy~0.mp3'
    relative_target = os.path.relpath(found_file, start=symlink_path.parent)

    # 3. Safely clear out the existing symlink path (working or broken)
    if symlink_path.exists() or symlink_path.is_symlink():
        symlink_path.unlink()
        logging.info(f"Removed old symlink at: {symlink_path}")
        
    # 4. Create the RELATIVE symlink
    try:
        # Passing the raw relative string tells the symlink to point to the local filename
        symlink_path.symlink_to(relative_target)
        logging.info(f"Successfully updated relative symlink: {symlink_path.name} -> {relative_target}")
        return symlink_path
    except OSError as e:
        logging.error(f"Operating System Error creating symlink: {e}")
        return None

def lookup_trackid(conn, playback_id: int) -> str | None:
    sql = """
        SELECT t.id
        FROM playback p
        JOIN tracks t
          ON t.id = p.trackid
        WHERE p.id = %s
        LIMIT 1
    """

    with conn.cursor() as cur:
        debug_sql = cur.mogrify(
            sql,
            (playback_id,),
        ).decode("utf-8", errors="replace")

        logging.info("lookup_category playback_id=%s", playback_id)
        logging.debug("lookup_category SQL=%s", debug_sql)

        cur.execute(sql, (playback_id,))
        row = cur.fetchone()

        logging.info("lookup_category row=%r", row)

        return row[0] if row and row[0] else None

def lookup_category(conn, playback_id: int) -> str | None:
    sql = """
        SELECT c.category
        FROM playback p
        JOIN tracks t
          ON t.id = p.trackid
        LEFT JOIN categories c
          ON c.id = t.categoryid
        WHERE p.id = %s
        LIMIT 1
    """

    with conn.cursor() as cur:
        debug_sql = cur.mogrify(
            sql,
            (playback_id,),
        ).decode("utf-8", errors="replace")

        logging.info("lookup_category playback_id=%s", playback_id)
        logging.debug("lookup_category SQL=%s", debug_sql)

        cur.execute(sql, (playback_id,))
        row = cur.fetchone()

        logging.info("lookup_category row=%r", row)

        return row[0] if row and row[0] else None

def lookup_latest_playback_id(conn) -> int | None:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id
            FROM playback
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cur.fetchone()

    return row[0] if row else None

def process_notification(
    conn,
    notification,
) -> tuple[str | None, str | None]:
    logging.info(
        "Received notification: channel=%s pid=%s playback_id=%r",
        notification.channel,
        notification.pid,
        notification.payload,
    )

    try:
        playback_id = int(notification.payload)
    except (TypeError, ValueError):
        logging.exception(
            "Invalid playback ID payload received: %r",
            notification.payload,
        )
        return None

    return lookup_trackid(conn, playback_id), lookup_category(conn, playback_id)

def main():
    conn = connect_db()

    count = 1

    listener_conn = None

    latest_id = None

    if listener_conn is None or listener_conn.closed:
        listener_conn = connect_listener()

        latest_id = lookup_latest_playback_id(listener_conn)

        if latest_id is not None:
            trackid = lookup_trackid(
                listener_conn,
                latest_id,
            )
            current_song_category = lookup_category(
                listener_conn,
                latest_id,
            )

            if count >= 3:
                count = 1
            announcement_file = find_announcement_file(trackid, count)
            count += 1

    try:
        while True:
            if listener_conn is None or listener_conn.closed:
                listener_conn = connect_listener()

            # Wait for a Postgres notification, up to one second.
            ready, _, _ = select.select([listener_conn], [], [], 1)

            if ready:
                listener_conn.poll()

                while listener_conn.notifies:
                    current_song_category = None
                    that_80s_show = False
                    a_category = False
                    b_category = False
                    c_category = False
                    d_category = False
                    e_category = False
                    f_category = False
                    g_category = False
                    notification = listener_conn.notifies.pop(0)
                    trackid, current_song_category = process_notification(
                        listener_conn,
                        notification,
                    )

                    if count >= 3:
                        count = 1
                    announcement_file = find_announcement_file(trackid, count)
                    count += 1

    except KeyboardInterrupt:
        logging.info("Exiting on keyboard interrupt")
    except psycopg2.Error as e:
        logging.exception("Database error: %s", e)
    except psycopg2.OperationalError as exc:
        logging.error("PostgreSQL listener connection error: %s", exc)

        if listener_conn:
            try:
                listener_conn.close()
            except Exception:
                pass

        listener_conn = None
        time.sleep(5)

    except Exception:
        logging.exception("Unhandled RDS listener error")
        time.sleep(2)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
