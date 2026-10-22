import os
import time
import select
import logging
import psycopg2
import psycopg2.extensions
from pathlib import Path
from openai import OpenAI

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

def get_announcement_mp3_files(text, trackid, count):
    logging.info('Generating audio file with text:\n' + text)
    print('Count: ', count)
    client = OpenAI()
    speech_file_path = Path(__file__).parent / Path(str(trackid) + '-' + str(count) + '~0.mp3')

    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice="nova",
        input=text,
        instructions="Speak with excitement like a radio DJ",
    ) as response:
        response.stream_to_file(speech_file_path)

DB_HOST = get_env_value('DB_HOST')
DB_NAME = get_env_value('DB_NAME')
DB_USER = get_env_value('DB_USER')
DB_PASSWORD = get_env_value('DB_PASSWORD')

CATEGORY = 'G golden oldie'

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

def lookup_category_tracks(conn, categoryid: int) -> str | None:
    sql = """
        SELECT t.id
        FROM tracks t
        WHERE categoryid = %s
    """

    with conn.cursor() as cur:
        debug_sql = cur.mogrify(
            sql,
            (categoryid,),
        ).decode("utf-8", errors="replace")

        logging.info("lookup_category playback_id=%s", categoryid)
        logging.debug("lookup_category SQL=%s", debug_sql)

        cur.execute(sql, (categoryid,))
        rows = cur.fetchall()

        logging.info("lookup_category row=%r", rows)

        return rows if rows and rows else None

def lookup_categoryid(conn, CATEGORY: int) -> str | None:
    sql = """
        SELECT id
        FROM categories
        WHERE category = %s
        LIMIT 1
    """

    with conn.cursor() as cur:
        debug_sql = cur.mogrify(
            sql,
            (CATEGORY,),
        ).decode("utf-8", errors="replace")

        logging.info("lookup_category %s", CATEGORY)
        logging.debug("lookup_category SQL=%s", debug_sql)

        cur.execute(sql, (CATEGORY,))
        row = cur.fetchone()

        logging.info("lookup_category row=%r", row)

        return row[0] if row and row[0] else None

def lookup_title(conn, trackid: int) -> str | None:
    sql = """
        SELECT COALESCE(NULLIF(t.track_display_name, ''), NULLIF(t.track_name, ''))
        FROM tracks t
        WHERE t.id = %s
        LIMIT 1
    """

    with conn.cursor() as cur:
        logging.info("Looking up track.id=%s", trackid)
        logging.debug(
            "Track query: %s",
            cur.mogrify(sql, (trackid,)).decode(
                "utf-8",
                errors="replace",
            ),
        )

        cur.execute(sql, (trackid,))
        row = cur.fetchone()

    logging.info("Track lookup result: %r", row)
    return row[0] if row and row[0] else None

def lookup_artist(conn, trackid: int) -> str | None:
    sql = """
        SELECT COALESCE(NULLIF(a.artist_display_name, ''), NULLIF(a.artist_name, ''))
        FROM tracks t
        LEFT JOIN artists a
          ON a.id = t.artistid
        WHERE t.id = %s
        LIMIT 1
    """

    with conn.cursor() as cur:
        logging.info("Looking up track.id=%s", trackid)
        logging.debug(
            "Playback query: %s",
            cur.mogrify(sql, (trackid,)).decode(
                "utf-8",
                errors="replace",
            ),
        )

        cur.execute(sql, (trackid,))
        row = cur.fetchone()

    logging.info("Artist lookup result: %r", row)
    return row[0] if row and row[0] else None

def main():
    conn = connect_db()

    listener_conn = None

    latest_id = None

    if listener_conn is None or listener_conn.closed:
        listener_conn = connect_listener()

    try:
        categoryid = lookup_categoryid(conn, CATEGORY)
        category_tracks = lookup_category_tracks(conn, categoryid)
        for trackid in category_tracks:
            print("Track ID", trackid[0])
            song_artist = lookup_artist(conn, trackid)
            song_title = lookup_title(conn, trackid)
            print("Song Artist: ", song_artist)
            print("Song Name: ", song_title)
            count = 1
            text = song_artist + ' with ' + song_title + ' on J-95!'
            get_announcement_mp3_files(text,trackid[0],count)
            time.sleep(2)
            count = 2
            text = song_title + ", that's "  + song_artist + ' on K-V-W-J!'
            if 'ABBA' in text:
                pass
            get_announcement_mp3_files(text,trackid[0],count)

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
