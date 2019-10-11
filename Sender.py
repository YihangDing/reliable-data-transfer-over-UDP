import socket
#from socket import *
from utils import *
import time, struct, sys, random

def send(file_list, address, port, local_socket):
	#start with seq # 0
	seqnum = 0
	#max seqnum is num(data)+1, start: seqnum == 0, end: seq = num(data) - 1 
	MAX_PKT_NUM = len(file_list)

	#decide if end pkt need to be sent within the first window
	IN_FIRST_WINDOW = True if MAX_PKT_NUM <= WND_SIZE else False

	#hash table for saving send time
	time_table = {}

	#send all pkt within window
	while seqnum < min(WND_SIZE, MAX_PKT_NUM):
		#send start pkt
		if not seqnum:
			#deal with case when start == end 
			tmp_flag = START_OPCODE if MAX_PKT_NUM > 1 else SPECIAL_OPCODE
			data = make_packet(seqnum, file_list[seqnum], flag=tmp_flag)
			local_socket.sendto(data, address)
			time_table[seqnum] = time.time()
			seqnum += 1
			#seq_num, time_table = send_pkt(seqnum, bytes(), 0, time_table, address, local_socket)
		#when end pkt not in first window, send everything
		elif not IN_FIRST_WINDOW:# and seqnum < WND_SIZE:
			data = make_packet(seqnum, file_list[seqnum], flag=DATA_OPCODE)
			local_socket.sendto(data, address)
			time_table[seqnum] = time.time()
			seqnum += 1
		#when end pkt is in first window
		elif IN_FIRST_WINDOW:# and seqnum < MAX_PKT_NUM:
			#deal with if flag is data or end
			tmp_flag = DATA_OPCODE if seqnum < MAX_PKT_NUM - 1 else END_OPCODE
			data = make_packet(seqnum, file_list[seqnum], flag=tmp_flag)
			local_socket.sendto(data, address)
			time_table[seqnum] = time.time()
			seqnum += 1
		print('send pkt with seq num %d' % (seqnum - 1))
		# if seqnum == MAX_PKT_NUM:
		# 	print('last pkt sent')
		# 	return 1
	print('first window all sent')

	#stack for saving last 3 acks
	duplicate_ack_stack = []
	#use unblock recv to recv ack, send corresponding data pkt 
	#check time.clock() at each loop, cmp with time_table, resend pkt whose gap > 0.5s
	while True:
		#unblock recv to recv ack
		try:
			message, address = local_socket.recvfrom(MAX_SIZE, socket.MSG_DONTWAIT)
			#seqnum is lowest sequence number not yet received in order
			csum, rsum, seqnum, flag, data = extract_packet(message)
			print('received ack with seqnum %d' % seqnum)
			#ignore if checksum is not correct
			if csum == rsum: 
				#if seqnum == MAX_PKT_NUM: all pkt has been received
				if seqnum == MAX_PKT_NUM:
					print('All Pkt Sent!')
					return seqnum
				#if seqnum in window: means all pkt whose seqnum < reveived seqnum has been received, 
				#move forward window (send ALL new pkt in NEW window that has not been sent)
				elif seqnum in time_table.keys():
					#pop out all seqnum in time_table before received seqnum
					time_table_list = sorted(list(time_table.keys()))
					for item in time_table_list:
						if item < seqnum:
							time_table.pop(item)
						else:
							break
					old_window_tail = time_table_list[-1]
					new_window_tail = min(seqnum + WND_SIZE, MAX_PKT_NUM) 
					#send all new pkt in window 
					for tmp_seqnum in range(old_window_tail+1, new_window_tail):
						#get flag
						tmp_flag = DATA_OPCODE if tmp_seqnum < MAX_PKT_NUM - 1 else END_OPCODE
						#tmp_flag = START_OPCODE if seqnum == 0 else tmp_flag
						#tmp_flag = SPECIAL_OPCODE if MAX_PKT_NUM == 0 else tmp_flag
						print('send pkt with seq num %d' % (tmp_seqnum))

						#resend
						data = make_packet(tmp_seqnum, file_list[tmp_seqnum], flag=tmp_flag)
						local_socket.sendto(data, address)
						time_table[tmp_seqnum] = time.time()


				#check if needs fast retransmit
				if len(duplicate_ack_stack) < 3:
					duplicate_ack_stack.append(seqnum)
				else:
					duplicate_ack_stack.pop(0)
					duplicate_ack_stack.append(seqnum)
					#resend if all 3 seqnum in stack are the same
					if len(set(duplicate_ack_stack)) == 1:
						print('fast retransmit for pkt with seqnum %d' % seqnum)
						#get flag
						tmp_flag = DATA_OPCODE if seqnum < MAX_PKT_NUM - 1 else END_OPCODE
						#tmp_flag = START_OPCODE if seqnum == 0 else tmp_flag
						#tmp_flag = SPECIAL_OPCODE if MAX_PKT_NUM == 0 else tmp_flag

						#resend
						data = make_packet(seqnum, file_list[seqnum], flag=tmp_flag)
						local_socket.sendto(data, address)
						time_table[seqnum] = time.time()

			else:
				#ignore incorrect checksum ack
				print('checksum incorrect. pkt corrupted')
				#pass

			#cmp time to get timeout pkt
			time_now = time.time()
			for seqnum in sorted(list(time_table.keys())):
				#for timeout pkt, resend
				if time_now - time_table[seqnum] >= 0.5:
					#get flag
					print('pkt timeout with seqnum: %d' % seqnum)
					tmp_flag = DATA_OPCODE if seqnum < MAX_PKT_NUM - 1 else END_OPCODE
					tmp_flag = START_OPCODE if seqnum == 0 else tmp_flag
					tmp_flag = SPECIAL_OPCODE if MAX_PKT_NUM == 0 else tmp_flag

					#resend
					data = make_packet(seqnum, file_list[seqnum], flag=tmp_flag)
					local_socket.sendto(data, address)
					time_table[seqnum] = time.time()
					break


		except socket.error, e:
			err = e.args[0]
			if err == socket.errno.EAGAIN or err == socket.errno.EWOULDBLOCK:
				#print 'No data recvd'
				continue
			else:
				# a "real" error occurred
				print e
	return 1


def send_pkt(seqnum, pkt_data, flag_num, time_table, address, local_socket):
	pkt = make_packet(seqnum, pkt_data, flag=flag_num)
	local_socket.sendto(pkt, address)
	time_table[seqnum] = time.time()
	seqnum += 1
	return seqnum, time_table

def usage():
	print("Usage: python Sender.py <input file> <receiver address> <receiver port>")
	exit()

def main():
	if len(sys.argv) < 4:
		print('argv less than 4')
		usage()
		sys.exit(-1)
	print(sys.argv)

	start_time = time.clock()
	file_name = sys.argv[1]
	address = sys.argv[2]
	port = int(sys.argv[3])
	# print('prep arg')
	# start_time = time.clock()
	# file_name = '11-0.txt'
	# address = 'localhost'
	# port = 7000

	address = (address, port)

	#create UDP socket to send file on
	local_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	#local_socket.setblocking(False)

	#read file chunk into list
	file_list = []
	for chunk in read_file(file_name, chunk_size=DATA_LENGTH):
		file_list.append(chunk)
	print('MAX_PKT_NUM: %d' % len(file_list))

	#start sending file
	print('Start sending file')
	sended = send(file_list, address, port, local_socket)

	end_time = x()
	print("start_time: {}, end_time: {}".format(start_time, end_time))

if __name__ == '__main__':
	main()