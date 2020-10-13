from netfilterqueue import NetfilterQueue
from scapy.all import *
import optparse
import sys
import time
import csv
from pathlib import Path
sys.path.insert(1, '../')
import helper

class Flow_Label_CC:

	#-------------- MAGIC VALUES --------------#
	START_MAGIC_VALUE = 1048575
	END_MAGIC_VALUE = 1048574
	#-------------- MAGIC VALUES --------------#

	def __init__(self, chunks, role, number_clean_packets, length_stego_packets):
		'''
		Constructor for sender and receiver of a Flow Label Covert Channel
		:param list chunks: A list of strings in binary format, which shall be injected into the Flow Label field.
		:param policy: injection policy: n stego-packets every n clear packets
		:raises ValueError: if the chunks is an empty list.
		'''

		self.chunks = chunks 			# A list with binary strings. These is this secret what shall be injected.
		self.chunks_int = [int(x,2) for x in self.chunks]	# The list of chunks converted to int
		
		self.sent_received_chunks = 0		# Contains the number of sent/received chunks/injected packets (depending on the role of the class).
		self.nfqueue = NetfilterQueue()		# The netfilter object which is bound on the netfilter queue.
		self.exfiltrated_data = []			# A list with signatures and the corresponding injected values.
		self.sent_packets = 0				# Number of sent packets in general (injected AND not injected).
		self.received_packets = 0			# The number of received packets (exfiltrated AND not exfiltrated).
		self.role = role
		self.first_packet = True
		self.start_exf = False
		self.dd = False
		self.separate_test = False

		self.number_of_repetitions = 10
		self.number_of_repetitions_done = 0

		self.number_clean_packets = number_clean_packets
		self.length_stego_packets = length_stego_packets
		self.stegotime = True
		self.clean_counter = 0

		# ------------------- MEASUREMENT VARIABLES ------------------- #
		self.starttime_stegocommunication = 0.0
		self.endtime_stegocommunication = 0.0
		self.injection_exfiltration_time_sum = 0.0

	def exfiltrate(self, packet):
		'''
	   	The exfiltration method of the receiver, which is bound the the netfilter queue NETFILTERQUEUE_NUMBER.
	   	This method exfiltrates the content of the flow label field of the received packet.
	   	The content is saved into self.exfiltrated_data. Then it increments the counter self.sent_received_chunks and self.received_packets by 1. If nothing
	   	is exfiltrated only the last counter is incremented. The list self.chunks_int_exfiltration is used to check if the message is correctly exfiltrated.

	   	:param Packet packet: The NetfilterQueue Packet object which is received and can be transformed into Scapy IPv6()-packet.
	   	'''
		# Exfiltration not started
		if self.number_of_repetitions_done < self.number_of_repetitions:
			
			if self.start_exf and self.stegotime: 
				tmp1 = time.perf_counter()
			
			pkt = IPv6(packet.get_payload())
			
			if not self.start_exf:
				self.start_exf = pkt.fl == Flow_Label_CC.START_MAGIC_VALUE
				if self.start_exf:
					self.starttime_stegocommunication = time.perf_counter()
					# print('start')

			# Exfiltration started
			else:
				# If the previous packet was an escape sequence
				if self.stegotime:

					if self.dd:
						# Unset delimiter detection Flag 
						self.dd = False
						# if the current packet is the end value => exfiltrate
						if pkt.fl == Flow_Label_CC.END_MAGIC_VALUE:
							self.exfiltrated_data.append(pkt.fl)
							# print('char stuf')
							self.sent_received_chunks += 1
						# The previous packet gets interpreted as end value => stop exfiltration
						else:
							# Stop the Exfiltration
							# print('end')
							self.start_exf = False
							self.endtime_stegocommunication = time.perf_counter()
							# Erase the Ending Value
							self.exfiltrated_data = self.exfiltrated_data[:-1]
							self.sent_received_chunks -= 1
							self.injection_exfiltration_time_sum += time.perf_counter() - tmp1
							# Increment the number of repitions
							self.number_of_repetitions_done += 1
							# Do the statistical evaluation
							self.statistical_evaluation_received_packets()
							# Write the csv-File
							self.write_csv()
							# Reset every necessary counter and list for the next experiment
							self.received_packets = 0
							self.sent_received_chunks = 0
							self.clean_counter = 0
							self.exfiltrated_data = []
							self.stegotime = True
							self.starttime_stegocommunication = 0.0
							self.endtime_stegocommunication = 0.0
							self.injection_exfiltration_time_sum = 0.0
							if pkt.fl == Flow_Label_CC.START_MAGIC_VALUE:
								# print('start')
								self.starttime_stegocommunication = time.perf_counter()
								self.start_exf = True

					# Previous packet was not an escape sequence or ending value
					else:
						# Is an escape sequence detected?
						# print('exf')
						self.dd = pkt.fl == Flow_Label_CC.END_MAGIC_VALUE
						self.exfiltrated_data.append(pkt.fl)
						self.sent_received_chunks += 1
						if self.length_stego_packets > 0:
							self.stegotime = self.sent_received_chunks % self.length_stego_packets != 0

					if self.start_exf: 
						self.injection_exfiltration_time_sum += time.perf_counter() - tmp1
				
				else:
					self.clean_counter += 1
					# print('not exf')
					self.stegotime = self.clean_counter % self.number_clean_packets == 0

		self.received_packets += 1
		packet.accept()

	def inject(self, packet):

		'''
	   	The inject method of the sender, which is bound the the netfilter queue NETFILTERQUEUE_NUMBER.
	   	This method injects the content of chunks into the flow label field of parameter packet.
	   	The injected content is saved into self.exfiltrated_data. Then it increments the counter self.sent_received_chunks and self.received_packets by 1.
	   	Then the payload of the altered packet is set. This is done considering the policy parameter.

	   	:param Packet packet: The NetfilterQueue Packet object packet, where the exfiltrated data is injected into the flow label field.
	   	'''
		if self.number_of_repetitions_done < self.number_of_repetitions:
			if self.stegotime:
				tmp1 = time.perf_counter()
				pkt = IPv6(packet.get_payload())
				if self.sent_received_chunks < len(self.chunks):
					if self.first_packet:
						# print('start')
						self.starttime_stegocommunication = time.perf_counter()
						pkt.fl = Flow_Label_CC.START_MAGIC_VALUE
						self.first_packet = False
						packet.set_payload(bytes(pkt))
					else:
						# print('inj')
						pkt.fl = int(self.chunks[self.sent_received_chunks], 2)
						self.exfiltrated_data.append(pkt.fl)
						self.sent_received_chunks += 1
						packet.set_payload(bytes(pkt))
				
						if self.length_stego_packets > 0:
							if self.sent_received_chunks % self.length_stego_packets == 0:
								self.stegotime = False
							else:
								self.stegotime = True

					if not self.first_packet:
						self.injection_exfiltration_time_sum += time.perf_counter() - tmp1
				else:
					# print('end')
					pkt.fl = Flow_Label_CC.END_MAGIC_VALUE
					packet.set_payload(bytes(pkt))
					self.endtime_stegocommunication = time.perf_counter()
					self.injection_exfiltration_time_sum += time.perf_counter() - tmp1
					self.number_of_repetitions_done += 1
					self.first_packet = True
					self.statistical_evaluation_sent_packets()
					self.write_csv()
					self.sent_received_chunks = 0
					self.sent_packets = 0
					self.stegotime = True
					self.clean_counter = 0
					self.injection_exfiltration_time_sum = 0
					self.starttime_stegocommunication = 0
					self.endtime_stegocommunication = 0
					# print(str(self.exfiltrated_data))
					self.exfiltrated_data = []
			else:
				
				# print('not inj')
				self.clean_counter += 1
				if self.clean_counter % self.number_clean_packets == 0:
					self.stegotime = True
					self.clean_counter = 0
		
		self.sent_packets += 1
		packet.accept()

	def start_sending(self):
		'''
	   	Binds the inject method to the netfilter queue with its specific number and runs the callback function. If the user press Ctrl + c
	   	the inject method is unbind.  
	   	'''
		self.nfqueue.bind(helper.NETFILTER_QUEUE_NUMBER, self.inject)
		try:
			self.nfqueue.run()
		except KeyboardInterrupt:
			print("The injection is stopped.")
		self.nfqueue.unbind()

	def start_receiving(self):
		'''
	   	Binds the exfiltrate method to the netfilter queue with its specific number and runs the callback function. If the user press Ctrl + c
	   	the inject method is unbind.  
	   	'''
		self.nfqueue.bind(helper.NETFILTER_QUEUE_NUMBER, self.exfiltrate)
		try:
			self.nfqueue.run()
		except KeyboardInterrupt:
			print("The exfiltration is stopped.")
		self.nfqueue.unbind()

	def write_csv(self):
		
		filename="results_flow_label_" + str(len(self.chunks_int)) + "_" + str(self.role) + ".csv"
		csv_file = Path(filename)
		file_existed = csv_file.is_file()

		with open(filename, 'a', newline='') as file:
			writer = csv.writer(file)

			if not file_existed:
				if self.role == 'sender':
					writer.writerow(["Stego-packets sent", "Duration of Stegocommunication (ms)", "Average Injection Time (ms)", "Bandwidth (bits/s)"])
				else:
					writer.writerow(["Stego-packets received", "Duration of Stegocommunication (ms)", "Average Exfiltration Time (ms)", "Bandwith (bits/s)", "Failures", "Successfully transmitted Message (%)"])
			
			if self.role == 'sender':
				writer.writerow([self.sent_received_chunks, \
					round((self.endtime_stegocommunication - self.starttime_stegocommunication) * 1000, 2), \
					round((self.injection_exfiltration_time_sum / self.sent_received_chunks) * 1000, 2), \
					round((helper.IPv6_HEADER_FIELD_LENGTHS_IN_BITS["Flow Label"] * self.sent_received_chunks) / (self.endtime_stegocommunication - self.starttime_stegocommunication), 2)])  			
			else:
				failures = 0
				index_first_failure = -1 

				# Count the failures
				if len(self.exfiltrated_data) <= len(self.chunks_int):
					for x in range(len(self.exfiltrated_data)):
						if self.exfiltrated_data[x] != self.chunks_int[x]:
							failures += 1
				else:
					for x in range(len(self.chunks_int)):
						if self.exfiltrated_data[x] != self.chunks_int[x]:
							failures += 1
				failures += abs(len(self.exfiltrated_data) - len(self.chunks_int))

				if failures != 0:
					# Receive less than expected => first failure can happen in the middle or after the last index
					if len(self.exfiltrated_data) < len(self.chunks_int):
						for x in range(len(self.exfiltrated_data)):
							if self.exfiltrated_data[x] != self.chunks_int[x]:
								index_first_failure = x
								break
						if index_first_failure == -1:
							index_first_failure = len(self.exfiltrated_data)
					# Receive exactly the amount which is expected => index must be in the middle
					elif len(self.exfiltrated_data) == len(self.chunks_int):
						for x in range(len(self.chunks_int)):
							if self.exfiltrated_data[x] != self.chunks_int[x]:
								index_first_failure = x
								break
					else:
					# Receive more than expected => first failure can happen in the middle or after the last index
						for x in range(len(self.chunks_int)):
							if self.exfiltrated_data[x] != self.chunks_int[x]:
								index_first_failure = x
								break
						if index_first_failure == -1:
							index_first_failure = len(self.chunks_int)

				if index_first_failure == -1:
					index_first_failure = self.sent_received_chunks
					
				writer.writerow([self.sent_received_chunks, \
					round((self.endtime_stegocommunication - self.starttime_stegocommunication) * 1000, 2), \
					round((self.injection_exfiltration_time_sum / self.sent_received_chunks) * 1000, 2), \
					round((helper.IPv6_HEADER_FIELD_LENGTHS_IN_BITS["Flow Label"] * self.sent_received_chunks) / (self.endtime_stegocommunication - self.starttime_stegocommunication), 2), \
					round(failures), \
					round((index_first_failure/self.sent_received_chunks),2) * 100])

	def print_start_message(self):

		print('')
		if self.role == "sender":
			print('################## MAGIC VALUE FLOW LABEL CC SENDER ##################')
		else:
			print('################## MAGIC VALUE FLOW LABEL CC RECEIVER ##################')
		print('- Number of Repetitions: ' + str(self.number_of_repetitions))		
		if self.number_clean_packets > 0 and self.length_stego_packets > 0:
			buf = ""
			for x in range(2):
				for y in range(self.length_stego_packets):
					buf += "S "
				for y in range(self.number_clean_packets):
					buf += "C "	
			print('- Length Clean Packets: ' + str(self.number_clean_packets))		
			print('- Length Stego Packets: ' + str(self.length_stego_packets))		
			print('  ==> Packet Pattern (S=stego, C=clean): ' + buf + "...")		
		print('- Number of Chunks: ' + str(len(self.chunks)))	
		if self.role == "sender":
			print('################## MAGIC VALUE FLOW LABEL CC SENDER ##################')
		else:
			print('################## MAGIC VALUE FLOW LABEL CC RECEIVER ##################')
		print('')
		if self.role == "sender":
			print('Injection in covert channel is started...')
			print('Stop injection with CTRL+C.')
		else:
			print('Exfiltration from covert channel is started...')
			print('Stop exfiltration with CTRL+C...')
		print('')

	def statistical_evaluation_sent_packets(self):
		
		print('')
		print('##################### ANALYSIS SENT DATA #####################')
		print("- Number of Repetitions: " + str(self.number_of_repetitions_done) + "/" + str(self.number_of_repetitions))
		print("- Stego-packets sent: " + str(self.sent_received_chunks) + "/" + str(len(self.chunks_int)))
		print("- Duration of Stegocommunication: " + str(round((self.endtime_stegocommunication - self.starttime_stegocommunication) * 1000, 2)) + " ms")
		print("- Average Injection Time: " + str(round((self.injection_exfiltration_time_sum / self.sent_received_chunks) * 1000, 2)) + " ms")
		print("- Bandwidth: " + str(round((helper.IPv6_HEADER_FIELD_LENGTHS_IN_BITS["Flow Label"] * self.sent_received_chunks) / (self.endtime_stegocommunication - self.starttime_stegocommunication), 2)) + " bits/s")
		print("- Injected data == Chunks: " + str(self.exfiltrated_data == self.chunks_int))
		print('##################### ANALYSIS SENT DATA #####################')
		print('')

	def statistical_evaluation_received_packets(self):
		
		failures = 0
		index_first_failure = -1 

		# Count the failures
		if len(self.exfiltrated_data) <= len(self.chunks_int):
			for x in range(len(self.exfiltrated_data)):
				if self.exfiltrated_data[x] != self.chunks_int[x]:
					failures += 1
		else:
			for x in range(len(self.chunks_int)):
				if self.exfiltrated_data[x] != self.chunks_int[x]:
					failures += 1
		failures += abs(len(self.exfiltrated_data) - len(self.chunks_int))

		if failures != 0:
			# Receive less than expected => first failure can happen in the middle or after the last index
			if len(self.exfiltrated_data) < len(self.chunks_int):
				for x in range(len(self.exfiltrated_data)):
					if self.exfiltrated_data[x] != self.chunks_int[x]:
						index_first_failure = x
						break
				if index_first_failure == -1:
					index_first_failure = len(self.exfiltrated_data)
			# Receive exactly the amount which is expected => index must be in the middle
			elif len(self.exfiltrated_data) == len(self.chunks_int):
				for x in range(len(self.chunks_int)):
					if self.exfiltrated_data[x] != self.chunks_int[x]:
						index_first_failure = x
						break
			else:
			# Receive more than expected => first failure can happen in the middle or after the last index
				for x in range(len(self.chunks_int)):
					if self.exfiltrated_data[x] != self.chunks_int[x]:
						index_first_failure = x
						break
				if index_first_failure == -1:
					index_first_failure = len(self.chunks_int)

		if index_first_failure == -1:
			index_first_failure = self.sent_received_chunks
		
		print('')
		print('##################### ANALYSIS RECEIVED DATA #####################')
		print("- Number of Repetitions: " + str(self.number_of_repetitions_done) + "/" + str(self.number_of_repetitions))
		print("- Stego-packets received: " + str(self.sent_received_chunks) + "/" + str(len(self.chunks_int)))
		print("- Duration of Stegocommunication: " + str(round((self.endtime_stegocommunication - self.starttime_stegocommunication) * 1000, 2)) + " ms")
		print("- Average Exfiltration Time: " + str(round((self.injection_exfiltration_time_sum / self.sent_received_chunks) * 1000, 2)) + " ms")
		print("- Bandwidth: " + str(round((helper.IPv6_HEADER_FIELD_LENGTHS_IN_BITS["Flow Label"] * self.sent_received_chunks) / (self.endtime_stegocommunication - self.starttime_stegocommunication), 2)) + " bits/s")
		print("- Exfiltrated data == Chunks: " + str(self.exfiltrated_data == self.chunks_int) + " (" + str(failures) + " Failures)")
		print("- Correct % message: " + str(round((index_first_failure/self.sent_received_chunks) * 100, 2)))
		print('##################### ANALYSIS RECEIVED DATA #####################')
		print('')

	def process_command_line(argv):
		'''
		Parses the command line arguments for the Covert Channel and returns the settings to run the specific covert channel.
		'''
		parser = optparse.OptionParser()

		parser.add_option(
		'-r',
		'--role',
		help='specify the sender or the receiving role of the script: {sender|receiver}',
		action='store',
		type='string',
		dest='role')

		parser.add_option(
		'-f',
		'--file',
		help='specify the file which shall be read and exfiltrated',
		action='store',
		type='string',
		dest='filepath')

		parser.add_option(
		'-p',
		'--consecutive_clean',
		help='specify the number of clean packets inserted before/after stegopackets (default: 0)',
		default=0,
		action='store',
		type='int',
		dest='consecutive_clean')

		parser.add_option(
		'-l',
		'--consecutive_stego',
		help='specify the burst length of stegopackets (default: 0)',
		default=0,
		action='store',
		type='int',
		dest='consecutive_stego')

		settings, args = parser.parse_args(argv)

		if settings.filepath is None:
			raise ValueError("ValueError: filepath must be specified!")

		if settings.role not in ["sender", "receiver"]:
			raise ValueError("ValueError: role can be only sender or receiver!")

		if settings.consecutive_clean != 0 and settings.consecutive_stego == 0 or settings.consecutive_clean == 0 and settings.consecutive_stego != 0:
			print("settings.consecutive_clean and settings.consecutive_stego are set to 0!")
			settings.consecutive_clean = 0
			settings.consecutive_stego = 0
		
		return settings, args

	def __str__(self):
		return str(self.__dict__)

if __name__ == "__main__":

	settings, args = Flow_Label_CC.process_command_line(sys.argv)
	flow_label_cc = Flow_Label_CC(helper.read_binary_file_and_return_chunks(settings.filepath, \
		helper.IPv6_HEADER_FIELD_LENGTHS_IN_BITS["Flow Label"], \
		character_stuffing=True, \
		escape_value=Flow_Label_CC.END_MAGIC_VALUE), \
		settings.role, settings.consecutive_clean, \
		settings.consecutive_stego)
	if flow_label_cc.role == 'sender':
		helper.append_ip6tables_rule(sender=True)
		flow_label_cc.print_start_message()
		flow_label_cc.start_sending()
		helper.delete_ip6tables_rule(sender=True)
	elif flow_label_cc.role == 'receiver':
		helper.append_ip6tables_rule(sender=False)
		flow_label_cc.print_start_message()
		flow_label_cc.start_receiving()
		helper.delete_ip6tables_rule(sender=False)

