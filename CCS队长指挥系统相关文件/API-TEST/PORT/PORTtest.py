from flask import Flask, request, render_template, redirect, url_for
from flask.json import jsonify
from flask_socketio import SocketIO, emit
from flask_cors import *
import requests
import configparser
import json
import importlib
import threading
import time
import hashlib

# 创建Flask类的实例
app = Flask(__name__)
CORS(app, supports_credentials=True,resources=r'/*')
socketio = SocketIO(app,cors_allowed_origins='*')
# 客户端线程
clinet_thread = None
headers = {"Content-Type": "application/json"}

PISERVERIP = '127.0.0.1:5001'


# 接收换线指令接口
@app.route("/ChangeLine", methods=['POST'])
def ChangeLineFun():
    if request.method == 'POST': 
        returndata = {"result":"","description":""}
        try:
            getdata = json.loads(request.get_data().decode("utf-8"))
            deviceID = getdata.get('deviceID')
            MO_NUMBER = getdata.get('MO_NUMBER')
            MODEL_NAME = getdata.get('MODEL_NAME')
            cldata = {
                "deviceID":deviceID,
                "MO_NUMBER":MO_NUMBER,
                "MODEL_NAME":MODEL_NAME
            }
            print("解析成功---接收模组发送的换线指令：%s"%cldata)
            returndata = {"result":"OK","description":""} 
        except:
            print('解析出错---接收模组发送的换线指令：%s'%getdata)
            returndata = {"result":"FAIL","description":"解析错误"}
        
        return jsonify(returndata)

tokenToPORT = '' # 对端的token
secertkey_PORT = 'A558506C036DD29B08EABB1CA2CD0C5C'

# MD5加密
def keymd5(src):
    str_md5 = hashlib.md5(src.encode("utf-8")).hexdigest()
    str_md5 = str_md5.upper()
    return str_md5

userIP = "127.0.0.1"
userPort = "5002"
baseInfor = "20210415}DPS-400AB 31}S01}焊锡}焊锡}第二次焊锡站}"
deviceID = ''
# 计算token
tokenToPORT = keymd5(secertkey_PORT+userIP+userPort+baseInfor)
# 更新头部      
headers = {"Content-Type": "application/json","token":tokenToPORT}
try:
    logindata = {
                "userIP":userIP,
                "userPort":userPort,
                "baseInfor":baseInfor
                }
    ress = requests.post('http://' + PISERVERIP + '/UserLogin', data=json.dumps(logindata), headers=headers, timeout=3)
except:
    print('----登录访问异常，请检查PI服务器是否开启----')
else:
    print('----发送登录数据=%s'%logindata)
    if ress.json()['result'] == 'OK': 
        deviceID = ress.json()['description']
        print("------端发送登录数据到PI成功------token=%s"%tokenToPORT)
    else:
        print("------端发送登录数据到PI失败,返回内容：%s"%ress.json()['description'])


# try:
#     exitdatas = {"deviceID":deviceID}
#     ress = requests.post('http://' + PISERVERIP + '/UserExit', data=json.dumps(exitdatas), headers=headers, timeout=3)
# except:
#     print('----退出登录访问异常，请检查PI服务器是否开启----')
# else:
#     print('----发送退出登录数据=%s'%exitdatas)
#     if ress.json()['result'] == 'OK': 
#         print("------端发送退出数据到PI成功------")
#     else:
#         print("------端发送退出数据到PI失败,返回内容：%s"%ress.json()['description'])

def background_task():
    n = 1
    while n:
        n-=1
        time.sleep(5)
        try:
            heartdata = {"heartSignal":"It's OK"}
            ress = requests.post('http://' + PISERVERIP + '/HeartbeatSignal', data=json.dumps(heartdata), headers=headers, timeout=3)
        except:
            print('----发送心跳数据访问异常，请检查PI服务器是否开启----')
        else:
            print('----发送心跳数据=%s'%heartdata)
            if ress.json()['result'] == 'OK': 
                print("------端发送心跳数据到PI成功------")
            else:
                print("------端发送心跳数据到PI失败,返回内容：%s"%ress.json()['description'])
        time.sleep(5)
        try:
            lineInfor = {
                "baseInfor":baseInfor,
                "lineData":[["123455534", "2012-04-08 11:04:23", "0", "电压-1", "200", "100", "150", "PASS", ""]]
            }
            ress = requests.post('http://' + PISERVERIP + '/ProducedDatas', data=json.dumps(lineInfor), headers=headers, timeout=3)
        except:
            print('----发送实时数据访问异常，请检查PI服务器是否开启----')
        else:
            print('----发送实时数据=%s'%lineInfor)
            if ress.json()['result'] == 'OK': 
                print("------端发送实时数据到PI成功------")
            else:
                print("------端发送实时数据到PI失败,返回内容：%s"%ress.json()['description'])
        time.sleep(5)
        try:
            clresult = {
                "changeLineResult":"OK",
                "description":""
            }
            ress = requests.post('http://' + PISERVERIP + '/ChangeLineResult', data=json.dumps(clresult), headers=headers, timeout=3)
        except:
            print('----发送换线结果访问异常，请检查PI服务器是否开启----')
        else:
            print('----发送换线结果=%s'%clresult)
            if ress.json()['result'] == 'OK': 
                print("------端发送换线结果到PI成功------")
            else:
                print("------端发送换线结果到PI失败,返回内容：%s"%ress.json()['description'])
        

clinet_thread = threading.Thread(target=background_task)
clinet_thread.start()

app.config['JSON_AS_ASCII'] = False
app.run('0.0.0.0', 5002, debug=False)

