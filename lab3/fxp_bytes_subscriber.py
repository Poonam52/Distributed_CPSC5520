from datetime import datetime
import ipaddress
from array import array

MIC_PER_SEC= 1_000_000

""" Convert a byte array into a float from an incoming provider method
	:param b: the bytes representing a price to be deserialized
	:return: the float representation of the bytes """
def deserializePrice(b: bytes) -> float:
	
	p_a = array('d')
	p_a.frombytes(b)
	return p_a[0]

""" Serialize a hostname, port tuple as bytes """	
def serializeAddress(address) -> bytes:
	""":param host: the hostname to serialize
	   :param port: the port to serialize
	   :return: the byte representation of host+port """
	ip_bytes = ipaddress.ip_address(address[0]).packed
	port_bytes = address[1].to_bytes(2, byteorder="big")
	return ip_bytes + port_bytes

"""Convert from bytes into a datetime object as UTC timestamp"""
def deserialize_utcdatetime(b: bytes) -> datetime:
	"""
	:param b: the bytes to deserialize
	:return: the datetime object representing the UTC timestamp
	"""
	a = array('L')
	a.frombytes(b)
	a.byteswap()
	time = datetime.fromtimestamp(a[0] / MIC_PER_SEC)
	return time + (datetime.utcnow() - datetime.now()) 

"""Convert from bytes into a list object containing all of the quotes (as dicts)"""
def demarshalMsg(b: bytes) -> list:
	"""Format of each quote: {'timestamp': datetime, cross: 'curr_tla/curr_tla', price: float}
	   :param b: the bytes to be demarshaled into a series of quotes
	   :return: a list of quote objects
	"""
	num_quotes = int(len(b) / 32) # 32 byte pieces for each quote
	quotes = []
	
	# go through each of the quotes to make the list
	for x in range(0, num_quotes):
		quote_bytes = b[x*32:x*32+32]
		quote = {}
		quote["timestamp"] = deserialize_utcdatetime(quote_bytes[0:8])
		quote["cross"] = quote_bytes[8:11].decode("utf-8") + "/" + quote_bytes[11:14].decode("utf-8")
		quote["price"] = deserializePrice(quote_bytes[14:22])
		quotes.append(quote)
		
	return quotes