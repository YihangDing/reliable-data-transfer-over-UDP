from utils import *

file_name = '11-0.txt'
cnt = 0
file_list = []
for chunk in read_file(file_name, chunk_size=DATA_LENGTH):
	#print(cnt)
	cnt += 1
	file_list.append(chunk)
print(type(file_list[0]))