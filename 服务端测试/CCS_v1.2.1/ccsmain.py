from flask import Flask, request, render_template, redirect, url_for
from flask.json import jsonify
from flask_socketio import SocketIO, emit
import socket
import threading
from threading import Lock
from flask_cors import *
import requests
import sqlite3
import json
import os
import xlwt
import xlrd
from xlutils.copy import copy
import time
from datetime import date,datetime, timedelta
import re
import hashlib

# 创建Flask类的实例
app = Flask(__name__)
CORS(app, supports_credentials=True, resources=r'/*')
socketio = SocketIO(app, cors_allowed_origins='*')

lock = Lock()
headers = {"Content-Type": "application/json"}
secertkey_CCS = 'A558506C036DD29B08EABB1CA2CD0C5C'
DBpath = os.getcwd()+"/doc/sydoc/totalsqlit.db"  # 数据库名

excelInstruID = [] # excel所有节点ID
# 添加节点类型，后续应在CCS由客户添加管理
# devicetype = ['Manual-station','Soldering-iron','Electric-lock']
loginvalid = []  # 登录验证通过的用户信息
loginadd = [] # 新节点登录信息-临时存放
tokenToCCS = [] # 所有登录成功的密钥
exitdown = [] # 节点退出ID-临时存放
intimedatas = [] # 实时数据-临时存放
clresultadd = [] # 换线结果-临时存放
stateadd = [] # 状态改变-临时存放

alarmDatas = [] # 存放所有报警数据
waitDatas = [] # 存放所有待机数据
onlineDates = [] # 存放在线节点数据
# 监控界面统计数据
statsDatas = [{'name': '在线总数', 'value': 0,'tip':'当前所有在线的节点'}, {
    'name': '报警总数', 'value': 0,'tip':'当前所有在线的节点'}, {'name': '离线总数', 'value': 0,'tip':'当前所有在线的节点'}]
# 异常统计直方图数据
columnBarData = {
    'dataAxis': [time.strftime("%m/%d", time.localtime())],
    'dataserror': [0],
    'dataswarn': [0],
}
tableDataAbnomal = []  # 异常表格数据
selectCascadeValue = ["ALLONLINE", "ALLONLINE"]  # 筛选对象默认值
InstruOptions = []  # 筛选选择器的所有选项
deviceData = []  # 监控界面节点实时状态数据
allmonitorData = [] # 保存所有在线节点的实时数据

currentadmin = '---'  # 登录界面用户名
cltimexls1 = '' # 记录换线日期
exceleimgName = ['Manual-station','Soldering-iron','Electric-lock'] # 每个卡片显示的图片，默认为人工站


# MD5加密
def keymd5(src):
    str_md5 = hashlib.md5(src.encode("utf-8")).hexdigest()
    str_md5 = str_md5.upper()
    return str_md5

# 创建一个txt文件，保存log,包括登录信息，异常情况等
def text_create(msg):
    try:
        # 保证本地只保存30天的日志数据
        for root,dir,files in  os.walk(os.getcwd()+'/doc/log/'):
            if len(files) >30:
                os.remove(os.getcwd()+'/doc/log/'+files[0])
        cltimexls1 = datetime.now().strftime('%Y-%m-%d')
        path = os.getcwd()+'/doc/log/' + cltimexls1 + '.txt'
        file = open(path, 'a+')
        file.write(msg)
    except:
        print('保存数据失败！')
    finally:
        file.close()

# 读取本地文件
def getdata_txt(filepath):
    b = open(filepath, "r", encoding='UTF-8')
    datas = []
    datas = b.read()
    if datas != '':
        datas = json.loads(datas)
    else:
        datas = ''
    return datas

# 创建新的xls表
def creatxls(files, path, lietou, cltimexls):
    # 保证本地只保存30天的数据
    for root,dir,files in  os.walk(os.getcwd()+'/doc/换线记录/'):
        if len(files) >30:
            os.remove(os.getcwd()+'/doc/换线记录/'+files[0])
    if cltimexls+'.xls' not in files:  
        workbook = xlwt.Workbook(encoding='utf-8')  # 新建工作簿
        sheet1 = workbook.add_sheet("sheet1")  # 新建sheet
        for i in range(len(lietou)):
            sheet1.write(0, i, lietou[i])  
        workbook.save(path)  # 保存
        xlsreturn = '--当前日期的文件新建成功---'
    else:
        xlsreturn = '---当前日期的文件已经存在---'
    return xlsreturn

# 读取xls文件，增加新数据
def addcldataxls(path, aa):
    data_xlsx = xlrd.open_workbook(path)
    excel = copy(data_xlsx)
    table = excel.get_sheet(0)
    i = data_xlsx.sheets()[0].nrows
    for m in range(len(aa)):
        for n in range(len(aa[m])):
            table.write(i+m, n, aa[m][n])  
    excel.save(path)

# 读取xls文件，更新换线结果
def upcldataxls(path, aa, rownum):
    data_xlsx = xlrd.open_workbook(path)
    excel = copy(data_xlsx)
    table = excel.get_sheet(0)
    table.write(rownum, 8, aa[8])  
    table.write(rownum, 10, aa[10])  
    excel.save(path)

# 获取本机IOT的IP地址提供前端与后台进行socketIO连接
def getIP(vaildresult):
    vaildresult1 = vaildresult
    getPMM3IP = '127.0.0.1'
    # 获取本机IOT-IP
    try:
        ss = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ss.connect(('8.8.8.8', 80))
        ip = ss.getsockname()[0]
    except:
        vaildresult1 = 3  # 请检查IOT网络
        print('请检查IOT网络！')
    else:
        getPMM3IP = ip
    finally:
        ss.close()
    return getPMM3IP, vaildresult1

# 检验IP地址合法性，用于验证节点发送的IP是否合法，防止后台访问出错
def check_ip(ipAddr):
    compile_ip = re.compile(
        '^(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|[1-9])\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)\.(1\d{2}|2[0-4]\d|25[0-5]|[1-9]\d|\d)$')
    if compile_ip.match(ipAddr):
        return True
    else:
        return False

# 创建数据库及数据库的表
# DBpath:"SQlitDEMO.db"
# DBread:"CREATE TABLE IF NOT EXISTS nodelogin(deviceID,tokenUser,userIP,userPort)"
def creatDB(DBpath, DBheader):
    # 指定创建数据库的路径
    con = sqlite3.connect(DBpath)
    # 创建游标
    cur = con.cursor()
    # 创建表
    cur.execute(DBheader)
    # 提交
    con.commit()
    # 关闭游标
    cur.close()
    # 断开数据库连接
    con.close()

# 插入单条数据
# DBpath:"SQlitDEMO.db"
# DBread:"INSERT INTO nodelogin values('111','222','3333','5002')"
def insertDB_one(DBpath, command, datasDB):
    # 指定创建数据库的路径
    con = sqlite3.connect(DBpath)
    # 创建游标
    cur = con.cursor()
    cur.execute(command, datasDB)
    # try:
    #     # 插入数据
    #     cur.execute(command, datasDB)
    # except:
    #     # 回滚
    #     con.rollback()
    # else:
    #     # 提交
    con.commit()
    # 关闭游标
    cur.close()
    # 断开数据库连接
    con.close()

# 插入多条数据
# DBpath:"SQlitDEMO.db"
# command:"INSERT INTO nodelogin values(?,?,?,?)"
# DBread: [('1', '1', '1', '1'),('2', '3', '3', '4')]
def insertDB_more(DBpath, command, datasDB):
    # 指定创建数据库的路径
    con = sqlite3.connect(DBpath)
    # 创建游标
    cur = con.cursor()
    try:
        # 插入数据
        cur.executemany(command, datasDB)
    except:
        # 回滚
        con.rollback()
    else:
        # 提交
        con.commit()
    # 关闭游标
    cur.close()
    # 断开数据库连接
    con.close()

# 查询数据返回表的所有内容
# DBpath:"SQlitDEMO.db"
# DBread:"SELECT deviceID,tokenUser,userIP,userPort from nodelogin"
def readDB(DBpath, DBread):
    readdatas = []
    # 指定创建数据库的路径
    con = sqlite3.connect(DBpath)
    try:
        # 查询数据
        cursor = con.execute(DBread)
    except:
        # 回滚
        con.rollback()
    else:
        for row in cursor:
            readdatas.append(row)
    # 断开数据库连接
    con.close()
    return readdatas

# 更新或删除某条数据
# DBpath:"SQlitDEMO.db"
# command:"UPDATE nodelogin SET userIP=? WHERE deviceID=?"/"DELETE FROM nodelogin WHERE deviceID=?"
# DBread: ("66", '1')/('111',)
def updelDB(DBpath, command, datasDB):
    # 指定创建数据库的路径
    con = sqlite3.connect(DBpath)
    # 创建游标
    cur = con.cursor()
    try:
        for i in range(len(command)):
            # 更新或删除数据
            cur.execute(command[i],datasDB[i])
    except:
        # 回滚
        con.rollback()
    else:
        # 提交
        con.commit()
    # 关闭游标
    cur.close()
    # 断开数据库连接
    con.close()

############ 节点访问接口相关处理函数#################
# 记录每次发送换线指令信息
def updataclform( cldeviceID, cloneIP, clline, clnewModel_number, current_state):
    global allCLdata, currentadmin, cltimexls1, loginvalid
    # 若当前日期不等于初始日期则更新日期记录全局变量，同时新建一个换线记录xls表
    if datetime.now().strftime('%Y-%m-%d') != cltimexls1:
        cltimexls1 = datetime.now().strftime('%Y-%m-%d')
        path = os.getcwd()+'/doc/换线记录/'+ cltimexls1 +'.xls'
        try:
            lietou = ["换线日期","换线时间","接入点类型","接入点ID","线别","站别","换线机种/工单","发送换线指令","换线结果","换线操作员","备注"]
            files = os.listdir(os.getcwd()+'/doc/换线记录/')
            xlsreturn = creatxls(files, path, lietou, cltimexls1)
        except:
            print('---新创建换线记录失败---')
            msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            msg += ' ERROR:' + ' 记录换线信息时新建换线记录xls表失败\n'
            text_create(msg)
        else:
            allCLdata = []
    modelType = ''
    station = ''
    ############################################
    aaa = [i[0] for i in loginvalid]
    if cldeviceID in aaa:
        j = aaa.index(cldeviceID)
        modelType = loginvalid[j][6]
        station = loginvalid[j][5][5]

    CLrestule = 'waiting' # 等待节点返回换线结果
    remarks = '无'
    if current_state == '10':
        CLcommand = 'OK'
        remarks = '控制台发送换线指令成功'
    else:
        CLcommand = 'NG'
        remarks = '控制台发送换线指令失败'

    aa = {
        'currentData':datetime.now().strftime('%Y-%m-%d'),
        'currentTime':datetime.now().strftime('%H:%M:%S'),
        'modelType':modelType,
        'modelID':cldeviceID,
        'line': clline,
        'station': station,
        'newModel_number':clnewModel_number,
        'CLcommand': CLcommand,
        'CLrestule': CLrestule,
        'CLadmin':currentadmin,
        'remarks': remarks
    }
    allCLdata.insert(0, aa)
    cc = []
    bb = [datetime.now().strftime('%Y-%m-%d'),datetime.now().strftime('%H:%M:%S'), modelType, cldeviceID, clline, station, clnewModel_number,CLcommand,CLrestule, currentadmin, remarks]
    cc.append(bb)
    # 将每次换线记录添加到对应的xls表里
    path = os.getcwd()+'/doc/换线记录/'+ cltimexls1 +'.xls'
    try:
        addcldataxls(path, cc)
    except:
        print('---添加换线记录失败---')
        msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg += ' ERROR:' + ' 换线时添加换线记录失败\n'
        text_create(msg)
    else:
        print('---添加换线记录成功---')

# 得到指定日期的换线记录
def getxlsdata(usertime):
    global allCLdata
    selecttime = usertime.strftime("%Y-%m-%d")
    path = os.getcwd()+'/doc/换线记录/'+ str(selecttime) +'.xls'
    data_xlsx = xlrd.open_workbook(path)
    setsprofile = data_xlsx.sheets()[0]
    allCLdata = []
    for x in range(setsprofile.nrows-1,-1,-1):
        if x>0:
            bb = {}
            bb['currentData'] = setsprofile.cell_value(x,0)
            bb['currentTime'] = setsprofile.cell_value(x,1)
            bb['modelType'] = setsprofile.cell_value(x,2)
            bb['modelID'] = setsprofile.cell_value(x,3)
            bb['line'] = setsprofile.cell_value(x,4)
            bb['station'] = setsprofile.cell_value(x,5)
            bb['newModel_number'] = setsprofile.cell_value(x,6)
            if setsprofile.cell_value(x,7) == 'OK':
                bb['CLcommand'] = '1'
            else:
                bb['CLcommand'] = '2'
            if setsprofile.cell_value(x,8) == 'OK':
                bb['CLrestule'] = '1'
            elif setsprofile.cell_value(x,8) == 'FAIL':
                bb['CLrestule'] = '2'
            else:
                bb['CLrestule'] = '3' # 等待节点返回换线结果
            bb['CLadmin'] = setsprofile.cell_value(x,9)
            bb['remarks'] = setsprofile.cell_value(x,10)
            allCLdata.append(bb)

# 记录每次接收换线结果
def updataclresult(clresult):
    global allCLdata
    try:
        # 获取当天换线记录
        getxlsdata(date.today())
    except:
        print('打开当天换线记录失败')
    else:
        rownum = 1 # 需要更新换线结果的行数
        for i in range(len(allCLdata)):
            if clresult["deviceID"] == allCLdata[i]['modelID']:
                rownum = i+1 # 因为有列头
                aa = []
                aa.append(allCLdata[i]['currentData'])
                aa.append(allCLdata[i]['currentTime'])
                aa.append(allCLdata[i]['modelType'])
                aa.append(allCLdata[i]['modelID'])
                aa.append(allCLdata[i]['line'])
                aa.append(allCLdata[i]['station'])
                aa.append(allCLdata[i]['newModel_number'])
                if allCLdata[i]['CLcommand'] == '1':
                    aa.append('OK')
                else:
                    aa.append('NG')  
                aa.append(clresult["changeLineResult"]) # 'OK'/'FAIL'
                aa.append(allCLdata[i]['CLadmin'])
                aa.append(clresult["description"]) # 更新备注
                # 及时将xls里的字母转为web定义的数字
                if clresult["changeLineResult"] == 'OK':
                    allCLdata[i]['CLrestule'] = '1'
                else:
                    allCLdata[i]['CLrestule'] = '2'
                allCLdata[i]['remarks'] = clresult["description"]
                # 将每次换线记录添加到对应的xls表里
                path = os.getcwd()+'/doc/换线记录/'+ datetime.now().strftime('%Y-%m-%d') +'.xls'
                try:
                    upcldataxls(path, aa, rownum)
                except:
                    print('---添加换线结果到换线记录失败---')
                    msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    msg += ' ERROR:' + ' 换线时添加换线结果到换线记录失败\n'
                    text_create(msg)
                else:
                    print('---添加换线结果到换线记录成功---')

# 得到选择器选择的所有节点实时数据
def getdecivedata():
    global deviceData, allmonitorData
    deviceData = []
    for i in range(len(allmonitorData)):
        # 如果节点类型与选择器一致或节点线别与选择器一致则进行显示
        if selectCascadeValue[1] == allmonitorData[i]['imgname'] or selectCascadeValue[1] == allmonitorData[i]['parameter'][0]['value']:
            deviceData.append(allmonitorData[i])

# 1.返回节点统计和节点状态实时数据-登录
def gettotalstatus_login(newdatas):
    global statsDatas, deviceData, allmonitorData
    statsDatas[0]['value'] += 1  # 有新节点在线总数加1
    if statsDatas[2]['value'] > 0:  # 防止出现负数
        # 离线总数减1
        statsDatas[2]['value'] -= 1
    # 节点状态实时数据增加1笔
    allmonitorData.append({
        'deviceID': newdatas[0],
        'oneIP': newdatas[2],
        'instrutip': [{'detail': '登录成功'}],
        'status': 1,
        'imgname': newdatas[6],
        'parameter': [
            {'name': "线别", 'value': newdatas[5][2]},
            {'name': "站别", 'value': newdatas[5][5]},
            {'name': "工单", 'value': newdatas[5][0]},
            {'name': "机种", 'value': newdatas[5][1]}, ]
    })
    if selectCascadeValue[0] == 'ALLONLINE': # 用户选择ALLONLINE默认为ALL
        deviceData = allmonitorData
    else:
        getdecivedata() # 得到选择器选择的所有节点实时数据
    
# 2.退出登录在线总数减1, 实时状态删除对应的信息
def gettotalstatus_exit(deviceID):
    global statsDatas, deviceData, allmonitorData, alarmDatas
    statsDatas[2]['value'] += 1
    if statsDatas[0]['value'] > 0:
        statsDatas[0]['value'] -= 1
    alarmID = [] # 当前在线节点报警总数
    for i in range(len(alarmDatas)):
        alarmID.append(alarmDatas[i]['modelID'])
    if deviceID in alarmID:
        statsDatas[1]['value'] -= 1 # 报警总数减一
        alarmDatas.pop(alarmID.index(deviceID))
    ##############################################################
    # 删除节点实时数据，下次登录再显示
    aaa = [i['deviceID'] for i in deviceData]
    if deviceID in aaa:
        deviceData.pop(aaa.index(deviceID))
    # 剔除离线节点实时数据
    aaa = [i['deviceID'] for i in allmonitorData]
    if deviceID in aaa:
        allmonitorData.pop(aaa.index(deviceID))
    

# 3.1返回该笔数据的总结果和提示消息
# 有FAIL时只显示FAIL信息
# 没有FAIL但有WARN时显示WARN信息
# 没有FAIL和WARN时显示PASS参数名和参数值，对数组型参数值则只显示参数名+PASS
def dataresult(lineData):
    result = 'PASS' # 默认为PASS
    instrutip = [{'detail': ''}]
    tipstring = ''
    a1 = []  # 用于存每个参数的判定结果
    b1 = []  # 用于存每个参数的提示消息内容
    for i in range(len(lineData)):
        if lineData[i][3] == '2':
            # 如果是没有上下限的参数结果全部是PASS，提示消息直接显示参数名加参数值
            tipstring += "'"+lineData[i][4]+"'"+lineData[i][8]+';'
        else:
            # 如果是数组型的参数值或数值参数
            if lineData[i][9] == 'PASS':
                if lineData[i][10] == '':  # 结果为PASS且备注为空表示数据正常
                    a1.append(lineData[i][9])
                    if lineData[i][3] == '0':  # 参数值是一个字符串
                        # 如果是PASS，且备注信息为空时则显示参数名和参数值
                        b1.append("'"+lineData[i][4]+"'"+lineData[i][8]+lineData[i][5]+';')
                    else:  # 参数值是一个数组
                        # 如果是PASS，且备注信息为空时则显示参数名和参数值
                        b1.append("'"+lineData[i][4]+"'"+'PASS'+';')
                else:
                     # 如果是PASS，且备注信息不为空时则显示参数名和备注信息，此时为SPC预警
                    a1.append('WARN')
                    b1.append("'"+lineData[i][4]+"'"+lineData[i][8]+lineData[i][5]+'-'+lineData[i][10]+';')
            else:
                # 如果是FAIL，则显示参数名和备注
                a1.append(lineData[i][9])
                if lineData[i][10] != '':
                    b1.append("'"+lineData[i][4]+"'"+lineData[i][8]+lineData[i][5]+'-'+lineData[i][10]+';')
                else:
                    b1.append("'"+lineData[i][4]+"'"+lineData[i][8]+lineData[i][5]+'-'+'超规格'+';')
    if len(a1)>0:
        # 对所有参数结果去重
        a = list(set(a1))
        if 'FAIL' in a:
            # 当多个参数中出现fail时以FAIL为最终结果
            for i in range(len(a1)):
                if a1[i] == 'FAIL':
                    result = 'FAIL'
                    tipstring += b1[i]
        elif 'WARN' in a:
            # 当多个参数中出现warn时以warn为最终结果
            for i in range(len(a1)):
                if a1[i] == 'WARN':
                    result = 'WARN'
                    tipstring += b1[i]
        else:
            # 参数结果全部为PASS
            result = 'PASS'
            tipstring = ''.join(b1)  # list转字符串
    instrutip = [{'detail': tipstring}]
    return result, instrutip

# 3.2更新异常直方图和表格
def getabnomaldata(lineInfor, result, instrutip):
    global statsDatas, columnBarData, tableDataAbnomal, loginvalid, alarmDatas
    if result!='PASS':
        ############## 更新异常信息表 ################  
        # 不管是超规格还是SPC预警都要插入到数据库的异常信息表中
        date = lineInfor['lineData'][0][1]  # 该笔数据的日期
        modelName = lineInfor['baseInfor']['STATION_NAME']
        cause = instrutip[0]['detail']
        insertDB_one(DBpath, "INSERT INTO tableDataAbnomal values(?,?,?)",
                    (date, modelName, cause))
        # 取出数据库的异常表倒数50行数据
        c = readDB(DBpath, "select * from 'tableDataAbnomal'order by date desc limit 50")
        tableDataAbnomal = []  # 异常表格显示当天异常信息
        for i in range(len(c)):
            # 只显示当天异常信息
            if c[i][0].split(' ')[0] == datetime.now().strftime('%Y-%m-%d'):
                d = {}
                d['date'] = c[i][0]
                d['modelName'] = c[i][1]
                d['cause'] = c[i][2]
                tableDataAbnomal.append(d)
        ############## 更新超规格和SPC预警次数 ################        
        a = lineInfor['lineData'][0][1].split(' ')[0].split('-')  # 该笔数据时间
        # 数据库最新日期的数据
        b = readDB(DBpath, "select * from 'columnBarData'order by dataAxis desc limit 1")
        errornum = 0  # 报警次数
        warnnum = 0  # SPC预警次数
        if result == 'WARN':
            warnnum = 1
        if result =='FAIL':
            errornum = 1 # 用于异常直方图次数相加
            ############ 得到报警数据,只统计真正不良次数 ###################
            alarmone = {}
            alarmone['nowtime'] = date # 报警时间
            alarmone['modelID'] = lineInfor['deviceID']
            alarmone['line'] = lineInfor["baseInfor"]["LINE_NAME"]
            alarmone['station'] = lineInfor["baseInfor"]["STATION_NAME"]
            alarmone['remarks'] = cause
            ##################################################
            aaa = [i[0] for i in loginvalid]
            if lineInfor['deviceID'] in aaa:
                alarmone['modelIP'] = loginvalid[aaa.index(lineInfor['deviceID'])][2]
            # 取出已经报警的所有节点
            onlineID = []
            for i in range(len(alarmDatas)):
                onlineID.append(alarmDatas[i]['modelID'])
            # 保证用户点击报警总数时显示所有在线节点最新的报警情况
            if len(alarmDatas) >0:
                if lineInfor['deviceID']  in onlineID:
                    alarmDatas.pop(onlineID.index(lineInfor['deviceID']))
            alarmDatas.append(alarmone)
            statsDatas[1]['value'] = len(alarmDatas)

        dataAxis = a[1]+'/'+a[2]  # 该笔数据的月/日
        dataserror = 0
        dataswarn = 0
        if b == []:  # 数据库没有数据直接插入当前数据
            dataserror = errornum
            dataswarn = warnnum
            insertDB_one(DBpath, "INSERT INTO columnBarData values(?,?,?)",
                        (dataAxis, dataserror, dataswarn))
        else:  # 数据库有数据
            if (a[1]+'/'+a[2]) == b[0][0]:  # 判断数据库最新日期与当前数据的日期是否一致
                dataserror = b[0][1]+errornum
                dataswarn = b[0][2]+warnnum
                updelDB(DBpath, ["UPDATE columnBarData SET dataserror=? WHERE dataAxis=?",
                                "UPDATE columnBarData SET dataswarn=? WHERE dataAxis=?"], [(dataserror, dataAxis), (dataswarn, dataAxis)])
            else:
                # 数据库没有该数据对应的日期时直接插入当前数据即可
                dataserror = errornum
                dataswarn = warnnum
                insertDB_one(DBpath, "INSERT INTO columnBarData values(?,?,?)",
                            (dataAxis, dataserror, dataswarn))
        # 取出数据库倒数7行数据
        c = readDB(
            DBpath, "select * from 'columnBarData'order by dataAxis desc limit 7")
        axisx = []  # 直方图横轴
        errory = []  # 直方图纵轴-报警次数
        warny = []  # 直方图纵轴-预警次数
        for i in range(len(c)):
            axisx.append(c[i][0])
            errory.append(c[i][1])
            warny.append(c[i][2])
        # 数据库取出的数据是从最后一行开始的，故要进行倒序
        axisx.reverse()
        errory.reverse()
        warny.reverse()
        columnBarData = {
            'dataAxis': axisx,
            'dataserror': errory,
            'dataswarn': warny,
        }
       
# 3.实时数据更新统计，异常和状态
def gettotalstatus_newdata(lineInfor):
    global  deviceData, allmonitorData
    ##########################################################
    aaa = [i['deviceID'] for i in allmonitorData]
    if lineInfor['deviceID'] in aaa:
        i = aaa.index(lineInfor['deviceID'])
        try:
            # 得到该笔数据的最终结果和提示消息
            result, instrutip = dataresult(lineInfor['lineData'])
            # # 更新报警统计，异常直方图数据和表格
            getabnomaldata(lineInfor, result, instrutip)
            # 更新提示消息和线别，站别，工单，机种
            if result =='FAIL':
                allmonitorData[i]['status'] = 2
            if result =='WARN':
                allmonitorData[i]['status'] = 4
            if result =='PASS':
                allmonitorData[i]['status'] = 1
            allmonitorData[i]['instrutip'] = instrutip
            allmonitorData[i]['parameter'][0]['value'] = lineInfor['baseInfor']['LINE_NAME']
            allmonitorData[i]['parameter'][1]['value'] = lineInfor['baseInfor']['STATION_NAME']
            allmonitorData[i]['parameter'][2]['value'] = lineInfor['baseInfor']['MO_NUMBER']
            allmonitorData[i]['parameter'][3]['value'] = lineInfor['baseInfor']['MODEL_NAME']
        except:
            print('实时数据接口-更新统计信息，异常情况和实时状态出错')
            msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            msg += ' ERROR: ' + '实时数据接口-更新统计信息，异常情况和实时状态出错\n'
            text_create(msg)
        else:
            print('实时数据接口-更新统计信息，异常情况和实时状态成功')
    # for i in range(len(allmonitorData)):
    #     if allmonitorData[i]['deviceID'] == lineInfor['deviceID']:
    #         # result, instrutip = dataresult(lineInfor['lineData'])
    #         # getabnomaldata(lineInfor, result, instrutip)
    #         try:
    #             # 得到该笔数据的最终结果和提示消息
    #             result,instrutip = dataresult(lineInfor['lineData'])
    #             # # 更新报警统计，异常直方图数据和表格
    #             getabnomaldata(lineInfor, result, instrutip)
    #             # 更新提示消息和线别，站别，工单，机种
    #             if result =='FAIL':
    #                 allmonitorData[i]['status'] = 2
    #             if result =='WARN':
    #                 allmonitorData[i]['status'] = 4
    #             if result =='PASS':
    #                 allmonitorData[i]['status'] = 1
    #             allmonitorData[i]['instrutip'] = instrutip
    #             allmonitorData[i]['parameter'][0]['value'] = lineInfor['baseInfor']['LINE_NAME']
    #             allmonitorData[i]['parameter'][1]['value'] = lineInfor['baseInfor']['STATION_NAME']
    #             allmonitorData[i]['parameter'][2]['value'] = lineInfor['baseInfor']['MO_NUMBER']
    #             allmonitorData[i]['parameter'][3]['value'] = lineInfor['baseInfor']['MODEL_NAME']
    #         except:
    #             print('实时数据接口-更新统计信息，异常情况和实时状态出错')
    #             msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #             msg += ' ERROR: ' + '实时数据接口-更新统计信息，异常情况和实时状态出错\n'
    #             text_create(msg)
    #         else:
    #             print('实时数据接口-更新统计信息，异常情况和实时状态成功')
    if selectCascadeValue[0] == 'ALLONLINE': # 用户选择ALLONLINE默认为ALL
        deviceData = allmonitorData
    else:
        getdecivedata() # 得到选择器选择的所有节点实时数据
    
# 4.更新换线结果(保证实时显示用户选择的节点数据)
def gettotalstatus_clresult(clresult):
    global deviceData, allmonitorData
    #######################################################
    aaa = [i['deviceID'] for i in allmonitorData]
    if clresult['deviceID'] in aaa:
        i = aaa.index(clresult['deviceID'])
        if clresult['changeLineResult'] == 'OK':
            allmonitorData[i]['status'] = 1
            allmonitorData[i]['instrutip'] = [{'detail': '换线成功'}]
        else:
            allmonitorData[i]['status'] = 2
            allmonitorData[i]['instrutip'] = [
                {'detail': '换线失败-'+clresult['description']}]
    if selectCascadeValue[0] == 'ALLONLINE': # 用户选择ALLONLINE默认为ALL
        deviceData = allmonitorData
    else:
        getdecivedata() # 得到选择器选择的所有节点实时数据
   

# 5.返回节点统计和节点状态实时数据-心跳信号
def gettotalstatus_heart(deviceID):
    global statsDatas, deviceData, loginvalid, allmonitorData, alarmDatas
    # 数据库更新掉线节点的数据
    loginstatus = 0
    # updelDB(DBpath, ["UPDATE nodelogin SET loginstatus=? WHERE deviceID=?"], [
    #         (loginstatus, deviceID)])
    statsDatas[2]['value'] += 1  # 离线总数加1，在线总数减1
    if statsDatas[0]['value'] > 0:
        statsDatas[0]['value'] -= 1
    alarmID = [] # 当前在线节点报警总数
    for i in range(len(alarmDatas)):
        alarmID.append(alarmDatas[i]['modelID'])
    if deviceID in alarmID:
        statsDatas[1]['value'] -= 1 # 报警总数减一
        alarmDatas.pop(alarmID.index(deviceID))
    #######################################################
    # 删除节点实时数据，下次登录再显示
    # 如果该节点在实时显示中则删除后不再显示，若该节点不在实时显示也没影响
    aaa = [i['deviceID'] for i in deviceData]
    if deviceID in aaa:
        deviceData.pop(aaa.index(deviceID))
    # 删除节点实时数据，下次登录再显示
    aaa = [i['deviceID'] for i in allmonitorData]
    if deviceID in aaa:
        allmonitorData.pop(aaa.index(deviceID))
    sockdatas = {}
    sockdatas = {
        'code': 200,
        'data': {
            'statsDatas': statsDatas,  # 节点统计
            'deviceData': deviceData,  # 节点状态
        }
    }
    return sockdatas

# 6.接收节点状态改变
def gettotalstatus_change(statedata):
    global  deviceData, allmonitorData
    ##########################################################
    aaa = [i['deviceID'] for i in allmonitorData]
    if statedata['deviceID'] in aaa:
        i = aaa.index(statedata['deviceID'])
        if statedata['stateChange'] == 'offline':  # 节点在线但设备离线
            # 更新设备状态
            allmonitorData[i]['status'] = 5
            allmonitorData[i]['instrutip'] = [{'detail': '设备离线,节点在线'}]
        elif statedata['stateChange'] == 'online':  # 节点在线,设备在线
            # 更新设备状态
            allmonitorData[i]['status'] = 1
            allmonitorData[i]['instrutip'] = [{'detail': '设备在线'}]
        elif statedata['stateChange'] == 'waiting':  # 等待换线
            # 更新设备状态
            allmonitorData[i]['status'] = 6
            allmonitorData[i]['instrutip'] = [{'detail': '设备等待换线'}]
        elif statedata['stateChange'] == 'changing':  # 正在换线
            # 更新设备状态
            allmonitorData[i]['status'] = 3
            allmonitorData[i]['instrutip'] = [{'detail': '设备正在换线'}]
        else:  # 此处待定（设备自检数据在实时数据那里即可判定为FAIL，不需要在这里再次更新状态）
            allmonitorData[i]['status'] = 2
            allmonitorData[i]['instrutip'] = [{'detail': '设备自检FAIL'}]
    # for i in range(len(allmonitorData)):
    #     if allmonitorData[i]['deviceID'] == statedata['deviceID']:
    #         if statedata['stateChange'] == 'offline':  # 节点在线但设备离线
    #             # 更新设备状态
    #             allmonitorData[i]['status'] = 5
    #             allmonitorData[i]['instrutip'] = [{'detail': '设备离线,节点在线'}]
    #         elif statedata['stateChange'] == 'online':  # 节点在线,设备在线
    #             # 更新设备状态
    #             allmonitorData[i]['status'] = 1
    #             allmonitorData[i]['instrutip'] = [{'detail': '设备在线'}]
    #         elif statedata['stateChange'] == 'waiting':  # 等待换线
    #             # 更新设备状态
    #             allmonitorData[i]['status'] = 6
    #             allmonitorData[i]['instrutip'] = [{'detail': '设备等待换线'}]
    #         elif statedata['stateChange'] == 'changing':  # 正在换线
    #             # 更新设备状态
    #             allmonitorData[i]['status'] = 3
    #             allmonitorData[i]['instrutip'] = [{'detail': '设备正在换线'}]
    #         else:  # 此处待定（设备自检数据在实时数据那里即可判定为FAIL，不需要在这里再次更新状态）
    #             allmonitorData[i]['status'] = 2
    #             allmonitorData[i]['instrutip'] = [{'detail': '设备自检FAIL'}]
    
    if selectCascadeValue[0] == 'ALLONLINE': # 用户选择ALLONLINE默认为ALL
        deviceData = allmonitorData
    else:
        getdecivedata() # 得到选择器选择的所有节点实时数据
   

########## 节点请求接口 #############
# 1.接收节点登录接口
@app.route("/LoginData", methods=['POST'])
def LoginDataFun():
    global loginvalid, loginadd, tokenToCCS
    if request.method == 'POST':
        returndata = {"result": "", "description": ""}
        msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            getdata = json.loads(request.get_data().decode("utf-8"))
            deviceID = getdata.get('deviceID')
            userIP = getdata.get('userIP')
            if check_ip(userIP):  # 判断解析的IP合法性
                userPort = getdata.get('userPort')
                baseInfor = getdata.get('baseInfor')
                infordata = baseInfor.split('}')
                usedatas = {
                    "deviceID": deviceID,
                    "userIP": userIP,
                    "userPort": userPort,
                    "baseInfor":
                        {
                            "MO_NUMBER": infordata[0],
                            "MODEL_NAME": infordata[1],
                            "LINE_NAME": infordata[2],
                            "SCETION_NAME": infordata[3],
                            "GROUP_NAME": infordata[4],
                            "STATION_NAME": infordata[5]
                        }
                }
                print("解析成功---接收节点登录信息：%s" % usedatas)
                tokenUser = keymd5(secertkey_CCS+deviceID + userIP+userPort+baseInfor)
                # 验证密钥和是否在中
                if (tokenUser == request.headers.get('token')) and (deviceID in excelInstruID):
                    # 取出已登录的节点ID
                    deviceIDlogin = [i[0] for i in loginvalid]
                    if deviceID in deviceIDlogin:  # 新节点已登录
                        returndata = {
                            "result": "FAIL", "description": "拒绝本次登录请求,您已登录,如需再次登录请先退出登录!"}
                    else:
                        # 保存每个节点ID,对应的token,IP和端口,登录时间,基本信息,节点类型,用于登录验证
                        deciveImg = 'Manual-station'
                        try:
                            deciveImg = exceleimgName[excelInstruID.index(deviceID)]
                        except:
                            deciveImg = 'Manual-station'
                        tokennode = [deviceID, tokenUser, userIP, userPort, [
                            round(time.time(), 1), 0], infordata, deciveImg]
                        # 该节点ID未登录应直接添加
                        tokenToCCS.append(tokenUser)
                        loginvalid.append(tokennode)
                        loginadd.append(tokennode)
                        returndata = {"result": "OK", "description": ""}
                        msg += ' INFOR: 节点' + '"' + deviceID + '"' + ' 登录成功\n'
                else:
                    print("已拒绝一次无权限的登录访问！")
                    print(deviceID)
                    print(userIP)
                    returndata = {"result": "FAIL",
                                  "description": "登录无权限, 拒绝访问, 请检查excel或密钥"}
                    msg += ' ERROR: 节点' + '"' + deviceID + '"' + '登录失败---请检查excel或密钥\n'
            else:
                print("已拒绝一次无权限的登录访问！")
                print(deviceID)
                print(userIP)
                returndata = {"result": "FAIL",
                              "description": "IP不合法, 请检查IP地址"}
                msg += ' ERROR: 节点' + '"' + deviceID + '"' + '登录失败---IP不合法, 请检查IP地址\n'
        except:
            print('解析出错---接收节点登录信息')
            returndata = {"result": "FAIL", "description": "解析错误"}
            msg += ' ERROR: ' + '登录失败---接收节点登录信息,解析出错\n'
        # finally:
        #     text_create(msg)
        return jsonify(returndata)

# 2.接收节点退出登录消息接口
@app.route("/ExitData", methods=['POST'])
def ExitDataFun():
    global tokenToCCS, exitdown
    if request.method == 'POST':
        returndata = {"result": "", "description": ""}
        msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                exitdatas = {"deviceID": deviceID}
                print("解析成功---接收节点退出登录信息：%s" % exitdatas)
                returndata = {"result": "OK", "description": ""}
                msg += ' INFOR: 节点' + '"' + deviceID + '"' + ' 已退出登录\n'
                exitdown.append(deviceID)
            else:
                print("已拒绝一次无权限的退出登录访问！")
                returndata = {"result": "FAIL", "description": "您无权限,拒绝访问"}
                msg += ' ERROR: ' + '退出登录失败---无权限, 拒绝访问\n'
        except:
            print('解析出错---接收节点退出登录信息')
            returndata = {"result": "FAIL", "description": "解析错误"}
            msg += ' ERROR: ' + '退出登录失败---接收节点退出登录信息,解析出错\n'
        # finally:
        #     text_create(msg)
        return jsonify(returndata)

# 3.接收节点实时数据接口
@app.route("/ProducedDatas", methods=['POST'])
def ProducedDatasFun():
    global tokenToCCS,intimedatas
    if request.method == 'POST':
        returndata = {"result": "", "description": ""}
        msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                baseInfor = getdata.get('baseInfor')
                infordata = baseInfor.split('}')
                lineData = getdata.get('lineData')
                lineInfor = {
                    "deviceID": deviceID,
                    "baseInfor":
                        {
                            "MO_NUMBER": infordata[0],
                            "MODEL_NAME": infordata[1],
                            "LINE_NAME": infordata[2],
                            "SCETION_NAME": infordata[3],
                            "GROUP_NAME": infordata[4],
                            "STATION_NAME": infordata[5]
                        },
                    "lineData": lineData}
                print("解析成功---接收节点实时数据：%s" % lineInfor)
                returndata = {"result": "OK", "description": ""}
                intimedatas.append(lineInfor)
            else:
                print("已拒绝一次无权限的发送实时数据访问！")
                returndata = {"result": "FAIL",
                              "description": "发送实时数据无权限, 拒绝访问"}
                msg += ' ERROR: ' + '密钥错误---发送实时数据无权限, 拒绝访问\n'
        except:
            print('解析出错---接收节点实时数据信息')
            returndata = {"result": "FAIL", "description": "解析错误"}
            msg += ' ERROR: ' + '接收实时数据失败---接收节点实时数据信息,解析出错\n'
        # finally:
        #     text_create(msg)
        return jsonify(returndata)

# 4.接收换线结果接口
@app.route("/ChangeLineResult", methods=['POST'])
def ChangeLineResultFun():
    global tokenToCCS,clresultadd
    if request.method == 'POST':
        returndata = {"result": "", "description": ""}
        msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                changeLineResult = getdata.get('changeLineResult')
                description = getdata.get('description')
                clresult = {
                    "deviceID": deviceID,
                    "changeLineResult": changeLineResult,
                    "description": description
                }
                print("解析成功---接收节点换线结果信息：%s" % clresult)
                clresultadd.append(clresult)
                returndata = {"result": "OK", "description": ""}
                msg += ' INFOR: 节点' + '"' + deviceID + '"' + ' 接收换线结果成功\n'
            else:
                print("已拒绝一次无权限的发送换线结果访问！")
                returndata = {"result": "FAIL",
                              "description": "发送换线结果无权限, 拒绝访问"}
                msg += ' ERROR: ' + '密钥错误---发送换线结果无权限, 拒绝访问\n'
        except:
            print('解析出错---接收节点换线结果信息')
            returndata = {"result": "FAIL", "description": "解析错误"}
            msg += ' ERROR: ' + '接收换线结果失败---接收换线结果信息,解析出错\n'
        # finally:
        #     text_create(msg)
        return jsonify(returndata)

# 5.接收心跳信号接口,实时更新节点时间,用于心跳检测
@app.route("/HeartbeatSignal", methods=['POST'])
def HeartbeatSignalFun():
    global tokenToCCS
    if request.method == 'POST':
        returndata = {"result": "", "description": ""}
        msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                heartSignal = getdata.get('heartSignal')
                heartdata = {
                    "deviceID": deviceID,
                    "heartSignal": heartSignal
                }
                print("解析成功---接收节点%s 心跳信号：%s" % (deviceID, heartdata))
                returndata = {"result": "OK", "description": ""}
                # 更新该节点心跳时间，用于心跳检测
                # for i in range(len(loginvalid)):
                #     if loginvalid[i][0] == deviceID:
                #         loginvalid[i][4][0] = round(time.time(), 1)
                ###############################################
                loginvalid[tokenToCCS.index(request.headers.get('token'))][4][0] = round(time.time(), 1)
            else:
                print("已拒绝一次无权限的发送心跳信号访问！")
                returndata = {"result": "FAIL",
                              "description": "发送心跳信号无权限, 拒绝访问"}
                msg += ' ERROR: ' + '密钥错误---发送心跳信号无权限, 拒绝访问\n'
        except:
            print('解析出错---接收节点心跳信号信息')
            returndata = {"result": "FAIL", "description": "解析错误"}
            msg += ' ERROR: ' + '接收心跳信号失败---接收心跳信号信息,解析出错\n'
        # finally:
        #     text_create(msg)
        return jsonify(returndata)

# 6.接收当站设备状态变化接口
@app.route("/StateChange", methods=['POST'])
def StateChangeFun():
    global tokenToCCS, stateadd
    if request.method == 'POST':
        returndata = {"result": "", "description": ""}
        msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                stateChange = getdata.get('stateChange')
                statedata = {
                    "deviceID": deviceID,
                    "stateChange": stateChange
                }
                print("解析成功---接收当站状态变化：%s" % statedata)
                returndata = {"result": "OK", "description": ""}
                stateadd.append(statedata)
            else:
                print("已拒绝一次无权限的发送当站状态变化访问！")
                returndata = {"result": "FAIL",
                              "description": "发送当站状态变化无权限, 拒绝访问"}
                msg += ' ERROR: ' + '密钥错误---发送当站状态变化无权限, 拒绝访问\n'
                # text_create(msg)
        except:
            print('解析出错---接收节点当站状态变化信息')
            returndata = {"result": "FAIL", "description": "解析错误"}
            msg += ' ERROR: ' + '接收当站状态变化失败---接收当站状态变化信息,解析出错\n'
            # text_create(msg)
        return jsonify(returndata)

########## 前端界面请求接口 #############
# 给指定模组发送换线指令
def sendcl(deviceID,cldata,PISERVERURL):
    clresult = 0 # 发送换线指令是否成功，默认没有成功
    # # 发送换线指令
    # deviceIDs = [i[0] for i in loginvalid] # 取出所有已登录的设备ID
    # # 取出换线设备ID 对应的token
    # headers = {"Content-Type": "application/json","token":loginvalid[deviceIDs.index(deviceID)][1]}
    # # 得到换线设备ID的访问IP和端口
    # PISERVERIP = loginvalid[deviceIDs.index(deviceID)][2]+':'+loginvalid[deviceIDs.index(deviceID)][3]
    # # ress = requests.post('http://' + PISERVERIP + '/ChangeLine', data=json.dumps(cldata), headers=headers, timeout=3)
    # ress = requests.post(PISERVERURL, data=json.dumps(cldata), headers=headers, timeout=3)
    try:
        deviceIDs = [i[0] for i in loginvalid] # 取出所有已登录的设备ID
        # 取出换线设备ID 对应的token
        headers = {"Content-Type": "application/json","token":loginvalid[deviceIDs.index(deviceID)][1]}
        # 得到换线设备ID的访问IP和端口
        PISERVERIP = loginvalid[deviceIDs.index(deviceID)][2]+':'+loginvalid[deviceIDs.index(deviceID)][3]
        # ress = requests.post('http://' + PISERVERIP + '/ChangeLine', data=json.dumps(cldata), headers=headers, timeout=3)
        ress = requests.post(PISERVERURL, data=json.dumps(cldata), headers=headers, timeout=3)
    except:
        print('----发送换线指令访问异常，请检查模组PI %s是否开启----'%deviceID)
        clresult = 0
    else:
        print('----发送换线指令到模组PI=%s'%cldata)
        if ress.json()['result'] == 'OK': 
            print("------CCS发送换线指令到模组PI %s成功------"%deviceID)
            clresult = 1
        else:
            print("------CCS发送换线指令到模组PI %s失败,返回内容：%s"%(deviceID, ress.json()['description']))
            clresult = 0
    return clresult

# 给指定模组发送换线指令
def sendkeyin(deviceID,cldata,PISERVERIP):
    clresult = 0 # 发送换线指令是否成功，默认没有成功
    # 发送换线指令
    try:
        deviceIDs = [i[0] for i in loginvalid] # 取出所有已登录的设备ID
        # 取出换线设备ID 对应的token
        headers = {"Content-Type": "application/json","token":loginvalid[deviceIDs.index(deviceID)][1]}
        # 得到换线设备ID的访问IP和端口
        PISERVERIP = loginvalid[deviceIDs.index(deviceID)][2]+':'+loginvalid[deviceIDs.index(deviceID)][3]
        ress = requests.post('http://' + PISERVERIP + '/KeyinDatas', data=json.dumps(cldata), headers=headers, timeout=3)
    except:
        print('----发送换线指令访问异常，请检查模组PI %s是否开启----'%deviceID)
        clresult = 0
    else:
        print('----发送换线指令到模组PI=%s'%cldata)
        if ress.json()['result'] == 'OK': 
            print("------CCS发送换线指令到模组PI %s成功------"%deviceID)
            clresult = 1
        else:
            print("------CCS发送换线指令到模组PI %s失败,返回内容：%s"%(deviceID, ress.json()['description']))
            clresult = 0
    return clresult

# 判断字符串是否时纯数字
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass
 
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False

# 得到用户维护的产线信息excle
def getexcle():
    global exceleimgName
    exceleimgName = []
    excelInstru = []
    excelInstruID = [] # 所有应该连接的设备ID
    try:
        data = xlrd.open_workbook(os.getcwd()+'/doc/产线设备信息.xls')
    except:
        print('---获取本地产线设备信息文件失败---')
    else:
        table = data.sheets()[0]#选定表
        nrows = table.nrows#获取行号
        ncols = table.ncols#获取列号
        for i in range(1, nrows):#第0行为表头
            if table.row_values(i)[5] == 'Y':
                excelInstruID.append(table.row_values(i)[0].strip())
                exceleimgName.append(table.row_values(i)[1].strip())
                excelInstru.append(table.row_values(i))

    return excelInstru,excelInstruID

# 得到节点待机信息
def getModelwait(): 
    global allmonitorData
    instruGridDatas = []
    nowInstruID = [] # 当前联网设备ID
    for i in range(len(allmonitorData)):
        nowInstruID.append(allmonitorData[i]['deviceID'])
    excelInstru, excelInstruID = getexcle()
    # 在xlsx中没有联网的设备ID
    a = [x for x in excelInstruID if x not in nowInstruID]
    # 得到在xlsx中但没有联网的设备信息
    for i in range(len(a)):
        for j in range(len(excelInstru)):
            if a[i] == excelInstru[j][0]:
                c = {}
                c['nowtime'] = datetime.now().strftime('%m-%d %H:%M:%S')
                c['modelID'] = excelInstru[j][0]
                c['modelIP'] = excelInstru[j][2]
                c['line'] = excelInstru[j][3]
                c['station'] = excelInstru[j][4]
                c['remarks'] = '节点已退出登录/掉线！'
                instruGridDatas.append(c)
                break
    return instruGridDatas

# 得到在线信息：在xls的和不在xls的
def getModelonline(): 
    global allmonitorData
    instruGridDatas = []
    nowInstruID = [] # 当前联网设备ID

    for i in range(len(allmonitorData)):
        nowInstruID.append(allmonitorData[i]['deviceID'])
        c = {}
        c['nowtime'] = datetime.now().strftime('%m-%d %H:%M:%S')
        c['modelID'] = allmonitorData[i]['deviceID']
        c['modelIP'] = allmonitorData[i]['oneIP']
        c['line'] = allmonitorData[i]['parameter'][0]['value']
        c['station'] = allmonitorData[i]['parameter'][1]['value']
        c['remarks'] = '节点已登录'
        instruGridDatas.append(c)
    excelInstru, excelInstruID = getexcle()
    # 联网但不在产线设备信息excel里
    b = [x for x in nowInstruID if x not in excelInstruID]
    for j in range(len(instruGridDatas)):
        if instruGridDatas[j]['modelID'] in b:
            instruGridDatas[j]['remarks'] = '已登录但不在产线设备信息里'
    return instruGridDatas

# 渲染PMM3.0界面接口
@app.route("/ccs", methods=['GET'])
def ccs():
    print('##### 进入CCS界面 #####')
    # 渲染PMM3.0界面
    return render_template("index.html")

# 登录验证接口
@app.route("/webloginvaild", methods=['GET'])
def webloginvaild():
    global currentadmin
    if request.method == 'GET':
        vaildresult = 0  # 默认不通过，用户不存在
        getPMM3IP = '127.0.0.1'
        try:
            # 该信息需要传给监控界面使用
            getusername = request.args.get('username')
            getpassword = request.args.get('password')
            # 获取数据库里用户账号和密码
            readdatas = readDB(
                DBpath, "SELECT id,usename,password,permission from webuserlogin")
            for row in readdatas:
                if getusername == str(row[1]):
                    if getpassword == str(row[2]):
                        vaildresult = 1  # 用户和密码正确
                        currentadmin = getusername  # 更新用户名，用于换线记录
                    else:
                        vaildresult = 2  # 用户存在但密码不正确
                    break
            getPMM3IP, vaildresult = getIP(vaildresult)
        except:
            # 读取本地数据库失败/解析出错
            vaildresult = 4  # 验证出错
        else:
            print('登录验证完成！')
        finally:
            msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if vaildresult == 1:
                msg += ' INFOR: 用户' + '"' + getusername + '"' + ' 登录成功\n'
            elif vaildresult == 2:
                msg += ' ERROR: 用户' + '"' + getusername + '"' + ' 密码不正确\n'
            elif vaildresult == 3:
                msg += ' ERROR: ' + '网络错误, 请检查IOT网络\n'
            else:
                msg += ' ERROR:' + ' 登录验证出错, 请检查数据库是否正常\n'
            text_create(msg)
        return jsonify({'code': 200, 'data': {'vaildresult': vaildresult, 'getPMM3IP': getPMM3IP}})

# home级联选择器点击事件接口
@app.route("/instruOptions", methods=['GET', 'POST'])
def instruOptions():
    global loginvalid, InstruOptions
    if request.method == 'GET':
        allSelects = []
        linedatas = []
        instrudatas = []
        for i in range(len(loginvalid)):
            linedatas.append(loginvalid[i][5][2])
            instrudatas.append(loginvalid[i][6])
        linedatas = list(set(linedatas))
        linedatas.sort()
        instrudatas = list(set(instrudatas))
        instrudatas.sort()
        a = ['ALLONLINE', 'LineType','ModelType']
        b = []
        b.append(['ALLONLINE'])
        b.append(linedatas)
        b.append(instrudatas)
        for i in range(len(a)):
            c = {}
            c['value'] = a[i]
            c['label'] = a[i]
            c['children'] = []
            for j in range(len(b[i])):
                d = {}
                d['value'] = b[i][j]
                d['label'] = b[i][j]
                c['children'].append(d)
            allSelects.append(c)
        InstruOptions = allSelects
        return jsonify({'code':200,'data':{'InstruOptions':allSelects}})

# home级联选择器选择事件接口
@app.route("/selectInstru", methods=['GET', 'POST'])
def selectInstru():
    global selectCascadeValue, deviceData, allmonitorData
    if request.method == 'GET':
        selectObject = request.args.get('selectObject') # 筛选类型
        selectName = request.args.get('selectName') # 筛选设备名
        selectCascadeValue = [selectObject, selectName]
        if selectCascadeValue[0] == 'ALLONLINE': # 用户选择ALLONLINE默认为ALL
            deviceData = allmonitorData
        else:
            getdecivedata() # 得到选择器选择的所有节点实时数据
        return jsonify({'code':200,
                        'data':{
                            'deviceData':deviceData, # 设备状态信息
                            } 
                        })

# 用户输入人工站多个不良发送到人工站节点的接口
@app.route("/keyintoms", methods=['GET', 'POST'])
def keyintoms():
    if request.method == 'POST':
        deviceID =  request.args.get('deviceID')
        keyindata =  request.args.get('keyindata')
        # 该信息需要传给监控界面使用
        oneIP = request.args.get('oneIP')
        # 传给节点
        cldata = {'deviceID': deviceID,'KeyinDatas':keyindata}
        print('用户keyin cldata=%s'%cldata)
        clresult = sendcl(deviceID,cldata,'http://' + oneIP + ':5000/KeyinDatas')
        current_state = ''
        if clresult == 1: # 发送成功返回'10'
            current_state = '10'
        return jsonify({'code':200,'data':{"current_state": current_state}})

# 单站换线发送的换线指令接口
@app.route("/changline", methods=['GET', 'POST'])
def changline():
    if request.method == 'POST':
        cldeviceID =  request.args.get('deviceID')
        # 该信息需要传给监控界面使用
        cloneIP = request.args.get('oneIP')
        # 用户需要换的线别
        clline = request.args.get('line')
        # 用户需要换的新机种
        clnewModel_number = request.args.get('newModel_number') # 换线机种
        clnewnumber = ''
        clnewModel = ''
        if is_number(clnewModel_number):
            clnewnumber = clnewModel_number
        else:
            clnewModel = clnewModel_number
        # 传给节点
        cldata = {'deviceID': cldeviceID,'MO_NUMBER': clnewnumber, 'MODEL_NAME':clnewModel}
        clresult = sendcl(cldeviceID,cldata,'http://' + cloneIP + ':5000/ChangeLine') # 发送换线指令到节点
        current_state = ''
        if clresult ==1: # 发送成功返回'10'
            current_state = '10'
        updataclform( cldeviceID, cloneIP, clline, clnewModel_number, current_state )
        return jsonify({'code':200,'data':{"current_state": current_state}})

# 一键换线接口,判断用户输入或扫描的是工单还是机种，再发送到节点
@app.route("/changlinemore", methods=['GET', 'POST'])
def changlinemore():
    if request.method == 'POST':
        clline = request.args.get('line')
        clnewModel_number = request.args.get('newModel_number')
        allIP = json.loads(request.args.get('allIP')) # IP
        alldeviceID = json.loads(request.args.get('alldeviceID')) # 设备ID
        clnewnumber = ''
        clnewModel = ''
        if is_number(clnewModel_number): # 判断用户输入的是工单还是机种
            clnewnumber = clnewModel_number
        else:
            clnewModel = clnewModel_number

        allclrestult = []
        for i in range(len(allIP)):
            a = {}
            a['oneIP'] = allIP[i]['oneIP']
            a['itemIndex'] = allIP[i]['itemIndex']
            # 传给节点
            cldata = {'deviceID': alldeviceID[i]['deviceID'],'MO_NUMBER': clnewnumber, 'MODEL_NAME':clnewModel}
            clresult = sendcl(alldeviceID[i]['deviceID'], cldata, 'http://' + allIP[i]['oneIP'] + ':5000/ChangeLine') # 发送换线指令到节点
            current_state = ''
            if clresult ==1: # 发送成功返回'10'
                current_state = '10'
            a['current_state'] = current_state
            allclrestult.append(a) 
            updataclform( alldeviceID[i]['deviceID'], allIP[i]['oneIP'], clline, clnewModel_number, current_state )  
        return jsonify({'code':200,'data':{"allclrestult": allclrestult}})

# 节点待机详情接口
@app.route("/waitmore", methods=['GET', 'POST'])
def waitmore():
    global waitDatas
    if request.method == 'GET':
        print('---节点待机详情接口')
        try:
            waitGridDatas = getModelwait()
        except:
            print('获取节点待机情况失败')
            waitGridDatas = waitDatas
       
        return jsonify({'code':200,'data':{'waitGridDatas':waitGridDatas}})

# 节点报警详情接口
@app.route("/alarmmore", methods=['GET', 'POST'])
def alarmmore():
    if request.method == 'GET':
        return jsonify({'code':200,'data':{'alarmGridDatas':alarmDatas}})

# 节点在线详情接口
@app.route("/onlinemore", methods=['GET', 'POST'])
def onlinemore():
    global onlineDates
    if request.method == 'GET':
        print('---节点在线详情接口')
        try:
            onlineGridDatas = getModelonline()
        except:
            onlineGridDatas = onlineDates
            print('获取节点在线情况失败')
        return jsonify({'code':200,'data':{'onlineGridDatas':onlineGridDatas}})

# operation界面初始化接口-默认当天所有换线记录
@app.route("/initcl", methods=['GET', 'POST'])
def initcl():
    global selectCascadeValue, allCLdata
    if request.method == 'GET':
        print('---初始化换线记录---')
        selectCLdata = [] # 选择器对应的换线记录
        # getxlsdata(date.today())
        try:
            # 得到当天的换线记录allCLdata
            getxlsdata(date.today())
        except:
            allCLdata = []
            print('---无该日期的xls文件---')
            msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            msg += ' ERROR:' + ' 进入换线记录界面时获取当天换线记录失败\n'
            text_create(msg)
        else:
            if selectCascadeValue[0] == 'ALLONLINE': # 用户选择ALLONLINE默认为ALL
                selectCLdata = allCLdata
            else:
                for i in range(len(allCLdata)):
                    # 如果节点类型与选择器一致或节点线别与选择器一致则进行显示
                    if selectCascadeValue[1] == allCLdata[i]['modelType'] or selectCascadeValue[1] == allCLdata[i]['line']:
                        selectCLdata.append(allCLdata[i])
            
        return jsonify({'code':200,
                        'data':{
                            'selectCascadeValue': selectCascadeValue,
                            'selectArgsName': '当天',
                            'dataList': selectCLdata,
                        }
                    })

# operation级联选择器选择事件接口
@app.route("/selectInstru2", methods=['GET', 'POST'])
def selectInstru2():
    global allCLdata
    if request.method == 'GET':
        print('---筛选换线记录---')
        selectObject = request.args.get('selectObject') # 筛选类型
        selectName = request.args.get('selectName') # 筛选设备名
        selecttimeweb = request.args.get('selecttime') # 选择时间
        selectCLdata = []
        day = date.today() # 当天日期
        now = datetime.now()
        if selecttimeweb == '当天':
            selecttime = day
        elif selecttimeweb == '前1天':
            selecttime = now - timedelta(days=1)
        elif selecttimeweb == '前2天':
            selecttime = now - timedelta(days=2)
        elif selecttimeweb == '前3天':
            selecttime = now - timedelta(days=3)
        elif selecttimeweb == '前4天':
            selecttime = now - timedelta(days=4)
        elif selecttimeweb == '前5天':
            selecttime = now - timedelta(days=5)
        else: 
            selecttime = now - timedelta(days=6)
        try:
            getxlsdata(selecttime) # 获取用户选择的指定日期的换线记录
        except:
            allCLdata = []
            print('---无该日期的xls文件---')
            msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            msg += ' ERROR:' + ' 进入换线记录界面时获取当天换线记录失败\n'
            text_create(msg)
        else:    
            if selectName == 'ALLONLINE': # 用户选择ALLONLINE默认为ALL
                selectCLdata = allCLdata
            else:
                for i in range(len(allCLdata)):
                    # 如果节点类型与选择器一致或节点线别与选择器一致则进行显示
                    if selectName == allCLdata[i]['modelType'] or selectName == allCLdata[i]['line']:
                        selectCLdata.append(allCLdata[i])
       
        return jsonify({'code':200,
                        'data':{
                            'dataList': selectCLdata
                        }
                    })

###################################################
# 监控运维初始数据-直接显示当前数据
def home_init():
    global statsDatas, deviceData, columnBarData, tableDataAbnomal
    sockdatas = {}
    sockdatas = {
        'code': 200,
        'data': {
            'statsDatas': statsDatas,  # 节点统计
            'columnBarData': columnBarData,
            'tableDataAbnomal': tableDataAbnomal,
            'selectCascadeValue':selectCascadeValue,
            'deviceData': deviceData,  # 节点状态
        }
    }
    return sockdatas

# 心跳信号重连时更新实时数据
def connectagine(deviceID):
    global deviceData, loginvalid, allmonitorData, alarmDatas
    # 数据库更新掉线节点的数据
    for i in range(len(deviceData)):
        if deviceData[i]['deviceID'] == deviceID:
            deviceData[i]['status'] = 5
            deviceData[i]['instrutip'] = [{'detail': '节点掉线, 正在重连!'}]
    sockdatas = {}
    sockdatas = {
        'code': 200,
        'data': {
            'deviceData': deviceData,  # 节点状态
        }
    }
    return sockdatas

# 心跳信号检测线程
def heart_task():
    global loginvalid
    while True:
        try:
            for i in range(len(loginvalid)):
                # 说明节点已经超过10S没有发送心跳信号了
                if (round(time.time(), 1)-loginvalid[i][4][0]) > 70:
                    # 进行重连, 3次，约1分钟,若10分钟内节点没有连上认为节点已掉线
                    if loginvalid[i][4][1] < 2:
                        loginvalid[i][4][1] += 1
                        loginvalid[i][4][0] = round(time.time(), 1)
                        sockdatas = connectagine(loginvalid[i][0]) # 更新节点实时数据的状态
                        # 向监控界面发送更新的数据
                        socketio.sleep(0.1)
                        socketio.emit("ccs_status",
                                sockdatas, namespace='/autocl')
                    else:
                        # 掉线需删除登录信息和节点实时数据，需要节点重新登录
                        sockdatas = gettotalstatus_heart(loginvalid[i][0])
                        # 向监控界面发送更新的数据
                        socketio.sleep(0.1)
                        socketio.emit("ccs_total_status",sockdatas, namespace='/autocl')
        except:
            # 可能出现某些ID退出登录但心跳检测线程还在通过上一次的loginvalid长度进行判断
            # 此时会出现超出LIST长度，直接开始新的一轮检测即可
            print('重新对所有在线ID检测心跳信号')

# 检测线程
def nodes_task():
    global loginvalid,loginadd,statsDatas,deviceData,exitdown,tokenToCCS,intimedatas
    global columnBarData,tableDataAbnomal,clresultadd,stateadd
    while True:
        if len(loginadd)>0: # 只要有新节点登录成功更新统计信息和实时数据
            # 更新节点统计数据和实时状态数据
            gettotalstatus_login(loginadd[0])
            # 向监控界面发送更新的数据
            socketio.sleep(0.1)
            sockdatas = {}
            sockdatas = {
                'code': 200,
                'data': {
                    'statsDatas': statsDatas,  # 节点统计
                    'deviceData': deviceData,  # 节点状态
                }
            }
            socketio.emit("ccs_total_status",sockdatas, namespace='/autocl')
            loginadd.pop(0)
        if len(exitdown)>0: # 退出登录更新统计信息和实时数据，删除实时状态数据
            # 删除实时状态数据
            gettotalstatus_exit(exitdown[0])
            # 向监控界面发送更新的数据
            sockdatas = {}
            sockdatas = {
                'code': 200,
                'data': {
                    'statsDatas': statsDatas,  # 节点统计
                    'deviceData': deviceData,  # 节点状态
                }
            }
            socketio.sleep(0.1)
            socketio.emit("ccs_total_status", sockdatas,namespace='/autocl')
            # 退出登录成功，同时删除登录信息
            ALLdeviceID = [i[0] for i in loginvalid]
            loginvalid.pop(ALLdeviceID.index(exitdown[0]))
            tokenToCCS.pop(ALLdeviceID.index(exitdown[0]))
            exitdown.pop(0)
        if len(intimedatas)>0: # 实时数据-更新实时状态数据
            # 更新实时状态数据
            gettotalstatus_newdata(intimedatas[0])
            # 向监控界面发送更新的数据
            sockdatas = {}
            sockdatas = {
                'code': 200,
                'data': {
                    'statsDatas': statsDatas,  # 节点统计
                    'columnBarData': columnBarData,
                    'tableDataAbnomal': tableDataAbnomal,
                    'deviceData': deviceData,  # 节点状态
                }
            }
            socketio.sleep(0.1)
            socketio.emit("ccs_total_abnomal_status",sockdatas, namespace='/autocl')
            intimedatas.pop(0)
        if len(clresultadd)>0: # 换线结果，更新实时状态数据
            # 更新实时状态数据
            gettotalstatus_clresult(clresultadd[0])
            # 向监控界面发送更新的数据
            sockdatas = {}
            sockdatas = {
                'code': 200,
                'data': {
                    'deviceData': deviceData,  # 节点状态
                }
            }
            socketio.sleep(0.1)
            socketio.emit("ccs_status", sockdatas, namespace='/autocl')
            updataclresult(clresultadd[0]) # 将换线结果更新换线记录中
            clresultadd.pop(0)
        if len(stateadd)>0:  # 状态改变，更新实时设备状态
            # 更新实时设备状态
            gettotalstatus_change(stateadd[0])
            # 向监控界面发送更新的数据
            sockdatas = {}
            sockdatas = {
                'code': 200,
                'data': {
                    'deviceData': deviceData,  # 节点状态
                }
            }
            socketio.sleep(0.1)
            socketio.emit("ccs_status", sockdatas,namespace='/autocl')
            stateadd.pop(0)
            

# 监听客户端的连接并向客户端推送新数据
@socketio.on("connect", namespace='/autocl')
def connect():
    initHomeDatas = home_init()
    print("------Socketio connect------")
    socketio.sleep(0.1)
    socketio.emit("ccs_begin_alldata",initHomeDatas, namespace='/autocl')
    
# 监听客户端是否离开或刷新监控界面，离开则需要将标志位变为fasle
@socketio.on("returnData", namespace='/autocl')
def leavemonitor(message):
    print('###########前端接收实时数据后返回 %s' % message['resultflag'])

@socketio.on("error", namespace='/autocl')
def error():
    socketio.emit("error", {'error': 'connecterror'}, namespace='/autocl')
    print("------Socketio connect error!------")

@socketio.on("disconnect", namespace='/autocl')
def disconnect():
    print("------Socketio disconnect!------")

# 后台开启后初始化相关数据-统计数据，异常统计和异常表格
def alldatainit():
    global statsDatas,  columnBarData, tableDataAbnomal, excelInstruID
    try:
        # 节点统计数据
        statsDatas = [{'name': '在线总数', 'value': 0,'tip':'当前所有在线的节点'}, {
            'name': '报警总数', 'value': 0,'tip':'此刻正在报警的节点'}, {'name': '离线总数', 'value': 0,'tip':'此刻所有离线的节点'}]
        excelInstru,excelInstruID = getexcle() # 直接以excel的ID数量为准
        # 初始值默认全部离线，需节点重新登录CCS后才会有在线总数
        statsDatas[2]['value'] = len(list(set(excelInstruID))) 
        # 取出数据库倒数7行数据-异常直方图数据
        c = readDB(
            DBpath, "select * from 'columnBarData'order by dataAxis desc limit 7")
        if len(c)>0: # 数据库有历史数据
            axisx = []  # 直方图横轴
            errory = []  # 直方图纵轴-报警次数
            warny = []  # 直方图纵轴-预警次数
            for i in range(len(c)):
                axisx.append(c[i][0])
                errory.append(c[i][1])
                warny.append(c[i][2])
            # 数据库取出的数据是从最后一行开始的，故要进行倒序
            axisx.reverse()
            errory.reverse()
            warny.reverse()
            columnBarData = {
                'dataAxis': axisx,
                'dataserror': errory,
                'dataswarn': warny,
            }
        else: # 数据库无历史数据
            columnBarData = {
                'dataAxis': [time.strftime("%m/%d", time.localtime())],
                'dataserror': [0],
                'dataswarn': [0],
            }
        # 取出数据库的异常表倒数50行数据-异常详情数据
        c = readDB(DBpath, "select * from 'tableDataAbnomal'order by date desc limit 100")
        tableDataAbnomal = []  # 异常表格显示当天异常信息
        for i in range(len(c)):
            # 只显示当天异常信息
            if c[i][0].split(' ')[0] == datetime.now().strftime('%Y-%m-%d'):
                d = {}
                d['date'] = c[i][0]
                d['modelName'] = c[i][1]
                d['cause'] = c[i][2]
                tableDataAbnomal.append(d)
    except:
        msg = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg += ' ERROR: ' + ' 初始化全局变量失败\n'
        text_create(msg)
    else:
        print('初始化全局变量成功')

def begin():
    # 前端用户信息
    creatDB(DBpath, "CREATE TABLE IF NOT EXISTS webuserlogin(id,usename,password,permission)")
    # 节点登录信息
    # creatDB(DBpath, "CREATE TABLE IF NOT EXISTS nodelogin(deviceID,tokenUser,userIP,userPort,loginstatus)")  
    # 异常统计数据
    creatDB(DBpath, "CREATE TABLE IF NOT EXISTS columnBarData(dataAxis,dataserror,dataswarn)")
    # 异常历史数据
    creatDB(DBpath, "CREATE TABLE IF NOT EXISTS tableDataAbnomal(date,modelName,cause)")
    alldatainit() # 初始化全局变量
    # 节点心跳检测线程
    heart_thread = threading.Thread(target=heart_task)
    heart_thread.start()
    nodes_thread = threading.Thread(target=nodes_task)
    nodes_thread.start()
    app.config['JSON_AS_ASCII'] = False
    app.run('0.0.0.0', 5001, debug=False)
    # socketio.run(app, host='0.0.0.0', port='5001',debug=False)
