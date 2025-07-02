'''import mysql.connector
import logging

logger = logging.getLogger("database_setup")

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root'
}
DATABASE_NAME = 'discord_osint'

SCHEMA_QUERIES = [
    """
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id BIGINT PRIMARY KEY,
        prefix VARCHAR(16) NOT NULL DEFAULT '!',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_footprints (
        id INT AUTO_INCREMENT PRIMARY KEY,
        discord_user_id BIGINT NOT NULL,
        guild_id BIGINT NOT NULL,
        query_email VARCHAR(128) NOT NULL,
        results_json TEXT,
        searched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS search_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        discord_user_id BIGINT NOT NULL,
        guild_id BIGINT NOT NULL,
        command VARCHAR(64) NOT NULL,
        params TEXT,
        executed_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        discord_user_id BIGINT PRIMARY KEY,
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        search_count INT DEFAULT 0
    )
    """
]

def setup_database():
    try:
        # Step 1: Connect as root (no database yet)
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        #conn.autocommit = True
        cursor = conn.cursor()
        # Step 2: Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE_NAME}")
        logger.info(f"Ensured database `{DATABASE_NAME}` exists.")
        cursor.close()
        conn.close()

        # Step 3: Connect to the new/existing database
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DATABASE_NAME
        )
        cursor = conn.cursor()
        # Step 4: Create all tables
        for query in SCHEMA_QUERIES:
            try:
                cursor.execute(query)
                logger.info("Executed query: %s", query.strip().splitlines()[0])
            except Exception as e:
                logger.error("Error executing query: %s\n%s", query, e)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Database setup complete.")
    except Exception as e:
        logger.error(f"Database setup failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    setup_database()
'''