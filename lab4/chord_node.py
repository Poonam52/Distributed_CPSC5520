import pickle
import hashlib
import threading
import socket
import sys
from threading import Thread, Lock
from datetime import datetime

M = 7
NODES = 2**M
BUF_SZ = 1024


class ChordNode(object):
    def __init__(self,Proto_Manager, node):
        self.node = node
        self.finger = [None] + [FingerEntry(self.node, k) for k in range(1, M+1)]  # indexing starts at 1
        self.size = len(self.finger)
        self.predecessor = None
        self.keys = {}
        self.server = None
        self.protocol = Proto_Manager
        
    """ node n joins the network
        remoteAddress is an arbitary node already in the network"""   
    def join(self, buddy):
        
        if buddy:              
            self.init_finger_table(buddy) 
            self.update_others()          
        else:
            for i in range(1, M+1): 
                 self.finger[i].node = self.node  # fot the node-0
            self.predecessor = self.node
            self.setSuccessor(self.node)
            
        self.display_finger()
        log_success("Node: " + self.node.__str__() + " with successor: " + str(self.finger[1].node) + " with predecessor: " + self.predecessor.__str__()) 
        log_success(self.node.__str__() + " joined.")
        
    def display_finger(self):
        for i in range(1, M+1):
            log_client("finger table of " + str(i) + " for " + str(self.finger[i].start) + " finger node is: " + str(self.finger[i].node))
        
    def call(self, node, func, param= None, param2= None): 
        log_server("rpc call to node: "   + ' %s' % node  + " usng func: "+ ' %s' %  func +  " with param " + ' %s' % param + " and "+ ' %s' % param2)
        
        if node != self.node:
            return self.protocol.call(node, func, param, param2)

        if func == 'update_finger_table' or func == 'add_key' or func == 'set_key':
                return getattr(self, func)(param, param2) 
            
        if param != None:           
            return getattr(self, func)(param) 
        else:
            return getattr(self, func)() 
        
    """initiate finger table of local node
        arbitraryNode is an arbitary node already in the network"""   
    def init_finger_table(self, arbitraryNode):
        

        self.finger[1].node = self.call(arbitraryNode, 'find_successor', self.finger[1].start)
        self.predecessor =  self.call(self.successor(), 'get_predecessor') 
        self.call(self.successor(), 'set_predecessor',self.node) 

        for i in range(1, M):
                if self.finger[i+1].start in ModRange(self.node, self.finger[i].node, NODES):
                     self.finger[i+1].node = self.finger[i].node
                else:
                    self.finger[i+1].node =  self.call(arbitraryNode, 'find_successor', self.finger[i+1].start)  
                
    def setSuccessor(self, id_):
        self.finger[1].node = id_

    """returns the first remote node object."""   
    def successor(self):
        
        return self.finger[1].node
    
    """return the predecessor of the node"""
    def get_predecessor(self):
        return self.predecessor
    
    def set_predecessor(self, id_):
        self.predecessor = int(id_)

    def find_successor(self, id_):
        np = self.find_predecessor(int(id_))
        return self.call(int(np), 'successor')

            
    def find_predecessor(self, id_):        
        node = self.node
        while int(id_) not in ModRange(int(node)+1, int(self.call(int(node), 'successor')) +1, NODES):  
            node = self.call(node, 'closest_preceding_finger', int(id_))    
        return node
    
    def closest_preceding_finger(self, id_):        
        for i in reversed(range(1, M+1)):
            if (int(self.finger[i].node) in ModRange(int(self.node)+1, int(id_) , NODES)):
                return self.finger[i].node
        return self.node

    """ Update all  nodes who have this node in their finger tables """   
    def update_others(self):
        for i in range(1, M+1):
            p = self.find_predecessor((1 + self.node - 2**(i-1) + NODES) % NODES)
            self.call(p, 'update_finger_table', int(self.node), i)
   
    """ if s is i-th finger of n, update this node's finger table with s"""
    def update_finger_table(self, s, i):
        
        i = int(i)
        s = int(s)
        
        if (int(self.finger[i].start) != int(self.finger[i].node)
                 and s in ModRange(int(self.finger[i].start), int(self.finger[i].node), NODES)):
            
            log_client('update_finger_table({},{}): {}[{}] = {} since {} in [{},{})'.format(
                     s, i, self.node, i, s, s, self.finger[i].start, self.finger[i].node))
            
            self.finger[i].node = s
             # get first node preceding myself
            p = self.predecessor 
            self.display_finger()
            self.call(p, 'update_finger_table', s, i)
            return str(self)
        else:
            return 'did nothing {}'.format(self)     
    
    def set_key(self,key,value):
        value = {key:value}  
        self.keys.update(value)
        log_success("key : " + key +  " is added to node: ", self.node)
    
    def add_key(self,key,value):
        successor_node = self.find_successor(key)
        self.call(successor_node, 'set_key', key, value)
        
    def search_key(self,key):
            
        if int(key) > int(NODES):
            return "not found"
            
        successor_node = self.find_successor(key)
        return self.call(successor_node, 'get_value', key)
     
    def get_value(self,input_key):
        for key, value in self.keys.items():
            if key == input_key:
                return value
        return "not found"
                

class Dispatcher(object):
    def __init__(self,protocol, chord_node):
        self.chord_node = chord_node
           
    def dispatch_rpc(self,method,arg):
        if method == 'add_key' or method == 'set_key':
            args = arg.split('#')
            return getattr(self.chord_node, method)(args[0],args[1])
        
        if arg != 'None':
            if method == 'update_finger_table':
                args = arg.split()
                return getattr(self.chord_node, method)(args[0],args[1])
            else:               
                return getattr(self.chord_node, method)(arg)
        else:
            return getattr(self.chord_node, method)()


class NodeDataServer(Thread):
     def __init__(self, protocol, dispatcher, localAddress):
        Thread.__init__(self)
        self.localAddress = localAddress
        self.protocol = protocol
        self.dispatcher = dispatcher

     def run(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ip_port = self.localAddress.split('/')
        self._socket.bind((ip_port[0], int(ip_port[1])))
        self._socket.listen(10)
        log_server("server listen on ip: ", ip_port)
        
        while True:
            try:
                client, client_addr = self._socket.accept()
                threading.Thread(target=self.handle_rpc, args=(client,)).start()
            except socket.error:
                log_fail("accept failed")
                
     def handle_rpc(self,client): 
            request = self.protocol.recv(client)
            msg = request.split()
            method = msg[0] 
            args = request[len(method) + 1:] 
            result = self.dispatcher.dispatch_rpc(method, args)
            self.protocol.send(client,result)  

class Proto_Manager(object): 
    def __init__(self):
        self.host = "127.0.0.1"
        self.ports = range( 3500, 3550)
        self.blockedPorts =[]
        self.node_map = []
        self.ip_hash()
    
    def call(self, node, func, param= None, param2 = None):       
        client = self.open_connection(node)
        if param2:
            if func == 'set_key':
                self.send(client, func + ' %s' % param + '#' + param2) 
            else:
                self.send(client, func + ' %s' % param + ' %s' % param2) 
        else:
            self.send(client, func + ' %s' % param)
        response = self.recv(client)
        self.close_connection(client) 
        return response
    
    """Open socket Connection"""
    def open_connection(self,node):
        address_ip , address_port = self.getAddress(node)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((address_ip, address_port))
        return self._socket 

    """get Address port and ip"""
    def getAddress(self,node):
        ipi_port = self.lookup_node(node)
        ip_port = ipi_port.split('/')
        address_ip = ip_port[0]
        address_port = int(ip_port[1])
        return address_ip, address_port

    def close_connection(self,client):
        client.close()
        client= None
        
    def send(self, client, msg):
         client.sendall(pickle.dumps(msg))

    def ip_hash(self):
        for key in self.ports:
            key = self.host + "/" + str(key)
            p = pickle.dumps(key)
            marshalled_hash = hashlib.sha1(p).digest()
            n = int.from_bytes(marshalled_hash, byteorder='big') % 101
            if self.lookup_node(n):
                self.blockedPorts.append(n)                    
            self.node_map.append([n,key])

    def recv(self,client):
        result = ""
        while True:
            recv_data = client.recv(9999)
            if recv_data:
                response = pickle.loads(recv_data) 
                return response
        return result
 
    def lookup_node(self,n):
        for node, ip in self.node_map:
            if int(n) == int(node):
                return ip
        
                
    def lookup_key(self,key):
        for node, ip in self.node_map:
            if ip == key:
                return node
            
    def getAvailablePort(self):
        for port in self.ports:
           if port in self.blockedPorts :
               pass
           a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
           a_socket.settimeout(1)
           result_of_check = a_socket.connect_ex(("127.0.0.1", port))
           a_socket.close()

           if result_of_check != 0:
               return port

        raise Exception("No port available")       
        
    
class ModRange(object):

    def __init__(self, start, stop, divisor):
        self.divisor = divisor
        self.start = start % self.divisor
        self.stop = int(stop) % int(self.divisor)
        # we want to use ranges to make things speedy, but if it wraps around the 0 node, we have to use two
        if self.start < self.stop:
            self.intervals = (range(self.start, self.stop),)
        elif self.stop == 0:
            self.intervals = (range(self.start, self.divisor),)
        else:
            self.intervals = (range(self.start, self.divisor), range(0, self.stop))

    """ Something like the interval|node charts in the paper """
    def __repr__(self):
         return ''.format(self.start, self.stop, self.divisor)

    """ check given id between this finger's interval? """
    def __contains__(self, id):
        for interval in self.intervals:
            if id in interval:
                return True
        return False

    def __len__(self):
        total = 0
        for interval in self.intervals:
            total += len(interval)
        return total

    def __iter__(self):
        return ModRangeIter(self, 0, -1)

class FingerEntry(object):
    
    def __init__(self, n, k, node=None):
        if not (0 <= n < NODES and 0 < k <= M):
            raise ValueError('invalid entry values')
        self.start = (n + 2**(k-1)) % NODES
        self.next_start = (n + 2**k) % NODES if k < M else n
        self.interval = ModRange(self.start, self.next_start, NODES)
        self.node = node

    """ Something like the interval|node charts in the paper """
    def __repr__(self):
        return ''.format(self.start, self.next_start, self.node)

    """ Is the given id within this finger's interval? """
    def __contains__(self, id):
        return id in self.interval        

class ModRangeIter(object):
    """ Iterator class for ModRange """
    def __init__(self, mr, i, j):
        self.mr, self.i, self.j = mr, i, j

    def __iter__(self):
        return ModRangeIter(self.mr, self.i, self.j)

    def __next__(self):
        if self.j == len(self.mr.intervals[self.i]) - 1:
            if self.i == len(self.mr.intervals) - 1:
                raise StopIteration()
            else:
                self.i += 1
                self.j = 0
        else:
            self.j += 1
        return self.mr.intervals[self.i][self.j]

    
"""Logs data handled"""
def log_client(*message):
    log_console("CLIENT", message)

def log_server(*message):
    log_console("SERVER", message)

def log_success(*message):
    log_console("SUCCESS", message)

def log_finger_table(*message):
    log_console("ft", message)

def log_fail(*message):
    log_console("FAIL", message)

def log_warn(*message):
    log_console("WARN", message)

def log_console(log_type, *message):
    if (log_type == "SERVER") :
        print("\033[0;35m", datetime.now(), message, "\033[0;00m")
    elif(log_type == "FAIL") :
        print("\033[0;31m",  datetime.now(),message, "\033[0;00m")
    elif(log_type == "WARN") :
        print("\033[0;33m", datetime.now(), message, "\033[0;00m")
    elif (log_type == "SUCCESS") :
        print("\033[0;32m",  datetime.now(),message, "\033[0;00m")
    else :
        print(datetime.now()," ] ",message)

    
if __name__ == "__main__":   
    
    protocol = Proto_Manager()
    remote_address = None
    local_address = "127.0.0.1" + "/" + str(protocol.getAvailablePort())
   
    if sys.argv[1] != 0:  
        remote_address =  "127.0.0.1" + "/" + sys.argv[1]

    node = protocol.lookup_key(local_address)
    lookupbuddy = protocol.lookup_key(remote_address) 
    log_client("Node Address: ", local_address)
    log_client("Node ID: ", node)
    chord_node = ChordNode(protocol,node)
    dispatcher = Dispatcher(protocol, chord_node)
    server = NodeDataServer(protocol, dispatcher, local_address)       
    server.start()
    chord_node.join(lookupbuddy)