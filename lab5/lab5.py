import socket
import time
import hashlib
import struct

peer_port = 8333
peer_address = '67.210.228.203'
HDR_SZ = 24
buffer_size = 1024
magic_value = 0xd9b4bef9
height = 1291 
num_per_itr = 500
total_itr = height / num_per_itr


def compactsize_t(n):
    if n < 252:
        return uint8_t(n)
    if n < 0xffff:
        return uint8_t(0xfd) + uint16_t(n)
    if n < 0xffffffff:
        return uint8_t(0xfe) + uint32_t(n)
    return uint8_t(0xff) + uint64_t(n)


def unmarshal_compactsize(b):
    key = b[0]
    if key == 0xff:
        return b[0:9], unmarshal_uint(b[1:9])
    if key == 0xfe:
        return b[0:5], unmarshal_uint(b[1:5])
    if key == 0xfd:
        return b[0:3], unmarshal_uint(b[1:3])
    return b[0:1], unmarshal_uint(b[0:1])


def bool_t(flag):
    return uint8_t(1 if flag else 0)


def ipv6_from_ipv4(ipv4_str):
    pchIPv4 = bytearray([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff])
    return pchIPv4 + bytearray((int(x) for x in ipv4_str.split('.')))


def ipv6_to_ipv4(ipv6):
    return '.'.join([str(b) for b in ipv6[12:]])


def uint8_t(n):
    return int(n).to_bytes(1, byteorder='little', signed=False)


def uint16_t(n):
    return int(n).to_bytes(2, byteorder='little', signed=False)


def int32_t(n):
    return int(n).to_bytes(4, byteorder='little', signed=True)


def uint32_t(n):
    return int(n).to_bytes(4, byteorder='little', signed=False)


def int64_t(n):
    return int(n).to_bytes(8, byteorder='little', signed=True)


def uint64_t(n):
    return int(n).to_bytes(8, byteorder='little', signed=False)


def unmarshal_int(b):
    return int.from_bytes(b, byteorder='little', signed=True)


def unmarshal_uint(b):
    return int.from_bytes(b, byteorder='little', signed=False)

def my_checksum(payload:bytes):
    if len(payload) == 0:
        return bytes.fromhex('5df6e0e2')
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return checksum 

def hex_littletobig(string):
    result = bytearray.fromhex(string)
    result.reverse
    return ''.join(format(x, '02x') for x in result)

def print_block_msg(b):
    print('BLOCK')
    print('-' * 56)
    prefix = '  '

    version = b[:4]
    prev_header_hash = hex_littletobig(b[4:36].hex())
    merkle_root_hash = hex_littletobig(b[36:68].hex())
    unix_time = b[68:72]
    time_str = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                        time.gmtime(unmarshal_int(unix_time)))
    nbits = hex_littletobig(b[72:76].hex())
    nonce = hex_littletobig(b[76:80].hex())

    print('{}{:80} version {}'.format(prefix, version.hex(),
                                      unmarshal_int(version)))
    print('{}{:80} Previous Hash'.format(prefix, prev_header_hash))
    print('{}{:80} Merkle Root '.format(prefix, merkle_root_hash))
    print('{}{:80} epoch {}'.format(prefix, unix_time.hex(), time_str))
    print('{}{:80} number of bits'.format(prefix, nbits))
    print('{}{:80} nonce'.format(prefix, nonce))

    split = b[80:].split(bytes.fromhex('01000000'))
    key, count = unmarshal_compactsize(split[0])

    print('Trans')
    print('-' * 56)
    print('{}{:80} Transaction Count {}'.format(prefix, key.hex(), count))

def print_inv_msg(b, iteration):
    if iteration == 0 or total_itr - iteration < 2:
        print('INV')
        print('-' * 56)
        print(b[:3].hex(),
              '   (each hash printed in reverse of serialized order for clarity'
              ')   count 500')
    count = 1
    iterationStart = iteration * 500
    numBytes = 36
    remainder = ''
    for i in range(3, len(b), numBytes):
        try:
            block = b[i:i + numBytes].hex()
            starter = block[:8]
            remainder = hex_littletobig(block[8:])
            if iterationStart + count == height:
                print(starter, remainder, 'MSG_BLOCK',
                      'inventory #' + str(iterationStart + count))
                return remainder, True
            if iteration == 0 or total_itr - iteration < 2:
                print(starter, remainder, 'MSG_BLOCK',
                      'inventory #' + str(iterationStart + count))
            count += 1
        except Exception:
            continue
    return remainder, False

def print_message(msg, text=None, iteration=0):
    """
    Report the contents of the given bitcoin message
    :param msg: bitcoin message including header
    :return: message type
    """
    print('\n{}MESSAGE'.format('' if text is None else (text + ' ')))
    print('({}) {}'.format(len(msg),
                           msg[:60].hex() + ('' if len(msg) < 60 else '...')))
    payload = msg[HDR_SZ:]
    command = print_header(msg[:HDR_SZ], my_checksum(payload))

    highest = ''
    found = False

    if command == 'version':
        print_version_msg(payload)
    elif command == 'inv':
        highest, found = print_inv_msg(payload, iteration)
    elif command == 'block':
        print_block_msg(payload)
    return command, highest, found


def print_version_msg(b):
    """
    Report the contents of the given bitcoin version message (sans the header)
    :param payload: version message contents
    """
    # pull out fields
    version, my_services, epoch_time, your_services = b[:4], b[4:12], b[12:20], b[20:28]
    rec_host, rec_port, my_services2, my_host, my_port = b[28:44], b[44:46], b[46:54], b[54:70], b[70:72]
    nonce = b[72:80]
    user_agent_size, uasz = unmarshal_compactsize(b[80:])
    i = 80 + len(user_agent_size)
    user_agent = b[i:i + uasz]
    i += uasz
    start_height, relay = b[i:i + 4], b[i + 4:i + 5]
    extra = b[i + 5:]

    # print report
    prefix = '  '
    print(prefix + 'VERSION')
    print(prefix + '-' * 56)
    prefix *= 2
    print('{}{:32} version {}'.format(prefix, version.hex(), unmarshal_int(version)))
    print('{}{:32} my services'.format(prefix, my_services.hex()))
    time_str = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(unmarshal_int(epoch_time)))
    print('{}{:32} epoch time {}'.format(prefix, epoch_time.hex(), time_str))
    print('{}{:32} your services'.format(prefix, your_services.hex()))
    print('{}{:32} your host {}'.format(prefix, rec_host.hex(), ipv6_to_ipv4(rec_host)))
    print('{}{:32} your port {}'.format(prefix, rec_port.hex(), unmarshal_uint(rec_port)))
    print('{}{:32} my services (again)'.format(prefix, my_services2.hex()))
    print('{}{:32} my host {}'.format(prefix, my_host.hex(), ipv6_to_ipv4(my_host)))
    print('{}{:32} my port {}'.format(prefix, my_port.hex(), unmarshal_uint(my_port)))
    print('{}{:32} nonce'.format(prefix, nonce.hex()))
    print('{}{:32} user agent size {}'.format(prefix, user_agent_size.hex(), uasz))
    print('{}{:32} user agent \'{}\''.format(prefix, user_agent.hex(), str(user_agent, encoding='utf-8')))
    print('{}{:32} start height {}'.format(prefix, start_height.hex(), unmarshal_uint(start_height)))
    print('{}{:32} relay {}'.format(prefix, relay.hex(), bytes(relay) != b'\0'))
    if len(extra) > 0:
        print('{}{:32} EXTRA!!'.format(prefix, extra.hex()))


def print_header(header, expected_cksum=None):
    """
    Report the contents of the given bitcoin message header
    :param header: bitcoin message header (bytes or bytearray)
    :param expected_cksum: the expected checksum for this version message, if known
    :return: message type
    """
    magic, command_hex, payload_size, cksum = header[:4], header[4:16], header[16:20], header[20:]
    command = str(bytearray([b for b in command_hex if b != 0]), encoding='utf-8')
    psz = unmarshal_uint(payload_size)

    if expected_cksum is None:
        verified = ''
    elif expected_cksum == cksum:
        verified = '(verified)'
    else:
        verified = '(WRONG!! ' + expected_cksum.hex() + ')'
    prefix = '  '
    print(prefix + 'HEADER')
    print(prefix + '-' * 56)
    prefix *= 2
    print('{}{:32} magic'.format(prefix, magic.hex()))
    print('{}{:32} command: {}'.format(prefix, command_hex.hex(), command))
    print('{}{:32} payload size: {}'.format(prefix, payload_size.hex(), psz))
    print('{}{:32} checksum {}'.format(prefix, cksum.hex(), verified))
    return command

# ============================

class Lab5(object):
    def __init__(self):
        self.listener, self.my_address = self.start_listener()
    
    @staticmethod
    def start_listener():
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Tcp connection
        listener.bind(('', 0))
        return listener, listener.getsockname()

    def processMessage(self, message, command ='', count=0):
        print_message(message, 'Sending')
        self.listener.send(message)
        received = self.listener.recv(buffer_size)
        processedMessages = self.splitMessage(received)
        check, msg, top, found = '','','',False

        for msg in processedMessages:
            payload = msg[HDR_SZ:]
            checksum = my_checksum(payload)
            header = msg[:HDR_SZ]
            header_msg = header[20:]

            while checksum != header_msg:
                addMessage = self.listener.recv(buffer_size)
                splitMessage = addMessage.hex().partition('f9beb4d9')

                payload += bytes.fromhex(splitMessage[0])
                processedMessages.extend(self.splitMessage(bytes.fromhex(splitMessage[2])))
                checksum = my_checksum(payload)
            check, top, found = print_message(header + payload, 'Received', count)
        
        if command == "getblocks":
            if check != 'inv':
                return self.processMessage(msg, command)

        return top, found

    @staticmethod
    def splitMessage(message):
        """
        Splits the messages which is we  recieve from blockchain network.
        into veracks 
        """
        all_messages = message.hex()
        message_arr = all_messages.split('f9beb4d9')
        parsed_messages  =[]
        for num in range(1, len(message_arr)):
            encoded_message = bytes.fromhex('f9beb4d9' + message_arr[num])
            parsed_messages.append(encoded_message)
        return parsed_messages

    def findBlock(self, top_inv, found):
        count = 1
        while not found:
            getblocks_payload = self.getblocks_payload(False, top_inv)
            getblocks_header = self.create_Header(getblocks_payload, 'getblocks')
            getblocks_message = getblocks_header + getblocks_payload
            top_inv, found = self.processMessage(getblocks_message, 'getblocks', count)

            count +=1
        return top_inv
    
    # Message blocks
    @staticmethod
    def create_Header (payload,command):
        """
        Constructs header for the message block
        """
        magic = bytearray.fromhex('F9BEB4D9')
        command =struct.pack("12s", command.encode())
        length = uint32_t(len(payload))
        checksum = my_checksum(payload)

        msg = magic + command + length + checksum

        return msg

    def createMessage(self, payload, cmd):
        """
        Contructs the message using the payload, magic command and encoding the command to bytes
        """
        magic = bytes.fromhex("F9BEB4D9")
        command = cmd + (5 * "\00")
        length = uint32_t(len(payload))
        check = my_checksum(payload)
        msg = magic + bytes(command.encode()) + length + check + payload
        return msg

    def getblocks_payload(self, genesis, top=''):
        version = int32_t(70015)
        count = compactsize_t(1)

        if genesis:
            blockhead_hash = struct.pack("32s", b'\x00')
        else:
            blockhead_hash = bytearray.fromhex(hex_littletobig(top))
        
        hash_end = struct.pack("32s",b'\x00')
        payload = version + count + blockhead_hash + hash_end

        return payload
    
    def getdata_payload(self, block_hash):
        count =  compactsize_t(1)
        verbosity = uint32_t(2)
        block = bytearray.fromhex(hex_littletobig(block_hash))
        payload =  count + verbosity + block
        return payload
        

    def create_version_message(self,peer_address,cmd):
        """
        Function to create a version message. After a header
        """
        version = int32_t(70015)

        services = uint64_t(0)
        timestamp = int64_t(int(time.time()))

        addr_recv_services = uint64_t(1) #services
        addr_recv_ip = ipv6_from_ipv4(peer_address)
        addr_recv_port = uint16_t(8333)

        addr_trans_services = uint64_t(0) #services
        addr_trans_ip = ipv6_from_ipv4(self.my_address[0])
        addr_trans_port = uint16_t(self.my_address[1])

        nonce = uint64_t(0)
        user_agent_bytes = compactsize_t(0)
        starting_height = int32_t(0)
        relay = bool_t(False)

        payload = version + services + timestamp + addr_recv_services + addr_recv_ip + addr_recv_port + addr_trans_services\
             + addr_trans_ip + addr_trans_port + nonce + user_agent_bytes + starting_height + relay
        return self.createMessage(payload, cmd)

    def message_verack(self):
        return bytearray.fromhex("f9beb4d976657261636b000000000000000000005df6e0e2")

    

if __name__ == '__main__':
          
    bitcoin_runner = Lab5()

    bitcoin_runner.listener.connect((peer_address, peer_port))

    # get version
    version_message = bitcoin_runner.create_version_message(peer_address,'version')
    bitcoin_runner.processMessage(version_message)

    # get verack
    verack =  bitcoin_runner.message_verack()
    bitcoin_runner.processMessage(verack)

    # getblocks
    getblocks_payload = bitcoin_runner.getblocks_payload(True)
    getblocks_header = bitcoin_runner.create_Header(getblocks_payload, 'getblocks')
    getblocks_message = getblocks_header + getblocks_payload

    top_inv, found = bitcoin_runner.processMessage(getblocks_message, 'getblocks')
    top_inv = bitcoin_runner.findBlock(top_inv, found)

    # getblock that I found in the bitcoin blocks
    getpayload = bitcoin_runner.getdata_payload(top_inv)
    getheader = bitcoin_runner.create_Header(getpayload, 'getdata')
    get_msg = getheader + getpayload
    bitcoin_runner.processMessage(get_msg, 'getdata')

