"""
CPSC 5520, Seattle University
:Authors: Poonamben Patel
"""
import pickle
import sys
import  socket
from urllib import response

BUF_SZ = 1024  # receive buffer size

class lab1(object):

    def __init__(self,gcd_host,gcd_port):
        # Assign value to self object for host , port and response
        self.host = gcd_host
        self.port = gcd_port
        self.response = None

    def join_group(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.host, self.port)) #connect to the desire host and port
            data_string = pickle.dumps('JOIN') # serialize the JOIN message
            s.sendall(data_string) # send join message to server
            data = s.recv(BUF_SZ) # receive respnse from GCD server
            self.reponse = pickle.loads(data) # deserialize data and store in response object 
            print(f"JOIN ({self.host}, {self.port})") # Display connected host and port adress
            lab1.meet_member(self)


    def meet_member(self):
        for res in self.reponse:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.settimeout(1.5) # set time out 
                    s.connect((res['host'], res['port']))
                    print(f"HELLO to {res}")
                except ConnectionRefusedError  as e: #exception handling
                    print(f"failed to connect: {e}")
                    continue
                except socket.timeout as ts:
                    print(f"TimeoutError caused and handled ",{ts})
                    continue
                else:
                    data_string = pickle.dumps('HELLO')
                    s.sendall(data_string)
                    data = s.recv(BUF_SZ)
                    result = pickle.loads(data)
                    print('Received from Server: ', repr(result)) # print server response
    

if __name__ == '__main__':
    if len(sys.argv) != 3:
       print('usage: python lab1.py GCDHOST, GCDPORT')
       exit(1)
       
    host = sys.argv[1]
    port = int(sys.argv[2]) 
    lb = lab1(host,port)
    lb.join_group()
   
