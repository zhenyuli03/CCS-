# loginvalid = [[1,234],[2,45],[5,234]]

# print(loginvalid)
# tokenToMLCM = [i[1] for i in loginvalid]
# print(tokenToMLCM)
# if 4567 in tokenToMLCM:
#     loginvalid.pop(tokenToMLCM.index(123))
#     print(loginvalid)
# deviceID = '12334'
# deviceID2 = 'asdf'
# print("------MLCM发送换线指令到模组PI %s失败,返回内容：%s"%(deviceID,deviceID2))
# -*- coding: utf-8 -*-
s = b'\xba\xb8\xbd\xd3\xd5\xbe'
# ss = s.encode('raw_unicode_escape')
# print(type(s))
# print(type(ss))
# print(ss)
a = '焊锡站'
b = a.encode('utf-8')
print(b)
sss = b.decode()
print(sss)
