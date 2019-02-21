"""
    Retrieve interfaces status from wired network devices
   
    tested on DNAC1.2.8 python 2.7
    requires a ElasticSearch instance running on the same machine

"""

__author__      = "Jean-Francois Pujol, Cisco Switzerland"
__copyright__   = "free to be re-used as needed; Feb 2018"

import requests
import json
import sys
from time import time, strftime, localtime
import codecs, unicodedata, base64
import elasticsearch
from pprint import pprint

# elasticsearch engine
seServer='localhost'
seIndex='dnac-interfaces'
seType='switches'
dnaServer = 'dnac.rollelab.ch'
baseUrl = 'https://' + dnaServer 

adminUser = 'admin' # user to access API
adminPwd = 'XXXXXX' # plain password

RETURN_OK='200' # found
RETURN_NF='400' # not found
RETURN_ERR='999' # generic error

requests.packages.urllib3.disable_warnings()
    
# timestamp in ms for DNAC (minus 60s)
timeStp = int(time() *1000) - 60000

def is_ascii(s):
    return all(ord(c) < 128 for c in s)

def rm_non_ascii(s):
    return(''.join(i for i in s if ord(i)<128))
    
def to_ascii(msg):
    if msg:
        if ( is_ascii(msg) ):
            return(msg)
        else:
            return(unicodedata.normalize('NFKD',msg).encode('ascii','ignore'))
    else:
        return('')

def utf_decode(raw):
    if ( raw ):
        return(to_ascii(raw.split('\n')[0]))
    else:
        return('')
        
def utf_list_decode(obj):
    if isinstance(obj,(list,)):
        strlist =''
        for item in obj:
            strlist += utf_decode(item) + ','
            
    elif isinstance(obj,(dict,)):
        strlist =''
        for item in obj:
            strlist += utf_decode(item) + ':' + utf_decode(obj[item]) + ','   
    else:
        strlist = utf_decode(obj)
        
    return(strlist)

class outputLog:
    def __init__(self,threshold=0,fname=None):
        self.td = int(threshold)
        self.fname = fname
        self.fh = sys.stdout
        if fname:
            self.file(fname)
        
    def file(self,fname):
        if fname:
            try:
                self.fh = open(fname, 'a')
            except IOError:
                print("Exit(-1). Could not open file " + fname + " for writing.")
                exit(-1)
            self.fname = fname
            
    def level(self,threshold=None):
        if threshold:
            self.td = int(threshold)
        return(self.td)
    
    def write(self,threshold,*messages):
        if threshold > self.td:
            return(False)
        else:
            try:
                self.fh.write(strftime("%m/%d %H:%M:%S", localtime()))
                for message in messages:
                    self.fh.write(' ' + str(message))
                self.fh.write('\n')
            except IOError:
                print("Exit(-1). Could not write message to file " + self.fname )
                exit(-1)
    
    def close(self):
        self.fh.close()

def setHeaders(username,password):
    authString = username + ':' + password
    b64AuthString = base64.b64encode(authString.encode('utf-8'))
    authHeader = 'Basic ' + b64AuthString.decode('utf-8')
    dnaHeader = {'Authorization' : authHeader , 'Content-Type': 'application/json'}
    return (dnaHeader)
    
def getDNAtoken(user,password):
    auth_url = baseUrl + '/dna/system/api/v1/auth/token'
    Headers = setHeaders(user,password)
    result = requests.post(auth_url, data='', headers=Headers, verify=False)
    json_Tok=json.loads(result.text)
    return(to_ascii(json_Tok['Token']))
    
# initialize message logs
log = outputLog(2,'/tmp/DNAgetAllInterfaces.log')

# initialize Elastic search index & server details
es = elasticsearch.Elasticsearch(seServer)

dnaToken = getDNAtoken(adminUser,adminPwd)
Headers = { 'x-auth-token' : dnaToken }

dna_url = baseUrl + '/dna/intent/api/v1/interface'
result = requests.get(dna_url, headers=Headers, verify=False)
json_intfs=json.loads(result.text)

nIntf = 0
for intf in json_intfs['response']:
    if intf['interfaceType'] ==  u'Physical':
        nIntf += 1
        
        portName = to_ascii(intf['portName'])
        series = to_ascii(intf['series'])
        mediaType = to_ascii(intf['mediaType'])
        opStatus = to_ascii(intf['status'])
        admStatus = to_ascii(intf['adminStatus'])
        lastUpdated = to_ascii(intf['adminStatus'])
        serialNo = to_ascii(intf['serialNo'])
        ipv4Addr = to_ascii(intf['ipv4Address'])
        pid = to_ascii(intf['pid'])
        portMode = to_ascii(intf['portMode'])
        
        log.write(2,'-- intf:',serialNo, portName, mediaType, opStatus)
        
        value = { 'portName' : portName, 'series':series, 'mediaType' : mediaType, 'opStatus' : opStatus,
                    'admStatus' : admStatus, 'lastUpdated' : lastUpdated,'serialNo' : serialNo,'ipv4Addr' : ipv4Addr,
                    'pid' : pid, 'portMode': portMode}
        key = nIntf
        try:
            res = es.index(index=seIndex, doc_type=seType, id=key, body=value)  
        except elasticsearch.exceptions.NotFoundError as es1:
            res = {'retcode' : RETURN_ERR, 'value' : None }

        if res['result'] == 'updated' or res['result'] == 'created':
            log.write(3,'[es.index]', key, 'creation. return code:',res['created'])
        else:
            log.write(3,'[es.write]', key,'es.index failed')
        
print('number of wired nodes:',nIntf)
