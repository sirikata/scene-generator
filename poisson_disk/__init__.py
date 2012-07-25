## @mainpage Poisson Disk Sampling
##
## Contains functions for Poisson disk sampling, and the classes and functions
## that support it. The code can be downloaded from http://www.luma.co.za/labs/2008/02/27/poisson-disk-sampling.
##
## @version 0.1 (last updated 16 Dec 2007)
## @author Herman Tulleken (herman@luma.co.za)

##@package poisson_perlin
##@brief Contains documentation for this library.


##@package poisson_disk 
##@brief Contains functions for generating Poisson disk samples.
##

from math import log
from math import sin
from math import cos
from math import sqrt
from math import floor
from math import ceil
from math import pi

from random import random
from random import randint
from random import uniform

from datastructures import RandomQueue
from enhanced_grid import int_point_2d
from enhanced_grid import int_point_3d
from enhanced_grid import Grid2D
from enhanced_grid import Grid3D
from enhanced_grid import ListGrid2D
from enhanced_grid import ListGrid3D


##@brief Returns a random integer in the range [0, n-1] inclusive.
def rand(n):
	return randint(0, n - 1)

##@brief The square of the distance between the given points
def sqr_dist((x0, y0), (x1, y1)):
	return (x1 - x0)*(x1 - x0) + (y1 - y0)*(y1 - y0)

##@brief The square of the distance between the given points
def sqr_dist_3d((x0, y0, z0), (x1, y1, z1)):
	return (x1 - x0)*(x1 - x0) + (y1 - y0)*(y1 - y0) + (z1 - z0)*(z1 - z0) 


## @brief Gives a Poisson sample of points of a rectangle.
##
# @param width
#		The width of the rectangle to sample
# @param height
#		The height of the rectangle to sample
# @param r
#		The mimum distance between points, in terms of 
#		rectangle units. For example, in a 10 by 10 grid, a mimum distance of 
#		10 will probably only give you one sample point.
# @param k
#		The algorithm generates k points around points already 
#		in the sample, and then check if they are not too close
#		to other points. Typically, k = 30 is sufficient. The larger 
#		k is, the slower th algorithm, but the more sample points
#		are produced.
# @return A list of tuples representing x, y coordinates of
#		of the sample points. The coordinates are not necesarily
#		integers, so that the can be more accurately scaled to be
#		used on larger rectangles.
def sample_poisson_uniform(width, height, r, k):
	#Convert rectangle (the one to be sampled) coordinates to 
	# coordinates in the grid.
	def grid_coordinates((x, y)):
		return (int(x*inv_cell_size), int(y*inv_cell_size))
	
	# Puts a sample point in all the algorithm's relevant containers.
	def put_point(p):
		process_list.push(p)
		sample_points.append(p)  
		grid[grid_coordinates(p)] = p

	# Generates a point randomly selected around
	# the given point, between r and 2*r units away.
	def generate_random_around((x, y), r):
		rr = uniform(r, 2*r)
		rt = uniform(0, 2*pi)
		
		return rr*sin(rt) + x, rr*cos(rt) + y
		
	# Is the given point in the rectangle to be sampled?
	def in_rectangle((x, y)):
		return 0 <= x < width and 0 <= y < height
		
	def in_neighbourhood(p):
		gp = gx, gy = grid_coordinates(p)
		
		if grid[gp]: return True
		
		for cell in grid.square_iter(gp, 2):
			if cell and sqr_dist(cell, p) <= r_sqr:
				return True
		return False

	#Create the grid
	cell_size = r/sqrt(2)
	inv_cell_size = 1 / cell_size	
	r_sqr = r*r
	
	grid = Grid2D((int(ceil(width/cell_size)),
		int(ceil(height/cell_size))))
		
	process_list = RandomQueue()
	sample_points = []	
	
	#generate the first point
	put_point((rand(width), rand(height)))
	
	#generate other points from points in queue.
	while not process_list.empty():
		p = process_list.pop()
		
		for i in xrange(k):
			q = generate_random_around(p, r)
			if in_rectangle(q) and not in_neighbourhood(q):
					put_point(q)
	
	return sample_points
	
##@brief Gives a Poisson sample of points of a rectangle with an arbitrary distance function between points.
##
# @param width
#		The width of the rectangle to sample
# @param height
#		The height of the rectangle to sample
# @param r_grid
#		r_grid[x, y] is the mimum distance between points around x, y, in terms of 
#		rectangle units. 
# @param k
#		The algorithm generates k points around points already 
#		in the sample, and then check if they are not too close
#		to other points. Typically, k = 30 is sufficient. The larger 
#		k is, the slower th algorithm, but the more sample points
#		are produced.
# @return A list of tuples representing x, y coordinates of
#		of the sample points. The coordinates are not necesarily
#		integers, so that the can be more accurately scaled to be
#		used on larger rectangles.
def sample_poisson(width, height, r_grid, k):	
	#Convert rectangle (the one to be sampled) coordinates to 
	# coordinates in the grid.
	def grid_coordinates((x, y)):
		return (int(x*inv_cell_size), int(y*inv_cell_size))
	
	# Puts a sample point in all the algorithm's relevant containers.
	def put_point(p):
		process_list.push(p)
		sample_points.append(p)  
		grid[grid_coordinates(p)].append(p)

	# Generates a point randomly selected around
	# the given point, between r and 2*r units away.
	def generate_random_around((x, y), r):
		rr = uniform(r, 2*r)
		rt = uniform(0, 2*pi)
		
		return rr*sin(rt) + x, rr*cos(rt) + y
		
	# Is the given point in the rectangle to be sampled?
	def in_rectangle((x, y)):
		return 0 <= x < width and 0 <= y < height
	
	def in_neighbourhood(p, r):
		gp = grid_coordinates(p)
		r_sqr = r*r
		
		for cell in grid.square_iter(gp, 2):
			for q in cell:
				if sqr_dist(q, p) <= r_sqr:
					return True
		return False

	r_min, r_max = r_grid.min_max()
	
	#Create the grid
	cell_size = r_max/sqrt(2)
	inv_cell_size = 1 / cell_size	
	r_max_sqr = r_max*r_max
	
	grid = ListGrid2D(int_point_2d((ceil(width/cell_size),
		ceil(height/cell_size))))
		
	process_list = RandomQueue()
	sample_points = []	
	
	#generate the first point
	put_point((rand(width), rand(height)))
	
	#generate other points from points in queue.
	while not process_list.empty():
		p = process_list.pop()
		r = r_grid[int_point_2d(p)]
		
		for i in xrange(k):			
			q = generate_random_around(p, r)
			if in_rectangle(q) and not in_neighbourhood(q, r):
					put_point(q)
	
	return sample_points

##@brief Gives a Poisson sample of points of a box (3D rectangle).
##
# @param width
#		The width of the box to sample
# @param height
#		The height of the box to sample
# @param depth
#		The depth of the box to sample.  
# @param r_grid
#		r_grid[x, y, z] is the mimum distance between points around x, y, z, in terms of 
#		rectangle units. 
# @param k
#		The algorithm generates k points around points already 
#		in the sample, and then check if they are not too close
#		to other points. Typically, k = 30 is sufficient. The larger 
#		k is, the slower th algorithm, but the more sample points
#		are produced.
# @return A list of tuples representing x, y coordinates of
#		of the sample points. The coordinates are not necesarily
#		integers, so that the can be more accurately scaled to be
#		used on larger rectangles.
def sample_poisson_3d(width, height, depth, r_grid, k):	
	#Convert rectangle (the one to be sampled) coordinates to 
	# coordinates in the grid.
	def grid_coordinates((x, y, z)):
		return int_point_3d((x*inv_cell_size, y*inv_cell_size, z*inv_cell_size))
	
	# Puts a sample point in all the algorithm's relevant containers.
	def put_point(p):
		process_list.push(p)
		sample_points.append(p)
		grid[grid_coordinates(p)].append(p)

	# Generates a point randomly selected around
	# the given point, between r and 2*r units away.
	def generate_random_around((x, y, z), r):
		rr = uniform(r, 2*r)		
		rs = uniform(0, 2*pi)
		rt = uniform(0, 2*pi)		
		
		return rr*sin(rs)*cos(rt) + x, rr*sin(rs)*sin(rt) + y, rr*cos(rs) + z
		
	# Is the given point in the rectangle to be sampled?
	def in_rectangle((x, y, z)):
		return 0 <= x < width and 0 <= y < height and 0 <= z < depth
	
	def in_neighbourhood(p, r):
		gp = grid_coordinates(p)
		r_sqr = r*r
		
		for cell in grid.square_iter(gp, 2):
			for q in cell:
				if sqr_dist_3d(q, p) <= r_sqr:
					return True
		return False

	r_min, r_max = r_grid.min_max()
	
	#Create the grid
	cell_size = r_max/sqrt(2)
	inv_cell_size = 1 / cell_size	
	r_max_sqr = r_max*r_max
	
	grid = ListGrid3D((
		int(ceil(width/cell_size)),
		int(ceil(height/cell_size)),
		int(ceil(depth/cell_size))))
		
	process_list = RandomQueue()
	sample_points = []	
	
	#generate the first point
	put_point((rand(width), rand(height), rand(depth)))
	
	#generate other points from points in queue.
	while not process_list.empty():
		p = process_list.pop()
		r = r_grid[int_point_3d(p)]

		for i in xrange(k):			
			q = generate_random_around(p, r)
			if in_rectangle(q) and not in_neighbourhood(q, r):
					put_point(q)
	
	return sample_points