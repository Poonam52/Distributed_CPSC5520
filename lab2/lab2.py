""" I made this  based on the template.
for check prob un comment the self.probing() method line number 70. """
import random
import socket
import selectors
import pickle
import sys
import time as ts
from enum import Enum
from datetime import datetime

ASSUME_FAILURE_TIMEOUT =1.5 # without response in 1.5 sec assumes peer is sleep
CHECK_INTERVAL = 0.2  # To wait until some registered file objects
BUF_SZ = 1024     # default buffer size for receive socket response             
PEER_DIGITS= 100 #socket size
BACKLOG=100

""" Enumeration of states a peer can be in for the Lab2 class."""
class State(Enum):
    
    QUIESCENT = 'QUIESCENT'  # Erase any memory of this peer
    # Outgoing message is pending
    SEND_ELECTION = 'ELECTION'
    SEND_VICTORY = 'COORDINATOR'
    SEND_OK = 'OK'

    # Incoming message is pending
    WAITING_FOR_OK = 'WAIT_OK'  # When I've sent them an ELECTION message
    WAITING_FOR_VICTOR = 'WHO IS THE WINNER?'  # This one only applies to myself
    WAITING_FOR_ANY_MESSAGE = 'WAITING'  # When I've done an accept on their connect to my server

    def is_incoming(self):
        """Categorization helper."""
        return self not in (State.SEND_ELECTION, State.SEND_VICTORY, State.SEND_OK)


class Lab2(object):
    
    def __init__(self, gcdhost, gcdport, next_birthday, su_id):
        """
        :param hoost: host name 
        :param port : port of the GCD
        :param next_birthday: datetime of next birthday
        :param su_id: SeattleU id number
        """
        self.host = gcdhost
        self.port = int(gcdport)
        days_to_birthday = (next_birthday - datetime.now()).days
        self.pid = (days_to_birthday, int(su_id))
        self.members = {}
        self.states = {}
        self.bully = None  # None means election is pending, otherwise this will be pid of leader
        self.selector = selectors.DefaultSelector()
        self.listener, self.listener_address = self.start_a_server()

    def run(self):
        print('STARTING WORK for pid {} on {}'.format(self.pid, self.listener_address))
        self.join_group()
        self.selector.register(self.listener, selectors.EVENT_READ)
        self.start_election('at startup')
        while True:
            events = self.selector.select(CHECK_INTERVAL)
            for key, mask in events:
                if key.fileobj == self.listener:
                    self.accept_peer()
                elif mask & selectors.EVENT_READ:
                    self.receive_message(key.fileobj)
                else:
                    self.send_message(key.fileobj)
            self.check_timeouts()
            #self.probing()

    """Accept New connections from a peer."""
    def accept_peer(self):
        try:
            peer, _addr = self.listener.accept()  
            print('{}: accepted [{}]'.format(self.pr_sock(peer), self.pr_now()))
            self.set_state(State.WAITING_FOR_ANY_MESSAGE, peer)
        except Exception as err:
            print('accept failed {}'.format(err))

    """" Send the queued message to the given peer based on its current state."""
    def send_message(self, peer):
        """:param peer: socket connected to peer process."""
        state = self.get_state(peer)
        print('{}: sending {} [{}]'.format(self.pr_sock(peer), state.value, self.pr_now()))
        try:
            self.send(peer, state.value, self.members)  
        except ConnectionError as err:
            # a ConnectionError handling for socket close
            print('closing: {}'.format(err))
            self.set_quiescent(peer)
            return
        except Exception as err:
            # exceptions assume are due to being non-blocking
            print('failed {}: {}'.format(err.__class__.__name__, err))
            if self.is_expired(peer):
                # if no avail, then set dead
                print('timed out')
                self.set_quiescent(peer)
            return
        # check to see if we want to wait for response immediately
        if state == State.SEND_ELECTION:
            self.set_state(State.WAITING_FOR_OK, peer, switch_mode=True)
        else:
            self.set_quiescent(peer)

    """ Receive a message from a peer and state transition."""
    def receive_message(self, peer):
        try:
            message_name, theirIdea = self.receive(peer)
            print('{}: received {} [{}]'.format(self.pr_sock(peer), message_name, self.pr_now()))

        except ConnectionError as err:
            # a ConnectionError means it will never succeed
            print('closing: {}'.format(err))
            self.set_quiescent(peer)
            return

        except Exception as err:
            # failed connection handling
            print('failed {}'.format(err))
            if self.is_expired(peer):
                # if no avail, then set dead 
                print('timed out')
                self.set_quiescent(peer)
            return

        self.update_members(theirIdea)  # add new members

        # handle state transition
        if message_name == 'ELECTION':
            self.set_state(State.SEND_OK, peer)
            if not self.is_election_in_progress():
                self.start_election('Got a VOTE card from a lower pid peer')

        elif message_name == 'COORDINATOR':
            # election  over 
            self.set_leader('someone else') 
            self.set_quiescent(peer)
            self.set_quiescent()

        elif message_name == 'OK':
            # if get any ok since starting electionchan then ge to expecting COORDINATOR
            if self.get_state() == State.WAITING_FOR_OK:
                self.set_state(State.WAITING_FOR_VICTOR)  
            self.set_quiescent(peer)

    def check_timeouts(self):
        if self.is_expired(): 
            if self.get_state() == State.WAITING_FOR_OK:
                self.declare_victory('timed out waiting for any OK message')
            else:  # my_state == State.WAITING_FOR_VICTOR:
                self.start_election('timed out waiting for COORDINATION message')

    def get_connection(self, member):
        """Get a socket for given member.
        :param member: process id of peer
        :return: socket or None if failed
        """
        listener = self.members[member]  # look up address to connect to
        peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer.setblocking(False)
        try:
            peer.connect(listener)

        except BlockingIOError:
            pass  # connection still in progress -- will pick it up in select

        except Exception as err:
            print('connection failed: {}'.format(err))
            return None

        return peer

    """Check if currently election is on going .signified by None bully."""
    def is_election_in_progress(self):
        return self.bully is None

    def is_expired(self, peer=None, threshold=ASSUME_FAILURE_TIMEOUT):
        """"
        :param peer: socket connected to another peer process
        :param threshold: waiting time since last state transition
        :return: if elapsed time is past threshold return True,  otherwise False
        """
        my_state, when = self.get_state(peer, detail=True)
        if my_state == State.QUIESCENT:
            return False
        waited = (datetime.now() - when).total_seconds()
        return waited > threshold

    """:param new_leader: whatever you want self.bully to be set to"""
    def set_leader(self, new_leader):
        self.bully = new_leader
        print('now Leader is  {}'.format(self.pr_leader()))

    """Look up current state in state table."""
    def get_state(self, peer=None, detail=False):
        """
        :param peer: socket connected to peer process (None means self)
        :param detail: if True, then the state and timestamp are both returned
        :return: either the state or (state, timestamp) depending on detail (not found gives (QUIESCENT, None))
        """

        if peer is None:
            peer = self
        status = self.states[peer] if peer in self.states else (State.QUIESCENT, None)
        return status if detail else status[0]

    """Set/change the state for the given process."""
    def set_state(self, state, peer=None, switch_mode=False):
        """
        :param State state: new state
        :param peer: socket connected to peer process (None means self)
        :param switch_mode: True if we want to move from read to write or vice versa
        """
        print('{}: {}'.format(self.pr_sock(peer), state.name))
        if peer is None:
            peer = self

        # figure out if we need to register for read or write in selector
        if state.is_incoming():
            mask = selectors.EVENT_READ
        else:
            mask = selectors.EVENT_WRITE

        # setting to quiescent means delete it from self.states
        if state == State.QUIESCENT:
            if peer in self.states:
                if peer != self:
                    self.selector.unregister(peer)
                del self.states[peer]
            if len(self.states) == 0:
                print('{} (leader: {})\n'.format(self.pr_now(), self.pr_leader()))
            return

        # note the new state and adjust selector as necessary
        if peer != self and peer not in self.states:
            peer.setblocking(False)
            self.selector.register(peer, mask)
        elif switch_mode:
            self.selector.modify(peer, mask)
        self.states[peer] = (state, datetime.now())

        # try sending right away (if currently writable, the selector will never trigger it)
        if mask == selectors.EVENT_WRITE:
            self.send_message(peer)

    """set state QUIESCENT."""
    def set_quiescent(self, peer=None):
        self.set_state(State.QUIESCENT, peer)

    """ Sends an ELECTION to all the greater group members.If no greater members, then we declare victory.else wait for OK response."""
    def start_election(self, reason):
        """
        :param reason: text to put out to log as explanation
        """
        print('Starting an election {}'.format(reason))
        self.set_leader(None)  # election in progress
        self.set_state(State.WAITING_FOR_OK)
        big_bully = True
        for member in self.members:
            if member > self.pid:
                peer = self.get_connection(member)
                if peer is None:
                    continue
                self.set_state(State.SEND_ELECTION, peer)
                big_bully = False
        if big_bully:
            self.declare_victory('no other biggest bully than me')
 
    """ Tell all members that I am the biggest bully."""
    def declare_victory(self, reason):
        print('Victory by {} {}'.format(self.pid, reason))
        self.set_leader(self.pid)  # indicates election is over 
        for member in self.members:
            if member != self.pid:
                peer = self.get_connection(member)
                if peer is None:
                    continue
                self.set_state(State.SEND_VICTORY, peer)
        self.set_quiescent()
    
    """Pick up any new members from peer."""
    def update_members(self, their_idea_of_membership):
        if their_idea_of_membership is not None:
            for member in their_idea_of_membership:
                self.members[member] = their_idea_of_membership[member]

    """ Pickles and sends the given message to the peer socket and unpickle returned response."""
    @classmethod 
    def send(cls, peer, message_name, message_data=None, wait_for_reply=False, buffer_size=BUF_SZ):
        """
        :param peer: socket to send/recv
        :param message_name: text message name i.e 'ELECTION', 'OK', etc.
        :param message_data: anything pickle-able data
        :param wait_for_reply: if a sync response is needed
        """
        message = message_name if message_data is None else (message_name, message_data)
        peer.sendall(pickle.dumps(message))
        if wait_for_reply:
            return cls.receive(peer, buffer_size)

    """Receives data and unpickles it from the given socket."""
    @staticmethod
    def receive(peer, buffer_size=BUF_SZ):
        """"
        :param peer: socket to recv from
        :param buffer_size: buffer size for recv data
        :return param: the unpickled data received from peer
        """
        packet = peer.recv(buffer_size)
        if not packet:
            raise ValueError('socket closed')
        data = pickle.loads(packet)
        if type(data) == str:
            data = (data, None)  # turn a message into pair: (text, None)
        return data


    """ Start a socket bound to 'localhost' at a random port."""
    @staticmethod
    def start_a_server():
        """return param: listening socket and its address """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', 0)) # use any free socket
        s.listen(BACKLOG)
        s.setblocking(False)
        return s, s.getsockname()

    """ Join the group via the GCD."""
    def join_group(self):
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            message_data = (self.pid, self.listener_address)
            print('JOIN {}, {}'.format((self.host,self.port), message_data))
            s.connect((self.host,self.port))
            self.members = self.send(s, 'JOIN', message_data, wait_for_reply=True) #fill the joined member as a dict
            if type(self.members) != dict:
                raise TypeError('receive unexpected Error from GCD: {}'.format(self.members))

    """Printing helper for current timestamp."""
    @staticmethod
    def pr_now():
        return datetime.now().strftime('%H:%M:%S.%f')

    """Printing helper for given socket."""
    def pr_sock(self, sock):
        if sock is None or sock == self or sock == self.listener:
            return 'self'
        return self.cpr_sock(sock)

    """Static version of helper for printing given socket."""
    @staticmethod
    def cpr_sock(sock):
        l_port = sock.getsockname()[1] % PEER_DIGITS
        try:
            r_port = sock.getpeername()[1] % PEER_DIGITS
        except OSError:
            r_port = '???'
        return '{}->{} ({})'.format(l_port, r_port, id(sock))

    """Printing helper for current leader's name."""
    def pr_leader(self):
        return 'unknown' if self.bully is None else ('self' if self.bully == self.pid else self.bully)

    def probing(self):
        
        if self.bully is not None and self.bully != self.pid:
            peer = self.get_connection(self.bully)
            if peer is None:  # Start election if bully got disconnected
                self.start_election('bully disconnected')
            else:
                randomNum = random.randint(300, 4000)
                ts.sleep(randomNum/1000)
                self.set_state(State.PROBE, peer)
                print('self: Probe after waiting', randomNum/1000, 'seconds')
if __name__ == '__main__':
    if not 4 <= len(sys.argv) <= 5:
        print("Usage: python lab2.py GCDHOST GCDPORT SUID [DOB]")
        exit(1)
    if len(sys.argv) == 5:
        pieces = sys.argv[4].split('-')
        now = datetime.now()
        next_birth_day = datetime(now.year, int(pieces[1]), int(pieces[2]))
        if next_birth_day < now:
            next_birth_day = datetime(next_birth_day.year + 1, next_birth_day.month, next_birth_day.day)
    else:
        next_birth_day = datetime(2023, 1, 1)
    print('Next Birthday:', next_birth_day)
    su_id = int(sys.argv[3])
    print('SeattleU ID:', su_id)
    lab2 = Lab2(sys.argv[1], sys.argv[2], next_birth_day,su_id) 
    lab2.run()