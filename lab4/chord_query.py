import sys
import csv
import pickle
import hashlib
import socket
from threading import Thread, Lock
        
class ChordQuery(Thread):
     def __init__(self, remote_address,key):
        Thread.__init__(self)
        self.remote_address = remote_address
        self.key = key

     """ Seprate remote address and send data to network"""
     def run(self):
 
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ip_port = self.remote_address.split('/')
            self._socket.connect((ip_port[0], int(ip_port[1])))
            print("key:", key)                                 
            self.send(self._socket, key)
            data = self.recv(self._socket)
            print("data: ", data)
            self.close_connection(self._socket)
        
        
     def send(self, client, msg):
        client.sendall(pickle.dumps('search_key ' + ' %s' % msg))

     def close_connection(self,client):
        client.close()
        client= None
        
     def recv(self,client):
        result = ""
        while True:
            recv_data = client.recv(9999)
            if recv_data:
                response = pickle.loads(recv_data) 
                return response
        return result
    
if __name__ == "__main__":    
    if len(sys.argv) != 3: 
        print("Usage: python Chord_query.py PORT KEY")
        exit(1)
    remote_address = "127.0.0.1" + "/" + sys.argv[1]
    key = sys.argv[2]
    server = ChordQuery("127.0.0.1" + "/" + sys.argv[1], sys.argv[2])       
    server.start()