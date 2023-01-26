import sys
import csv
import pickle
import hashlib
import socket
from threading import Thread, Lock

class ChordPopulate(object):
    def __init__(self):
        self.value_map={}       

    """marshaling hash keys """
    def key_hash(self,key):
        p = pickle.dumps(key)
        marshalled_hash = hashlib.sha1(p).digest() # SHA-1 will give you 160-bit identifiers
        n = int.from_bytes(marshalled_hash, byteorder='big')
        n %= 101 #modulo  to pare it down.  
        return n


    # open csv file and read and data
    def open(self,fileName):
        with open(fileName, newline='') as csvfile:
            reader = csv.DictReader(csvfile) 
            # Csv file data header
            other_headers = ['Name','Position','Team','Games Played','Passes Attempted','Passes Completed','Completion Percentage',
                              'Pass Attempts Per Game',	'Passing Yards','Passing Yards Per Attempt',
                              'Passing Yards Per Game'	,'TD Passes','Percentage of TDs per Attempts','Ints',
                              'Int Rate' ,'Longest Pass',	'Passes Longer than 20 Yards','Passes Longer than 40 Yards',
                              'Sacks',	'Sacked Yards Lost','Passer Rating']
            for row in reader:
                hashed_key = self.key_hash(row['Player Id'] + row['Year']) #create hash key using playerID and year
                directory = {}
                for name in other_headers:
                    directory[name] = row[name]
               
                self.value_map[hashed_key] = directory
        return self.value_map
        
                
 
class Server_call(Thread):
     def __init__(self, remote_address,keys):
        Thread.__init__(self)
        self.remote_address = remote_address
        self.keys = keys
     """Connect with server and send key and value """ 
     def run(self):
            for key, value in self.keys.items():
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                ip_port = self.remote_address.split('/')
                print("ip Address: ", ip_port)
                self._socket.connect((ip_port[0], int(ip_port[1])))
                print("key :", key)
                print("value :", value)                                  
                self.send(self._socket, str(key) + '#' + str(value))
                self.recv(self._socket)
                self.close_connection(self._socket)
        
        
     def send(self, client, msg):
        client.sendall(pickle.dumps('add_key ' + ' %s' % msg))

     def close_connection(self,client):
        client.close()
        client= None
     """receive data handled in response""" 
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
        print("Usage: python3 chord_populate.py PORT FILENAME")
        exit(1)
    
    remote_address = "127.0.0.1" + "/" + sys.argv[1]
    file_name = sys.argv[2]
    
    populate = ChordPopulate() 
    data = populate.open(file_name)

    server = Server_call(remote_address,data)      
    server.start()