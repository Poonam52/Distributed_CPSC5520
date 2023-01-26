class BellmanFord(object):
	
	def __init__(self, init_graph):
		"""
		:param init_graph: the graph to use
		"""
		self.graph = init_graph
		self.vertices = len(init_graph)
	
	def shortest_paths(self, origin, tolerance=0):
		# construct a list of distances
		previous = {}
		distance = {}
		
		# initialize the shortest distance to infinity and previous vertex to None
		for vertex in self.graph:
			distance[vertex] = float("Inf")
			previous[vertex] = None
		
		# the shortest distance to the origin from the origin is 0
		distance[origin] = 0
		
		for i in range(self.vertices - 1):
			for curr1 in self.graph:
				for curr2 in self.graph[curr1]:
					weight = self.graph[curr1][curr2]["price"]
					# if this new path is shorter than the previous distance
					if distance[curr1] != float("Inf") and (distance[curr1] + weight + tolerance < distance[curr2] and distance[curr1] + weight - tolerance < distance[curr2]):
						distance[curr2] = distance[curr1] + weight
						previous[curr2] = curr1
						
		# negative path detection
		for curr1 in self.graph:
			for curr2 in self.graph[curr1]:
				weight = self.graph[curr1][curr2]["price"]
				# if found a negative path, return it
				if distance[curr1] != float("Inf") and (distance[curr1] + weight + tolerance < distance[curr2] and distance[curr1] + weight - tolerance < distance[curr2]):
					return distance, previous, (curr1, curr2)
					
		return distance, previous, None