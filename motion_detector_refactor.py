# USAGE
# python motion_detector.py
# python motion_detector.py --video videos/example_01.mp4

# import the necessary packages
import argparse
from threading import Thread
import datetime
import imutils
import time
import cv2
import json
import pprint
import numpy
import math
import sys
import select
import subprocess
import tty
import termios
import os
import signal

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", help="path to the video file")
ap.add_argument("-u", "--show-video", action="store_true")
ap.add_argument("-a", "--min-area", type=int, default=1000, help="minimum area size")
ap.add_argument("-m", "--max-area", type=int, default=11500, help="maximum area size")
ap.add_argument("-b", "--blend-rate", type=int, default=3, help="background image blend rate. Higher is faster")
ap.add_argument("-f", "--filename", type=str, default="motion_%Y-%m-%d_%H-%M-%S", help="strftime() string to use for capture file names")
ap.add_argument("-c", "--codec", type=str, default="XVID", help="Codec to use for output videos")
ap.add_argument("-l", "--motion-buffer", type=int, default=20, help="number of frames to capture after movement ends")
ap.add_argument("-j", "--polygon-json", default="zones.json", help="Polygon zones file")
ap.add_argument("-d", "--debug", action="store_true", help="Debug image stream and polygons")
ap.add_argument("-r", "--resolution", type=float, default=1.0, help="Resolution multiplier. Use to reduce CPU utilization.")
ap.add_argument("-p", "--filepath", type=str, default="/motiondata/motioneye/Camera1/%Y-%m-%d/", help="Folder path to store screenshots and video. In strftime format.")
ap.add_argument("-M", "--max-hitseconds", type=int, default=20, help="The maximum amount of time before forcing a keyframe reset. Does not interrupt active events.")
ap.add_argument("-z", "--zabbix-server", type=str, default="192.168.6.6", help="The zabbix server to send events to")
ap.add_argument("-H", "--zabbix-name", type=str, default="Front Camera", help="The name of the zabbix item to report events under")
args = vars(ap.parse_args())

# Define some proper exit strategies
def unix_hard_exit():
	os.kill(os.getpid(), signal.SIGKILL)

def sigint_unix_hard_exit_handler(signal, frame):
	unix_hard_exit()

def install_hard_ctrl_c():
	signal.signal(signal.SIGINT, sigint_unix_hard_exit_handler)
 
class FrameCounter:
	def __init__(self):
		# store the start time, end time, and total number of frames
		# that were examined between the start and end intervals
		self._start = None
		self._end = None
		self._numFrames = 0
 
	def start(self):
		# start the timer
		self._start = datetime.datetime.now()
		return self
 
	def update(self):
		# increment the total number of frames examined during the
		# start and end intervals
		self._numFrames += 1

	def elapsed(self):
		# return the total number of seconds between the start and
		# end interval
		return (datetime.datetime.now() - self._start).total_seconds()
 
	def fps(self):
		# compute the (approximate) frames per second
		return self._numFrames / self.elapsed()

class ThreadedStream:
	def __init__(self, video):
		self.frame = False
		self.stopped = False

		self.stream = cv2.VideoCapture(video)
		(self.success, self.frame) = self.stream.read()

	def start(self):
		Thread(target=self.update, args=()).start()
		return self
 
	def update(self):
		# keep looping infinitely until the thread is stopped
		while True:
			# if the thread indicator variable is set, stop the thread
			if self.stopped:
				return
 
			# otherwise, read the next frame from the stream
			(self.success, self.frame) = self.stream.read()
 
	def read(self):
		# return the frame most recently read
		frame = self.frame
		self.frame = False
		return frame
 
	def stop(self):
		# indicate that the thread should be stopped
		self.stopped = True

class ZoneState:
	def __init__(self):
		self.state = 0
		self.count = ZoneCount()
		self.changed_to_active = False

class ZoneCount:
	def __init__(self):
		self.hit = 0
		self.miss = 0

class Zone:
	# States:
	INACTIVE = 0
	MONITOR = 1
	ACTIVE = 2
	COOLDOWN = 3
	CONTINUATION = 4

	# Frame states:
	NONE = 0
	HIT = 1

	def __init__(self, zone_attrs, resolution):
		self.attrs = zone_attrs
		points = []
		for point in zone_attrs['points']:
			points.append([point['x'] * resolution, point['y'] * resolution])

		self.poly = numpy.array(points, dtype=numpy.int32)
		self.frame = self.NONE
		self.changed_to_active = False
		self.state = ZoneState()
	
	# Test if a given point is within this zone.
	def containsPoint(self, x, y):
		return cv2.pointPolygonTest(self.poly, (x, y), False) < 0

	# Compare boundingRect(contour) + center(x, y) to zone requirements
	def registerObject(self, x, y, w, h, cx, cy, cArea, fps):

		self.changed_to_active = False

		# Make sure the contour center is within the zone
		if not self.containsPoint(cx, cy):
			return False

		# Make sure it meets the minimum size requirements
		if w < int(self.attrs['minimum_x']) or h < int(self.attrs['minimum_y']):
			#print("Saw something in zone [" + self.attrs['name'] + "], but it wasn't big enough (" + str(w) + " < " + str(self.attrs['minimum_x']) + " || " + str(h) + " < " + str(self.attrs['minimum_y']) + ")")
			return False
		
		# It's a hit. Act accordingly, but only allow one hit per frame.
		if self.frame is self.HIT:
			return self.state.state

		self.state.changed_to_active = False
		self.frame = self.HIT
		self.state.count.hit += 1
		#print(self.attrs['name'] + " hit: " + str(self.state.count.hit))

		if self.state.state is self.INACTIVE:
			Notify().notifyMonitor(self)
			self.state.state = self.MONITOR
			
			# Set the FPS to avoid rehits:
			self.state.fps = fps

			return self.state.state

		if self.state.state is self.MONITOR:
			if self.state.count.hit < int(self.attrs['warmup']) * int(self.state.fps):
				#print(str(self.state.count.hit) + " < " + str(int(self.attrs['warmup']) * int(self.state.fps)))
				if self.state.count.hit is 1:
					Notify().notifyMonitor(self)

				self.state.state = self.MONITOR

			if self.state.count.hit >= int(self.attrs['warmup']) * int(self.state.fps):
				self.state.count.hit = 0
				Notify().notifyActive(self)
				self.state.changed_to_active = True
				self.state.state = self.ACTIVE

			return self.state.state

		if self.state.state is self.COOLDOWN:
			if self.state.count.hit >= int(self.attrs['continuation']):
				self.state.count.hit = 0
				self.state.count.miss = 0
				Notify().notifyActive(self)
				self.state.state = self.ACTIVE

			else:
				Notify().notifyContinue(self)
				self.state.state = self.CONTINUATION

			return self.state.state

		if self.state.state is self.CONTINUATION:
			if self.state.count.hit >= int(self.attrs['continuation']):
				self.state.count.hit = 0
				self.state.count.miss = 0
				Notify().notifyActive(self)
				self.state.state = self.ACTIVE

			return self.state.state

		return "WTF?"

	# What to do if not hit during a frame.
	def endFrame(self):
		# Handle the changed_to_active variable
		if self.state.changed_to_active is True:
			self.changed_to_active = True

		self.state.changed_to_active is False
		# Set the hit to false in preparation for a new frame
		self.state.frame_has_hit = False
		if self.frame is self.HIT:
			self.frame = self.NONE
			return self.state.state

		if self.state.state is self.INACTIVE:
			return self.state.state

		self.state.count.miss += 1
		if self.state.state is self.MONITOR:
			self.state.count.hit = 0
			self.state.count.miss = 0
			Notify().notifyInactive(self)
			self.state.state = self.INACTIVE

			return self.state.state

		if self.state.state is self.ACTIVE:
			if self.state.count.miss >= int(self.attrs['cooldown']) * self.state.fps:
				self.state.count.hit = 0
				self.state.count.miss = 0
				Notify().notifyInactive(self)
				self.state.state = self.INACTIVE

			else:
				Notify().notifyCooldown(self)
				self.state.state = self.COOLDOWN

			return self.state.state

		if self.state.state is self.COOLDOWN:
			if self.state.count.miss >= int(self.attrs['cooldown']) * self.state.fps:
				self.state.count.hit = 0
				self.state.count.miss = 0
				Notify().notifyInactive(self)
				self.state.state = self.INACTIVE

			else:
				self.state.state = self.COOLDOWN

			return self.state.state

		if self.state.state is self.CONTINUATION:
			if self.state.count.miss >= int(self.attrs['cooldown']) * self.state.fps:
				self.state.count.hit = 0
				self.state.count.miss = 0
				Notify().notifyInactive(self)
				self.state.state = self.INACTIVE

			else:
				Notify().notifyCooldown(self)
				self.state.state = self.COOLDOWN

			return self.state.state

		return "WTF2?"

class Frame:
	def __init__(self, video, resolution):
		self.captureStream = ThreadedStream(video=video).start()
		self.resolution = resolution
		self.counter = FrameCounter()
		self.fullWidth = 0
		self.fullHeight = 0

		self.opencv_frame = None
		self.frame = None
		self.reduced = None
		self.blur = None

	def next(self):
		self.opencv_frame = self.captureStream.read()
		while not type(self.opencv_frame) is numpy.ndarray:
			time.sleep(0.01)
			self.opencv_frame = self.captureStream.read()

		self.frame = self.opencv_frame
		if self.fullHeight is 0 or self.fullWidth is 0:
			(self.fullHeight, self.fullWidth) = self.frame.shape[:2]
			self.counter.start()
			print("Capture started")

		self.reduced = None
		self.blur = None

		self.counter.update()
		return self.frame

	def fps(self):
		return self.counter.fps()

	def reduceFrame(self):
		if self.reduced is None:
			self.reduced = cv2.resize(self.opencv_frame, (int(math.floor(self.fullWidth * self.resolution)), int(math.floor(self.fullHeight * self.resolution))))

		return self.reduced

	def blurFrame(self):
		if self.blur is None:
			self.blur = cv2.cvtColor(self.reduceFrame(), cv2.COLOR_BGR2GRAY)
			self.blur = cv2.GaussianBlur(self.blur, (21, 21), 0)
		
		return self.blur

	# Convert a downsampled point to it's full resolution location
	def pointToOriginalResolution(self, x, y):
		return (int(math.floor(x * 1.0 / self.resolution)), int(math.floor(y *  1.0 / self.resolution)))

	def getContoursDifferentTo(self, key_frame):	
		diff = cv2.threshold(cv2.absdiff(key_frame, self.blurFrame()), 25, 255, cv2.THRESH_BINARY)[1]
		diff = cv2.dilate(diff, None, iterations=2)
		(_, contours, _) = cv2.findContours(diff.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
		return contours

	def adaptToFrame(self, key_frame, blend_rate):
		return cv2.addWeighted(key_frame, blend_rate, self.blurFrame(), 1.00 - blend_rate, 0)

	def drawContourBox(self, x, y, w, h, cx, cy, cArea):
		self.frame = cv2.circle(self.frame, self.pointToOriginalResolution(cx, cy), 1, (0, 0, 255), 1)
		self.frame = cv2.rectangle(self.frame, self.pointToOriginalResolution(x, y), self.pointToOriginalResolution(x + w, y + h), (0, 255, 0), 1)
		self.frame = cv2.putText(self.frame, str(cArea / self.resolution / self.resolution), self.pointToOriginalResolution(x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

	def drawStatusLists(self, zones, fps):
		y = self.fullHeight - (len(zones) * 32) - 20
		for name in zones:
			y += 32
			if zones[name].state.state is 0:
				self.frame = cv2.putText(self.frame, name + ": Inactive", (20, y), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (255, 0, 0), 2, 16)

			if zones[name].state.state is 1:
				self.frame = cv2.putText(self.frame, name + ": Monitor", (20, y), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 174, 255), 2, 16)
				self.drawProgressBar(350, y, 300, 22, zones[name].state.count.hit, int(zones[name].attrs['warmup']) * int(math.floor(self.fps())), (0, 174, 255))

			if zones[name].state.state is 2:
				self.frame = cv2.putText(self.frame, name + ": Active", (20, y), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 0, 255), 2, 16)

			if zones[name].state.state is 3:
				self.frame = cv2.putText(self.frame, name + ": Cooldown", (20, y), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (127, 255, 0), 2, 16)
				self.drawProgressBar(350, y, 300, 22, zones[name].state.count.miss, int(zones[name].attrs['cooldown']) * int(math.floor(self.fps())), (127, 255, 0))

			if zones[name].state.state is 4:
				self.frame = cv2.putText(self.frame, name + ": Continuation", (20, y), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (195, 0, 255), 2, 16)
				self.drawProgressBar(350, y, 300, 22, zones[name].state.count.hit, int(zones[name].attrs['continuation']), (195, 0, 255))

	def drawProgressBar(self, x, y, w, h, current, maximum, color):
		self.frame = cv2.rectangle(self.frame, (x, y - h), (x + w, y), (color), 1)

		if current > maximum:
			current = maximum

		w = int(math.floor(float(w) / float(maximum) * float(current)))
		self.frame = cv2.rectangle(self.frame, (int(math.floor(x)), int(math.floor(y - h))), (int(math.floor(x + w)), int(math.floor(y + 2))), (color), -1)

	def putDateTime(self):
		cv2.putText(self.frame, datetime.datetime.now().strftime("%m/%d/%Y %H:%M:%S"), (20, 90), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (255, 255, 255), 2)

class MotionTracker:
	def __init__(self, settings):
		self.resolution = 1.0
		self.settings = settings
		if settings['resolution'] < 1.0:
			self.resolution = settings['resolution']

		# Set the frame source and get the key_frame
		self.frame = Frame(settings['video'], self.resolution)
		self.frame.next()
		self.key_frame = self.frame.blurFrame()
		cv2.imwrite("/motiondata/last_keyframe.jpg", self.key_frame)

		self.to_original = 1.0 / self.resolution
		self.blend_rate = 1.00 - (settings['blend_rate'] / float(100))
		self.codec = cv2.VideoWriter_fourcc(*args["codec"])

		self.fps = 20
		self.zones = {}
		self.lists = {}
		self.has_active_zone = False
		self.snapshot = False
		self.upload_snapshot = False
		self.last_snapshot = None
		self.recording = False
		self.recorded_frames = 0
		self.output = None

		zones = json.loads(open(args['polygon_json'], 'r').read())
		for zone in zones['zones']:
			self.zones.update({str(zones['zones'][zone]['name']): Zone(zones['zones'][zone], self.resolution)})

		if not zones['s3_bucket'] is None:
			self.settings['s3_bucket'] = zones['s3_bucket']

	def resetZabbixItems(self):
		for name in self.zones:
			Notify().sendZabbixValue("mrec." + name.lower(), 0)
			Notify().sendZabbixValue("mdect." + name.lower(), 0)

	# Get the next frame from the camera
	def getNextFrame(self):
		# Reset the lists and temporary variables;
		self.has_active_zone = False
		self.lists = {'inactive': [], 'monitor': [], 'active': [], 'cooldown': [], 'continuation': []}

		self.snapshot = False
		self.frame.next()

		return True

	# Returns the members of a list as a comma delimeted string
	def getListString(list_name):
		text = "";
		for (name, value) in self.lists[list_name].iteritems():
			text += name + ", "

		return text[:-2];

	def processCurrentFrame(self):
		contours = self.frame.getContoursDifferentTo(self.key_frame);

		for contour in contours:	
			# Ignore small contours
			cArea = cv2.contourArea(contour)
			if cArea < self.settings["min_area"] * self.resolution * self.resolution:
				continue

			# Contour is big enough. Draw the boundingRect and calculate the center of motion.
			(x, y, w, h) = cv2.boundingRect(contour)
			cx = x + (w / 2)
			cy = y + (h / 2)

			self.frame.drawContourBox(x, y, w, h, cx, cy, cArea)
			for name in self.zones:
				self.zones[name].registerObject(x, y, w, h, cx, cy, cArea, self.fps)
				if self.zones[name].state.state >= 2:
					self.has_active_zone = True

				if self.zones[name].state.changed_to_active is True:
					if self.zones[name].attrs['upload_to_s3'] is True:
						self.upload_snapshot = True

					self.snapshot = True

	def endCurrentFrame(self):
		for name in self.zones:
			state = self.zones[name].endFrame()
			if state >= 2:
				self.has_active_zone = True

			'''
			if state is 0:
				self.lists['inactive'].append(name)

			if state is 1:
				self.lists['monitor'].append(name)

			if state is 2:
				self.lists['active'].append(name)

			if state is 3:
				self.lists['cooldown'].append(name)

			if state is 4:
				self.lists['continuation'].append(name)
			'''

	def run(self):
		install_hard_ctrl_c()
		while (self.getNextFrame()):
			self.processCurrentFrame()
			self.endCurrentFrame()
			self.frame.drawStatusLists(self.zones, self.fps)
			self.frame.putDateTime()
			dt = datetime.datetime.now()

			if self.snapshot:
				name = dt.strftime(self.settings["filename"])
				if not self.last_snapshot == name:
					if os.path.isdir(dt.strftime(self.settings["filepath"])) is False:
						os.makedirs(dt.strftime(self.settings["filepath"]))

					path = dt.strftime(self.settings["filepath"])
					cv2.imwrite(path + name + ".jpg", self.frame.frame)

					if self.upload_snapshot:
						#print("### Would have Uploaded to S3 @ " + self.settings['s3_bucket'])
						p = subprocess.Popen("/motiondata/s3_upload.sh " + path + name + ".jpg s3://motion.aws.bradwoodward.io/", shell=True)

						self.upload_snapshot = False

					Notify().sendZabbixValue('mz.latest_snapshot', name + ".jpg")

					self.last_snapshot = name
				self.snapshot = False

			if self.has_active_zone is True:
				if self.recording is False:
					if os.path.isdir(dt.strftime(self.settings["filepath"])) is False:
						os.makedirs(dt.strftime(self.settings["filepath"]))

					path = dt.strftime(self.settings["filepath"])
					name = dt.strftime(self.settings["filename"])
					Notify().sendZabbixValue('mz.latest_video', name + ".avi")
					self.output = cv2.VideoWriter(path + name + ".avi", self.codec, math.floor(self.frame.fps()), (self.frame.fullWidth, self.frame.fullHeight))
					self.fps = self.frame.fps()
					self.recording = True

				self.output.write(self.frame.frame)
				self.recorded_frames += 1
				if self.recorded_frames % math.floor(self.settings['max_hitseconds'] * self.frame.fps()) < 1:
					Notify().notifyForceRekey()
					self.key_frame = self.frame.blurFrame()
				else:
					self.key_frame = self.frame.adaptToFrame(self.key_frame, self.blend_rate)

			if self.has_active_zone is False:
				if self.recording is True:
					self.output.release()
					self.output = None
					self.recording = False
					self.recorded_frames = 0
					Notify().notifyStopRecording()

			if int(dt.strftime("%S")) % 4 == 0:
				self.key_frame = self.frame.adaptToFrame(self.key_frame, self.blend_rate)


class Notify:
	def __init__(self):
		self.cmd = "/usr/bin/zabbix_sender -z " + mdect.settings['zabbix_server'] + " -s '" + mdect.settings['zabbix_name'] + "'"
		self.dt = datetime.datetime.now()

	def notifyForceRekey (self):
		print(self.dt.strftime("[%H:%M:%S] Forcing rekey of master frame"))
		return

	def notifyActive (self, zone):
		self.sendZabbixValue("mrec." + zone.attrs['name'].lower(), 1)
		print(self.dt.strftime("[%H:%M:%S] -- -O [" + zone.attrs['name'] + "]"))
		return

	def notifyMonitor (self, zone):
		self.sendZabbixValue("mdect." + zone.attrs['name'].lower(), 1)
		print(self.dt.strftime("[%H:%M:%S] ->    [" + zone.attrs['name'] + "]"))
		return

	def notifyCooldown (self, zone):
		self.sendZabbixValue("mdect." + zone.attrs['name'].lower(), 0)
		print(self.dt.strftime("[%H:%M:%S] -- -- [" + zone.attrs['name'] + "]"))
		return

	def notifyInactive (self, zone):
		self.sendZabbixValue("mdect." + zone.attrs['name'].lower(), 0)
		self.sendZabbixValue("mrec." + zone.attrs['name'].lower(), 0)
		print(self.dt.strftime("[%H:%M:%S] -X    [" + zone.attrs['name'] + "]"))
		return

	def notifyContinue(self, zone):
		print(self.dt.strftime("[%H:%M:%S] -- -> [" + zone.attrs['name'] + "]"))
		return

	def notifyStopRecording(self):
		print(self.dt.strftime("[%H:%M:%S] -X XX"))
		print("")
		return

	def sendZabbixValue(self, key, value):
		subprocess.check_output(self.cmd + " -k " + key + " -o " + str(value), shell=True)
		return

	def sendZabbixBoolFlip(self, key, new_value):
		old_value = math.fabs(new_value - 1)
		sendZabbixValue(key, old_value)
		sendZabbixValue(key, new_value)	

mdect = MotionTracker(args)
mdect.resetZabbixItems()
mdect.run()

'''
# loop over the frames of the video
	if event is 1:
		firstFrame = adaptKeyFrame(firstFrame, compare)
		cv2.putText(frame, "Record", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
		if output is None:
			(h, w) = frame.shape[:2]
			print(dt.strftime("[%H:%M:%S] -- -O Recording at {:.2f} FPS").format(counter.fps()))
			if os.path.isdir(dt.strftime(args["filepath"])) is False:
				os.makedirs(dt.strftime(args["filepath"]))

			name = dt.strftime(args["filepath"] + args["filename"]) + ".avi"
			sendZabbixValue("mz.latest_video", dt.strftime(args["filename"] + ".avi"))
			output = cv2.VideoWriter(name, fourcc, math.floor(counter.fps()), (w, h))
			if not output.isOpened():
				print("Error write")

		output.write(frame)

	if event is 0:
		cv2.putText(frame, "Monitor", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
		if not output is None:
			print(dt.strftime("[%H:%M:%S] XX XX"))
			print("")
			output.release
			output = None


	# reKey if not recording and not specifically supressed.
	if reKey is 1 and event is 0:
		firstFrame = compare

	# but still adapt the key if supressed:
	if reKey is 0:
		firstFrame = adaptKeyFrame(firstFrame, compare)

	# Show zones if debug = true
	if args['debug'] == True:
		for (name, poly) in polys.iteritems():
			cv2.drawContours(frame, [poly], 0, (0, 255, 0), 2)
'''