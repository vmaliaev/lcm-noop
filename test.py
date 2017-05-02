#!/usr/bin/env python

import requests
from requests.adapters import HTTPAdapter
import json
#import time
#import base64
import urllib2
import logging
#from logging.handlers import RotatingFileHandler
import yaml
import subprocess
import sys
import socket
#import getopt

_DEBUG = 0

class ForemanNodeBunch():
    _noop_mode = "noop_mode"
    _hiera_key = "fuel-plugin-lcm"
    _log_file = "/var/log/foreman_noop_lcm.log"
    _retries = 15
    _session = None
    def __init__(self):
        data = self.hiera_lookup(self._hiera_key)
        self.dnsdomain = socket.gethostname().split('.',1)[1]
#TODO add verification of data
        self.user = data["foreman_user"]
        self.passwd = data["foreman_password"]
        self.url =  "https://"+"puppet."+self.dnsdomain#socket.gethostname().split('.',1)[1]
        self.log = self._log_file
        self.retries = self._retries

        print "iFinish init"

    @staticmethod
    def hiera_lookup(primary_key):
        hiera_command = '''hiera -h {prim_key}'''
        command = hiera_command.format(prim_key = primary_key)
        try:
            _res=subprocess.check_output(command.split(' '))
            response = subprocess.Popen(
                command,
                shell=True,
#                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )

            hash_data = response.stdout.read()
            yaml_data = yaml.load(hash_data.replace('=>',':'))

            return yaml_data
        except subprocess.CalledProcessError as exception:
            logging.warn('Unable to lookup Hiera data: {} ; Code: {} ; Output: {}'.format(command, exception.returncode, exception.output))
            return None
        except OSError as exception:
            logging.error('Non-zero exit: {} \nExit code: {} Output: None'.format(command, exception.errno))
            return None


    def main(self,argv):
        action = argv[0]
#TODO add USAGE
#        if argv[1:]:
#            print argv[1]
        nodes=argv[1:] if argv[1:] else []
        if nodes == ['all'] or nodes == []: 
            nodes=[]
        else:
            nodes = list(set(nodes))
            nodes_temp = list(nodes)
            for elem in nodes_temp:
                if ',' in elem: 
                    nodes.remove(elem)
                    nodes.extend(elem.split(','))  
            nodes = list(set(nodes))
            try:
                nodes.remove(',')
            except ValueError as e:
                pass
            try:
                nodes.remove('')
            except ValueError:
                pass
#        print nodes
        
        for idx, elem in enumerate(nodes):
            if '.' not in elem:
                nodes[idx]=elem+'.'+self.dnsdomain#'.xyz' 
        print nodes
#TODO Add validation check of nodes (use API call and compare)

#        return 0

#TODO check that only host names are in argv list, but not FQDN
#TODO add validation for argv[1:] - check identation/trail spaces
#        print self.list_noop(argv[0])
        operation = {
            'list_noop'    : self.list_noop,
            'enable_noop'  : self.enable_noop,
            'disable_noop' : self.disable_noop,
        } 
#TODO add check of operation
        res_func = operation.get(action,"absent")
        if res_func == "absent" : print action," Wrong argument: must be one of ", operation.keys() 
        else: res_func(nodes)
            
        
        print "Finished main"
        return 0


    @property
    def session(self):
        if _DEBUG: print "FUNCTION:",sys._getframe().f_code.co_name 
        if self._session:
            return self._session
        self._session = requests.Session()
        self._session.auth = (self.user, self.passwd)
        self._session.encoding = 'utf-8'
        self._session.verify = False
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        self._session.mount('https://',HTTPAdapter(max_retries=3))
        return self._session
        
    def send_request(self, session_method, request_url, request_data = None):
        if _DEBUG: print "FUNCTION:",sys._getframe().f_code.co_name
#TODO Add retries here and logging
        total_url = self.url + request_url 
        response = session_method(total_url) if not request_data else session_method(total_url, request_data)
#        print response.json()['results'][0]['url']
        return response

    def list_noop(self,arg=[]):
        print "FUNCTION:",sys._getframe().f_code.co_name
        if arg == []:
            response = self.send_request(self.session.get,'/api/v2/hosts?order=name+ASC')
            if _DEBUG: print "RESPONSE: {}\n BODY: {}".format(response,response.json())#['results'])
            f = open('./api_resp','w') #TODO delete this debug
    #        print >>f, yaml.safe_load(json.dumps(response.json()['results'][1]))#TODO delete this debug
            print >>f, json.dumps(response.json()['results'][1])#TODO delete this debug
            print json.dumps(response.json()['results'][1]["name"]) #TODO delete this debug
            host_list_api = response.json()['results']
            host_list = [] #TODO add if arg is emty for the next block
            for indx in host_list_api:
                host_list.append(indx["name"])
        else:
            host_list = arg

        print host_list
        result_list = []

        for node_name in host_list:
            print node_name
            response = self.send_request(self.session.get, '/api/hosts/{}/parameters'.format(node_name))
            params = response.json()['results']
            if params:
                for indx in params:
                    if indx['name'] == self._noop_mode : result_list.append([node_name,indx['name'],indx['value']])

        if _DEBUG: print sys._getframe(1).f_code.co_name
        if sys._getframe(1).f_code.co_name != "enable_noop":
            if not result_list: print "No nodes have \"{_noop_mode}\" parameter".format(_noop_mode=self._noop_mode)
            for indx in result_list:
                print "{} : {} = {}".format(indx[0],indx[1],indx[2])
        return result_list

    def enable_noop(self, arg):
        print "FUNCTION:",sys._getframe().f_code.co_name
        response = self.send_request(self.session.get,'/api/v2/hosts?order=name+ASC')
        host_list_api = response.json()['results']
        host_list = [] #TODO add if arg is emty for the next block
        for indx in host_list_api:
            host_list.append(indx["name"])

        upd_list = self.list_noop(arg)

        for indx in upd_list:
            host_list.pop(host_list.index(indx[0]))
 
        print host_list
        print upd_list
        for node_name in host_list: 
#            break
            response = self.send_request(self.session.post,'/api/v2/hosts/{}/parameters'.format(node_name),
                request_data = json.dumps(
                    {
                        'parameter':
                            {
                                'name': self._noop_mode,
                                'value': 'true',
                            },
                    }
                ),
            )
#            print node_name
#            print response.json()
            #break

        upd_list_temp = list(upd_list)
        for indx in upd_list_temp:
            if indx[2] == 'true': upd_list.pop(upd_list.index(indx))
            
        for node_name in upd_list:
            response = self.send_request(self.session.put,'/api/v2/hosts/{}/parameters/{}'.format(node_name[0],self._noop_mode),
                request_data = json.dumps(
                    {
                        'value': 'true',
                    }
                ),
            )
#TODO Add noop_list() and return it
        return response

    def disable_noop(self, arg):
        print "FUNCTION:",sys._getframe().f_code.co_name
        upd_list=self.list_noop(arg)

        upd_list_temp = list(upd_list)
        for indx in upd_list_temp:
            if indx[2] != 'true': upd_list.pop(upd_list.index(indx))

        for node_name in upd_list:
            response = self.send_request(self.session.put,'/api/v2/hosts/{}/parameters/{}'.format(node_name[0],self._noop_mode),
                request_data = json.dumps(
                    {
                        'value': 'false',
                    }
                ),
            )
#        print upd_list
        return 0




if __name__ == "__main__":
    node_bunch = ForemanNodeBunch()
    node_bunch.main(sys.argv[1:])
    print "Competed"
#TODO add check of TRUE True true "True" and so on, then FALSE .....
#TODO add USAGE()
