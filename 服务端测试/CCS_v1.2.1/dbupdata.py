import sqlite3
import os

DBpath = os.getcwd()+"/doc/sydoc/totalsqlit.db"
# 删除整张表
con = sqlite3.connect(DBpath)
# con.execute('DROP TABLE nodelogin')
con.execute('DROP TABLE columnBarData')
con.execute('DROP TABLE tableDataAbnomal')