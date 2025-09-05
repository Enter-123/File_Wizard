import MySQLdb

# Connect to MySQL (adjust user, password, and host as per your system)
conn = MySQLdb.connect(
    host="localhost",
    user="root",
    passwd="Sayyed@786"
)

cursor = conn.cursor()
cursor.execute("CREATE DATABASE IF NOT EXISTS file_utility")
cursor.execute("USE file_utility")

cursor.execute('''
    CREATE TABLE IF NOT EXISTS AppDB(
        User_ID INT AUTO_INCREMENT PRIMARY KEY,
        First_Name VARCHAR(100) NOT NULL,
        Last_Name VARCHAR(100) NOT NULL,
        Email_ID VARCHAR(150) NOT NULL UNIQUE,
        Pass_Word VARCHAR(200) NOT NULL
    )
''')

conn.commit()
conn.close()
