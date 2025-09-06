import MySQLdb
import os
from dotenv import load_dotenv

# Load .env if running locally
load_dotenv()

conn = MySQLdb.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    passwd=os.getenv("DB_PASSWORD"),
    port=int(os.getenv("DB_PORT"))
)

cursor = conn.cursor()
cursor.execute("CREATE DATABASE IF NOT EXISTS railway")
cursor.execute("USE railway")

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
