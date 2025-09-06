import MySQLdb
import os
from dotenv import load_dotenv

# Load .env if running locally
load_dotenv()

conn = MySQLdb.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    passwd=os.getenv("DB_PASSWORD", ""),
    port=int(os.getenv("DB_PORT", 3306))
)

cursor = conn.cursor()
cursor.execute("CREATE DATABASE IF NOT EXISTS file_utility")
cursor.execute("USE file_utility")

# Create users table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS AppDB (
        User_ID INT AUTO_INCREMENT PRIMARY KEY,
        First_Name VARCHAR(100) NOT NULL,
        Last_Name VARCHAR(100) NOT NULL,
        Email_ID VARCHAR(150) NOT NULL UNIQUE,
        Pass_Word VARCHAR(200) NOT NULL
    )
''')

conn.commit()
conn.close()
