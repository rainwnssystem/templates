import sys
import logging
import pymysql
import json
rds_host  = "ws-rds-mysql.cluster-cukiuqrdabzk.ap-northeast-2.rds.amazonaws.com"
user_name = "admin"
password = "password"
db_name = "ws"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

try:
    conn = pymysql.connect(host=rds_host, user=user_name, passwd=password, db=db_name, connect_timeout=5)
except pymysql.MySQLError as e:
    logger.error("연결 실패!")
    logger.error(e)
    sys.exit()

logger.info("연결 성공!")

def lambda_handler(event, context):
    username = event['username']
    password = event['password']

    item_count = 0
    sql_string = f"insert into USER (username, password) values('{username}', '{password}')"
    
    with conn.cursor() as cur:
        cur.execute("create table if not exists USER ( username varchar(20) PRIMARY KEY, password varchar(20) NOT NULL)")
        cur.execute(sql_string)
        conn.commit()

    return "회원가입 성공!"