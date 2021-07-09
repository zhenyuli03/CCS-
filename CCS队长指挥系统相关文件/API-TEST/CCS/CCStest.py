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


headers = {"Content-Type": "application/json"}
secertkey_CCS = 'A558506C036DD29B08EABB1CA2CD0C5C'
loginvalid = []
sendclflag = 0

# MD5加密
def keymd5(src):
    str_md5 = hashlib.md5(src.encode("utf-8")).hexdigest()
    str_md5 = str_md5.upper()
    return str_md5

# 1.接收模组登录接口
@app.route("/LoginData", methods=['POST'])
def LoginDataFun():
    global loginvalid
    if request.method == 'POST':
        returndata = {"result":"","description":""} 
        try:
            getdata = json.loads(request.get_data().decode("utf-8"))
            deviceID = getdata.get('deviceID')
            userIP = getdata.get('userIP')
            userPort = getdata.get('userPort')
            baseInfor = getdata.get('baseInfor')
            infordata = baseInfor.split('}')
            MO_NUMBER = infordata[0]
            MODEL_NAME = infordata[1]
            LINE_NAME = infordata[2]
            SCETION_NAME = infordata[3]
            GROUP_NAME = infordata[4]
            STATION_NAME = infordata[5]
            usedatas = {
                "deviceID":deviceID,
                "userIP":userIP,
                "userPort":userPort,
                "baseInfor":
                    {
                        "MO_NUMBER":MO_NUMBER,
                        "MODEL_NAME":MODEL_NAME,
                        "LINE_NAME":LINE_NAME,
                        "SCETION_NAME":SCETION_NAME,
                        "GROUP_NAME":GROUP_NAME,
                        "STATION_NAME":STATION_NAME
                    }
            }
            print("解析成功---接收模组登录信息：%s"%usedatas)
            tokenUser = keymd5(secertkey_CCS+deviceID+userIP+userPort+baseInfor)
            if tokenUser == request.headers.get('token'):
                print("驗證成功---允許登錄")
                # 取出已登录的设备ID
                deviceIDlogin = [i[0] for i in loginvalid]
                if deviceID in deviceIDlogin: # 新设备已登录
                    returndata = {"result":"FAIL","description":"拒绝本次登录请求,您已登录,如需再次登录请先退出登录!"}
                else:
                    # 保存每个设备ID,对应的token,IP和端口,用于登录验证
                    tokenToCCS = [deviceID, tokenUser, userIP, userPort]
                    # 该设备ID未登录应直接添加
                    loginvalid.append(tokenToCCS)
                    returndata = {"result":"OK","description":""} 
            else:
                print("已拒绝一次无权限的登录访问！")
                returndata = {"result":"FAIL","description":"登录无权限, 拒绝访问"}
        except:
            print('解析出错---接收模组登录信息')
            returndata = {"result":"FAIL","description":"解析错误"}
        
        return jsonify(returndata)

# 2.接收模组退出登录消息接口
@app.route("/ExitData", methods=['POST'])
def ExitDataFun():
    global loginvalid
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        tokenToCCS = [i[1] for i in loginvalid]
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                exitdatas = {"deviceID":deviceID}
                print("解析成功---接收模组退出登录信息：%s"%exitdatas)
                returndata = {"result":"OK","description":""} 
                # 退出登录成功，同时删除登录信息
                loginvalid.pop(tokenToCCS.index(request.headers.get('token')))
            else:
                print("已拒绝一次无权限的退出登录访问！")
                returndata = {"result":"FAIL","description":"您无权限, 拒绝访问"}
        except:
            print('解析出错---接收模组退出登录信息')
            returndata = {"result":"FAIL","description":"解析错误"}
            
        return jsonify(returndata) 
            
# 3.接收模组实时数据接口
@app.route("/ProducedDatas", methods=['POST'])
def ProducedDatasFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        tokenToCCS = [i[1] for i in loginvalid]
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                baseInfor = getdata.get('baseInfor')
                infordata = baseInfor.split('}')
                MO_NUMBER = infordata[0]
                MODEL_NAME = infordata[1]
                LINE_NAME = infordata[2]
                SCETION_NAME = infordata[3]
                GROUP_NAME = infordata[4]
                STATION_NAME = infordata[5]
                lineData = getdata.get('lineData')
                lineInfor = {
                    "deviceID":deviceID,
                    "baseInfor":
                        {
                            "MO_NUMBER":MO_NUMBER,
                            "MODEL_NAME":MODEL_NAME,
                            "LINE_NAME":LINE_NAME,
                            "SCETION_NAME":SCETION_NAME,
                            "GROUP_NAME":GROUP_NAME,
                            "STATION_NAME":STATION_NAME
                        },
                    "lineData":lineData }
                print("解析成功---接收模组实时数据：%s"%lineInfor)
                returndata = {"result":"OK","description":""} 
            else:
                print("已拒绝一次无权限的发送实时数据访问！")
                returndata = {"result":"FAIL","description":"发送实时数据无权限, 拒绝访问"}
        except:
            print('解析出错---接收模组实时数据信息')
            returndata = {"result":"FAIL","description":"解析错误"}
        
        return jsonify(returndata)

# 4.接收换线结果接口
@app.route("/ChangeLineResult", methods=['POST'])
def ChangeLineResultFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        tokenToCCS = [i[1] for i in loginvalid]
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                changeLineResult = getdata.get('changeLineResult')
                description = getdata.get('description')
                clresult = {
                    "deviceID":deviceID,
                    "changeLineResult":changeLineResult,
                    "description":description
                    }
                print("解析成功---接收模组换线结果信息：%s"%clresult)
                returndata = {"result":"OK","description":""} 
            else:
                print("已拒绝一次无权限的发送换线结果访问！")
                returndata = {"result":"FAIL","description":"发送换线结果无权限, 拒绝访问"}
        except:
            print('解析出错---接收模组换线结果信息')
            returndata = {"result":"FAIL","description":"解析错误"}
        
        return jsonify(returndata)

# 5.接收心跳信号接口
@app.route("/HeartbeatSignal", methods=['POST'])
def HeartbeatSignalFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        tokenToCCS = [i[1] for i in loginvalid]
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                heartSignal = getdata.get('heartSignal')
                heartdata = {
                "deviceID":deviceID,
                "heartSignal":heartSignal
                }
                print("解析成功---接收模组%s 心跳信号：%s"%(deviceID, heartdata))
                returndata = {"result":"OK","description":""} 
            else:
                print("已拒绝一次无权限的发送心跳信号访问！")
                returndata = {"result":"FAIL","description":"发送心跳信号无权限, 拒绝访问"}
        except:
            print('解析出错---接收模组心跳信号信息')
            returndata = {"result":"FAIL","description":"解析错误"}
        
        return jsonify(returndata)

# 6.接收当站状态变化接口
@app.route("/StateChange", methods=['POST'])
def StateChangeFun():
    global sendclflag
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        tokenToCCS = [i[1] for i in loginvalid]
        try:
            if request.headers.get('token') in tokenToCCS:
                getdata = json.loads(request.get_data().decode("utf-8"))
                deviceID = getdata.get('deviceID')
                stateChange = getdata.get('stateChange')
                statedata = {
                    "deviceID":deviceID,
                    "stateChange":stateChange
                }
                print("解析成功---接收当站状态变化：%s"%statedata)
                returndata = {"result":"OK","description":""}
            else:
                print("已拒绝一次无权限的发送当站状态变化访问！")
                returndata = {"result":"FAIL","description":"发送当站状态变化无权限, 拒绝访问"}
        except:
            print('解析出错---接收模组当站状态变化信息')
            returndata = {"result":"FAIL","description":"解析错误"}
        else:
            sendclflag = 1
        return jsonify(returndata)

# 给指定模组发送换线指令
def sendcl(deviceID):
    # 发送换线指令
    try:
        deviceIDs = [i[0] for i in loginvalid] # 取出所有已登录的设备ID
        # 取出换线设备ID 对应的token
        headers = {"Content-Type": "application/json","token":loginvalid[deviceIDs.index(deviceID)][1]}
        # 得到换线设备ID的访问IP和端口
        PISERVERIP = loginvalid[deviceIDs.index(deviceID)][2]+':'+loginvalid[deviceIDs.index(deviceID)][3]
        cldata = {
                    "deviceID":deviceID,
                    "MO_NUMBER":'3333333',
                    "MODEL_NAME":'22222'
                }
        print('headers=%s'%headers)
        print('PISERVERIP=%s'%PISERVERIP)
        ress = requests.post('http://' + PISERVERIP + '/ChangeLine', data=json.dumps(cldata), headers=headers, timeout=3)
    except:
        print('----发送换线指令访问异常，请检查模组PI %s是否开启----'%deviceID)
    else:
        print('----发送换线指令到模组PI=%s'%cldata)
        if ress.json()['result'] == 'OK': 
            print("------CCS发送换线指令到模组PI %s成功------"%deviceID)
        else:
            print("------CCS发送换线指令到模组PI %s失败,返回内容：%s"%(deviceID, ress.json()['description']))

def background_task():
    global sendclflag
  
    while 1:
        time.sleep(5)
        if sendclflag == 1:
            if loginvalid!=[]:
                sendcl(loginvalid[0][0])
                sendclflag = 0
       
clinet_thread = threading.Thread(target=background_task)
clinet_thread.start()

app.config['JSON_AS_ASCII'] = False
app.run('0.0.0.0', 5001, debug=False)

