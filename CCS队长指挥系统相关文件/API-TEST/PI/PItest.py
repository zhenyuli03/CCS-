from flask import Flask, request, render_template, redirect, url_for
from flask.json import jsonify
from flask_socketio import SocketIO, emit
from flask_cors import *
import requests
import configparser
import json
import importlib
import hashlib
import threading
import time

# 创建Flask类的实例
app = Flask(__name__)
CORS(app, supports_credentials=True,resources=r'/*')
socketio = SocketIO(app,cors_allowed_origins='*')
# 客户端线程
clinet_thread = None
headers = {"Content-Type": "application/json"}

CCSSERVERIP = '127.0.0.1:5000'
deviceID = 'M001'

tokenToPORT = '' # 对端的token
secertkey_PORT = 'A558506C036DD29B08EABB1CA2CD0C5C'
tokenToCCS = '' # 对CCS的token
secertkey_CCS = 'A558506C036DD29B08EABB1CA2CD0C5C'

PORTSERVERIP = ''

# MD5加密
def keymd5(src):
    str_md5 = hashlib.md5(src.encode("utf-8")).hexdigest()
    str_md5 = str_md5.upper()
    return str_md5

# 1.接收端登录接口
@app.route("/UserLogin", methods=['POST'])
def UserLoginFun():
    global tokenToPORT, PORTSERVERIP
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        try:
            getdata = json.loads(request.get_data().decode("utf-8"))
            userIP = getdata.get('userIP')
            userPort = getdata.get('userPort')
            baseInfor = getdata.get('baseInfor')
            infordata = baseInfor.split('}')
            MO_NUMBER = infordata[0]
            MODEL_NAME = infordata[1]
            LINE_NAME = infordata[2]
            STATION_NAME = infordata[3]
            GROUP_NAME = infordata[4]
            STATION_NAME = infordata[5]
            usedatas = {
                "userIP":userIP,
                "userPort":userPort,
                "baseInfor":
                    {
                        "MO_NUMBER":MO_NUMBER,
                        "MODEL_NAME":MODEL_NAME,
                        "LINE_NAME":LINE_NAME,
                        "STATION_NAME":STATION_NAME,
                        "GROUP_NAME":GROUP_NAME,
                        "STATION_NAME":STATION_NAME
                    },
            }
            print("解析成功---接收端登录信息：%s"%usedatas)
            # 驗證客户端的登录token
            if keymd5(secertkey_PORT+userIP+userPort+baseInfor) == request.headers.get('token'):
                tokenToPORT = keymd5(secertkey_PORT+userIP+userPort+baseInfor)
                returndata = {"result":"OK","description":deviceID} 
                PORTSERVERIP = userIP +':'+ userPort
            else:
                print("已拒绝一次无权限的登录访问！")
                returndata = {"result":"FAIL","description":"登录无权限, 拒绝访问"}
        except:
            print('解析出错---接收端登录信息')
            returndata = {"result":"FAIL","description":"解析错误"}
         
        return jsonify(returndata)

# 2.接收端退出登录消息接口
@app.route("/UserExit", methods=['POST'])
def UserExitFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        try:
            if tokenToPORT == request.headers.get('token'):
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                exitdatas = {"deviceID":deviceID}
                print("解析成功---接收端退出登录信息：%s"%exitdatas)
                returndata = {"result":"OK","description":""}
            else:
                print("已拒绝一次无权限的退出登录访问！")
                returndata = {"result":"FAIL","description":"退出登录无权限, 拒绝访问"}
        except:
            print('解析出错---接收端退出登录信息')
            returndata = {"result":"FAIL","description":"解析错误"}
               
        return jsonify(returndata) 
            
# 3.接收端实时数据接口
@app.route("/ProducedDatas", methods=['POST'])
def ProducedDatasFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        try:
            if tokenToPORT == request.headers.get('token'):
                getdata = json.loads(request.get_data().decode("utf-8"))
                baseInfor = getdata.get('baseInfor')
                infordata = baseInfor.split('}')
                MO_NUMBER = infordata[0]
                MODEL_NAME = infordata[1]
                LINE_NAME = infordata[2]
                SECTION_NAME = infordata[3]
                GROUP_NAME = infordata[4]
                STATION_NAME = infordata[5]
                lineData = getdata.get('lineData')
                lineInfor = {
                    "baseInfor":
                        {
                            "MO_NUMBER":MO_NUMBER,
                            "MODEL_NAME":MODEL_NAME,
                            "LINE_NAME":LINE_NAME,
                            "SECTION_NAME":SECTION_NAME,
                            "GROUP_NAME":GROUP_NAME,
                            "STATION_NAME":STATION_NAME
                        },
                    "lineData": lineData 
                }
                print("解析成功---接收端实时数据：%s"%lineInfor)
                returndata = {"result":"OK","description":""}
            else:
                print("已拒绝一次无权限的发送实时数据访问！")
                returndata = {"result":"FAIL","description":"发送实时数据无权限, 拒绝访问"}
        except:
            print('解析出错---接收端实时数据')
            returndata = {"result":"FAIL","description":"解析错误"}
        
        return jsonify(returndata)

# 4.接收换线结果接口
@app.route("/ChangeLineResult", methods=['POST'])
def ChangeLineResultFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        try:
            if tokenToPORT == request.headers.get('token'):
                getdata = json.loads(request.get_data().decode("utf-8"))
                changeLineResult = getdata.get('changeLineResult')
                description = getdata.get('description')
                clresult = {
                    "changeLineResult":changeLineResult,
                    "description":description
                }
                print("解析成功---接收端换线结果：%s"%clresult)
                returndata = {"result":"OK","description":""} 
            else:
                print("已拒绝一次无权限的发送换线结果访问！")
                returndata = {"result":"FAIL","description":"发送换线结果无权限, 拒绝访问"}
        except:
            print('解析出错---接收端换线结果')
            returndata = {"result":"FAIL","description":"解析错误"}
            
        return jsonify(returndata)

# 接收心跳信号接口
@app.route("/HeartbeatSignal", methods=['POST'])
def HeartbeatSignalFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        try:
            if tokenToPORT == request.headers.get('token'):
                getdata = json.loads(request.get_data().decode("utf-8"))
                heartSignal = getdata.get('heartSignal')
                heartdata = {"heartSignal":heartSignal}
                print("解析成功---接收端心跳信号：%s"%heartdata)
                returndata = {"result":"OK","description":""} 
            else:
                print("已拒绝一次无权限的心跳信号访问！")
                returndata = {"result":"FAIL","description":"发送心跳信号无权限, 拒绝访问"} 
        except:
            print('解析出错---接收端心跳信号')
            returndata = {"result":"FAIL","description":"解析错误"}
               
        return jsonify(returndata)

def background_task2(cldata):
    headers2 = {"Content-Type": "application/json","token": tokenToPORT}
    # 发送换线指令
    try:
        ress = requests.post('http://' + PORTSERVERIP + '/ChangeLine', data=json.dumps(cldata), headers=headers2, timeout=3)
    except:
        print('----发送换线指令访问异常，请检查端是否开启----')
    else:
        print('----发送换线指令到端=%s'%cldata)
        if ress.json()['result'] == 'OK': 
            print("------模组PI发送换线指令到端成功------")
        else:
            print("------模组PI发送换线指令到端失败,返回内容：%s"% ress.json()['description'])
       

# 接收CCS换线指令接口
@app.route("/ChangeLine", methods=['POST'])
def ChangeLineFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        try:
            if tokenToCCS == request.headers.get('token'):
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                MO_NUMBER = getdata.get('MO_NUMBER')
                MODEL_NAME = getdata.get('MODEL_NAME')
                cldata = {
                    "deviceID":deviceID,
                    "MO_NUMBER":MO_NUMBER,
                    "MODEL_NAME":MODEL_NAME
                }
                print("解析成功---接收CCS换线指令：%s"%cldata)
                returndata = {"result":"OK","description":""}
                clinet_thread2 = threading.Thread(target=background_task2,args=(cldata,))
                clinet_thread2.start()
        except:
            print('解析出错---接收CCS换线指令')
            returndata = {"result":"FAIL","description":"解析错误"}
           
        return jsonify(returndata)


deviceID = "M001"
userIP = "127.0.0.1"
userPort = "5001"
baseInfor = "20210415}DPS-400AB 31}S01}焊锡}焊锡}第二次焊锡站}"
logindata = {
                "deviceID":deviceID,
                "userIP":userIP,
                "userPort":userPort,
                "baseInfor":baseInfor
                }
# 登錄時得到token
tokenToCCS = keymd5(secertkey_CCS+deviceID+userIP+userPort+baseInfor)
headers = {"Content-Type": "application/json","token":tokenToCCS}
try:
    ress = requests.post('http://' + CCSSERVERIP + '/LoginData', data=json.dumps(logindata), headers=headers, timeout=3)
except:
    print('----登录访问异常，请检查CCS服务器是否开启----')
else:
    print('----发送登录数据到CCS=%s'%logindata)
    if ress.json()['result'] == 'OK': 
        print("------PI发送登录数据到CCS成功------")
    else:
        print("------PI发送登录数据到CCS失败,返回内容：%s"%ress.json()['description'])



# print(tokenToCCS)
# try:
#     exitdatas = {"deviceID":deviceID}
#     ress = requests.post('http://' + CCSSERVERIP + '/ExitData', data=json.dumps(exitdatas), headers=headers, timeout=3)
# except:
#     print('----退出登录访问异常，请检查CCS服务器是否开启----')
# else:
#     print('----发送退出登录数据到CCS=%s'%exitdatas)
#     if ress.json()['result'] == 'OK': 
#         print("------PI发送退出数据到CCS成功------")
#     else:
#         print("------PI发送退出数据到CCS失败,返回内容：%s"%ress.json()['description'])

def background_task():
    n = 1
    while n:
        n-=1
        time.sleep(5)
        try:
            heartdata = {
                "deviceID":deviceID,
                "heartSignal":"It's OK"
                }
            ress = requests.post('http://' + CCSSERVERIP + '/HeartbeatSignal', data=json.dumps(heartdata), headers=headers, timeout=3)
        except:
            print('----发送心跳数据访问异常，请检查CCS服务器是否开启----')
        else:
            print('----发送心跳数据=%s'%heartdata)
            if ress.json()['result'] == 'OK': 
                print("------PI发送心跳数据到CCS成功------")
            else:
                print("------PI发送心跳数据到CCS失败,返回内容：%s"%ress.json()['description'])
        time.sleep(5)
        try:
            lineInfor = {
                "deviceID":deviceID,
                "baseInfor":baseInfor,
                "lineData":[["123455534", "2012-04-08 11:04:23", "0", "电压-1", "200", "100", "150", "PASS", ""]]
            }
            ress = requests.post('http://' + CCSSERVERIP + '/ProducedDatas', data=json.dumps(lineInfor), headers=headers, timeout=3)
        except:
            print('----发送实时数据访问异常，请检查CCS服务器是否开启----')
        else:
            print('----发送实时数据到CCS=%s'%lineInfor)
            if ress.json()['result'] == 'OK': 
                print("------PI发送实时数据到CCS成功------")
            else:
                print("------PI发送实时数据到CCS失败,返回内容：%s"%ress.json()['description'])
        time.sleep(5)
        try:
            clresult = {
                "deviceID":deviceID,
                "changeLineResult":"OK",
                "description":""
            }
            ress = requests.post('http://' + CCSSERVERIP + '/ChangeLineResult', data=json.dumps(clresult), headers=headers, timeout=3)
        except:
            print('----发送换线结果访问异常，请检查CCS服务器是否开启----')
        else:
            print('----发送换线结果到CCS=%s'%clresult)
            if ress.json()['result'] == 'OK': 
                print("------PI发送换线结果到CCS成功------")
            else:
                print("------PI发送换线结果到CCS失败,返回内容：%s"%ress.json()['description'])

        time.sleep(5)
        try:
            statechanges = {
                "deviceID":deviceID,
                "stateChange":"waiting",
            }
            ress = requests.post('http://' + CCSSERVERIP + '/StateChange', data=json.dumps(statechanges), headers=headers, timeout=3)
        except:
            print('----发送当站状态变化访问异常，请检查CCS服务器是否开启----')
        else:
            print('----发送当站状态变化到CCS=%s'%statechanges)
            if ress.json()['result'] == 'OK': 
                print("------PI发送当站状态变化到CCS成功------")
            else:
                print("------PI发送当站状态变化到CCS失败,返回内容：%s"%ress.json()['description'])        
        
clinet_thread = threading.Thread(target=background_task)
clinet_thread.start()

app.config['JSON_AS_ASCII'] = False
app.run('0.0.0.0', 5001, debug=False)

