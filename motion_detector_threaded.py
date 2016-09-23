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

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", help="path to the video file")
ap.add_argument("-u", "--show-video", action="store_true")
ap.add_argument("-a", "--min-area", type=int, default=1500, help="minimum area size")
ap.add_argument("-m", "--max-area", type=int, default=11500, help="maximum area size")
ap.add_argument("-s", "--skip-frames", type=int, default=5, help="number of frames to skip when processing")
ap.add_argument("-b", "--blend-rate", type=int, default=3, help="background image blend rate. Higher is faster")
ap.add_argument("-f", "--filename", type=str, default="motion_%Y-%m-%d_%H-%M-%S", help="strftime() string to use for capture files")
ap.add_argument("-c", "--codec", type=str, default="XVID", help="Codec to use for output videos")
ap.add_argument("-l", "--motion-buffer", type=int, default=20, help="number of frames to capture after movement ends")
ap.add_argument("-j", "--polygon-json", default="zones.json", help="Polygon zones file")
ap.add_argument("-d", "--debug", action="store_true", help="Debug image stream and polygons")
ap.add_argument("-r", "--resolution", type=float, default=1.0, help="Resolution multiplier. Use to reduce CPU utilization.")


args = vars(ap.parse_args())
 
class frameCounter:
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
		# initialize the video camera stream and read the first frame
		# from the stream
		self.stream = cv2.VideoCapture(video)
		(self.success, self.frame) = self.stream.read()
 
		# initialize the variable used to indicate if the thread should
		# be stopped
		self.stopped = False

	def start(self):
		# start the thread to read frames from the video stream
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

# Pull in the JSON polygon file
f = open(args['polygon_json'], 'r')
text = f.read()
zones = json.loads(text)
zones = zones['zones']

resolution = 1.0
if (args['resolution'] < 1.0):
	resolution = args['resolution']

res_to_original = 1.0 / resolution

# Pull the zone point coordinates into 'polys' object.
polys = dict([])
resized_polys = dict([])
for zone in zones:
	points = []
	resized_points = []
	for point in zones[zone]['points']:
		points.append([point['x'], point['y']])
		resized_points.append([point['x'] * resolution, point['y'] * resolution])
	
	polys.update({zones[zone]['name']: numpy.array(points, dtype=numpy.int32)})
	resized_polys.update({zones[zone]['name']: numpy.array(resized_points, dtype=numpy.int32)})

camera = ThreadedStream(video=args['video']).start()

# initialize the necessary vars
lastFrame = None
firstFrame = None
output = None
frameSkip = 0
frameCount = 0
mFrameCount = args['motion_buffer']
beta = args["blend_rate"] / float(100)
alpha = 1.00 - beta
fourcc = cv2.cv.FOURCC(*args["codec"])

# initialize the active polys global objects
global polyActive
global polyActiveFrame
global alertPolys
global warningPolys
global cooldownPolys
global inactivePolys
global event
global reKey

polyActive = dict([])
polyActiveFrame = dict([])
alertPolys = dict([])
warningPolys = dict([])
cooldownPolys = dict([])
inactivePolys = dict([])
event = 0
reKey = 1

def reduceFrame( redFrame ):
	redFrame = cv2.cvtColor(redFrame, cv2.COLOR_BGR2GRAY)
	redFrame = cv2.GaussianBlur(redFrame, (21, 21), 0)
	return redFrame;

def to_orig( x, y ):
	return (int(math.floor(x * res_to_original)), int(math.floor(y * res_to_original)))

def getMotionContours( keyFrame, currentFrame ):	
	frameDiff = cv2.absdiff(keyFrame, currentFrame)
	thresh = cv2.threshold(frameDiff, 35, 255, cv2.THRESH_BINARY)[1]
	thresh = cv2.dilate(thresh, None, iterations=2)
	(cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	return (cnts, frameDiff);

def registerPolyMotion( point ):
	for (name, poly) in resized_polys.iteritems():
		polyHit = cv2.pointPolygonTest(poly, point, False)
		if polyHit >= 0:
			trackActivePolys("registerFrameHit", name)
	return;

def getZoneNamesList( zoneList ):
	text = "";
	for (name, value) in zoneList.iteritems():
		text += name + ", "

	return text[:-2];

def notifyHit ( zoneName ):
	print("Hit detected in zone: " + zoneName)
	filename = dt.strftime("/motiondata/motioneye/Camera1/%Y-%m-%d/" + args["filename"]) + ".jpg"
	pprint.pprint(filename)
	cv2.imwrite(filename, frame)
	return;

def notifyContinue( zoneId ):
	i = zoneId
	return;

def adaptKeyFrame( keyFrame, currentFrame ):
	keyFrame = cv2.addWeighted(keyFrame, alpha, currentFrame, beta, 0)
	return keyFrame;

def trackActivePolys(action, name=None):
	# Use globals
	global polyActive
	global polyActiveFrame

	global alertPolys
	global warningPolys
	global cooldownPolys
	global inactivePolys
	global event
	global reKey

	if action is "digest":

		# Reset the registers
		event = 0
		reKey = 1
		alertPolys = dict([])
		warningPolys = dict([])
		cooldownPolys = dict([])
		inactivePolys = dict([])

		for zone in zones:
			zone = str(zone)
			name = zones[zone]['name']

			if name in polyActiveFrame:
				if polyActive[name]['hit'] < int(zones[zone]['warmup']) * counter.fps():
					warningPolys[name] = 1

					# Suppress reKeying when warning is active.
					reKey = 0
				else:
					if polyActive[name]['hit'] < (int(zones[zone]['warmup']) * counter.fps()) + 1:
						notifyHit(name)

					event = 1
					alertPolys[name] = 1

			elif name in polyActive:
				polyActive[name]['miss'] += 1
				if polyActive[name]['miss'] < int(zones[zone]['cooldown']) * counter.fps():

					# Cooldown is only an event if warmup was already surpassed, but should always supress reKeying.
					reKey = 0
					if polyActive[name]['hit'] > int(zones[zone]['warmup']) * counter.fps():
						event = 1

					cooldownPolys[name] = 1
				else:
					del polyActive[name]
					inactivePolys[name] = 1

			else:
				inactivePolys[name] = 1

		polyActiveFrame = dict([]);
		return;

	# poly would be an int here.
	if action is "registerFrameHit" and not name is None:
		if not name in polyActive:
			polyActive[name] = {'hit': 0, 'miss': 0}

		polyActive[name]['hit'] += 1
		polyActive[name]['miss'] -= polyActive[name]['miss']
		polyActiveFrame[name] = 1
		return;

	print("trackActivePolys called with no/invalid action or no poly");
	return;

# loop over the frames of the video
while True:

	capture = camera.read()
	if capture is False:
		#slow down a tad.
		time.sleep(0.03)
		continue;

	frame = capture

	if firstFrame is None:
		(orig_h, orig_w) = capture.shape[:2]

	capture = cv2.resize(capture, (int(math.floor(orig_w * resolution)), int(math.floor(orig_h * resolution))))
	compare = reduceFrame(capture)
	# Set the keyFrame, if it doesn't exist.
	if firstFrame is None:
		firstFrame = compare
		counter = frameCounter().start()
		continue

	counter.update()

	# Get the contours compared to the keyFrame
	(cnts, frameDiff) = getMotionContours(firstFrame, compare)

	# loop over those contours
	for c in cnts:
		# Ignore small contours
		cArea = cv2.contourArea(c)
		if cArea < args["min_area"] * resolution:
			continue

		# Contour is big enough. Draw the boundingRect and calculate the center of motion.
		(x, y, w, h) = cv2.boundingRect(c)
		center_x = x + (w / 2)
		center_y = y + (h / 2)

		# See if the contour center is within a defined zone
		registerPolyMotion((center_x, center_y))

		# Draw the center
		cv2.circle(frame, to_orig(center_x, center_y), 1, (0, 0, 255), 1)
		cv2.rectangle(frame, to_orig(x, y), to_orig(x + w, y + h), (0, 255, 0), 1)
		cv2.putText(frame, str(cArea), to_orig(x - 5, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

	trackActivePolys("digest");
	dt = datetime.datetime.now()

	textY = 110;
	if len(alertPolys) > 0:
		cv2.putText(frame, "Alert: " + getZoneNamesList(alertPolys), (20, textY), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
		textY += 20

	if len(warningPolys) > 0:
		cv2.putText(frame, "Warning: " + getZoneNamesList(warningPolys), (20, textY), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 195, 255), 1)
		textY += 20

	if len(cooldownPolys) > 0:
		cv2.putText(frame, "Cooldown: " + getZoneNamesList(cooldownPolys), (20, textY), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
		textY += 20

	cv2.putText(frame, dt.strftime("%m/%d/%Y %H:%M:%S"), (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
	if event is 1:
		firstFrame = adaptKeyFrame(firstFrame, compare)
		cv2.putText(frame, "Record", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
		if output is None:
			(h, w) = frame.shape[:2]
			name = dt.strftime("/motiondata/motioneye/Camera1/%Y-%m-%d/" + args["filename"]) + ".avi"
			output = cv2.VideoWriter(name, fourcc, int(math.floor(counter.fps() * 0.7)), (w, h))
			if not output.isOpened():
				print("Error write")

		output.write(frame)

	if event is 0:
		cv2.putText(frame, "Monitor", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
		if not output is None:
			output.release

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
	
	# show the frame and record if the user presses a key

	if args['show_video'] is True:
		frame = cv2.resize(frame, (1280, 720))
		cv2.imshow("Live Feed", frame)
		#cv2.imshow("Keyframe", firstFrame)
		#cv2.imshow("Frame Delta", frameDiff)

		# if the `q` key is pressed, break from the lop
		key = cv2.waitKey(1) & 0xFF
		if key == ord("q"):
			break

		if key == ord('i'):
			print("[INFO] approx. FPS: {:.2f}".format(counter.fps()))

		if key == ord('p'):
			cv2.imwrite(dt.strftime(args["filename"]) + ".jpg", frame)

# cleanup the camera and close any open windows
camera.stop()
cv2.destroyAllWindows()
