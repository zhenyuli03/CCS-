import hashlib

# MD5加密
def keymd5(src):
    str_md5 = hashlib.md5(src.encode("utf-8")).hexdigest()
    str_md5 = str_md5.upper()
    return str_md5


secertkey = '1111111111'
userIP = '127.0.0.1'
userPort ='4000'
baseInfor ='20120408123}DPS-400AB-31 A}S03}2次站}第一段}焊接站}'
print(secertkey+userIP+userPort+baseInfor)
print(keymd5(secertkey+userIP+userPort+baseInfor))
# print(keymd5('Delta-TTDD-产线现场集中管理'))