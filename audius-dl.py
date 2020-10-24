import re
import os
import io
import sys
import json
import requests
import urllib.parse
import shutil
from joblib import Parallel, delayed
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, APIC, TIT2, TALB, TPE1, TPE2, COMM, USLT, TCOM, TCON, TDRC
import subprocess

import multiprocessing

def fix_filename(filename):
	return re.sub(r'[\/\*\<\?\>\|]', '-', filename)

def get_artist_name(account):
	username_json = requests.get("https://discoveryprovider3.audius.co/users?handle=" + account + "&limit=1&offset=0")
	username_json = json.loads(username_json.content)
	return username_json['data'][0]['name']

def add_tags(filename, title, artist, description, cover_flag):
		tags = MP4(filename + ".m4a").tags
		if description != None:
			tags["desc"] = description
		tags["\xa9nam"] = title
		tags["\xa9alb"] = "Audius"
		tags["\xa9ART"] = artist

		if cover_flag == 1:
			with open("cover.jpg", "rb") as f:
				tags["covr"] = [
					MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)
				]
		tags.save(filename + ".m4a")

def download_fragment(url, i):
	global segments_arr
	print("\033[K", "Fragment: [{}/{}]".format(i + 1, len(data['data'][0]['track_segments'])), "\r", end='')
	sys.stdout.flush()
	segments_arr[i] = requests.get("https://creatornode.audius.co/ipfs/" + data['data'][0]['track_segments'][i]['multihash']).content

link = input("Please enter a link: ")

link_array = link.split("/")
account = link_array[3]
track_id = (link_array[4].split("-"))[-1]

title = urllib.parse.unquote(link_array[4])
title = title [:-(len(track_id) + 1)]
title = title.replace('"', '\"')
title = urllib.parse.quote(title)
#title = "%22mvinline-svn%22"

headers = {
    'content-type': 'application/json;charset=UTF-8',
    'referer': link,
}

data = '{"tracks":[{"id":' + str(track_id) + ',"url_title":"' + str(title.replace('"', '\"')) + '","handle":"' + str(account) + '"}]}'
r = requests.post('https://discoveryprovider3.audius.co/tracks_including_unlisted', headers=headers, data=data)

data = json.loads(r.text)

print("Number of fragments: {}".format(len(data['data'][0]['track_segments'])))
manager = multiprocessing.Manager()
segments_arr = manager.list([None] * len(data['data'][0]['track_segments']))

Parallel(n_jobs=16)(delayed(download_fragment)(data,i) for i in range(len(data['data'][0]['track_segments'])))
all_seg = b''.join(segments_arr)

print("")
p = subprocess.Popen(["ffmpeg", "-y", "-i", "pipe:", "-c:a", "copy", f"{track_id}.m4a"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
grep_stdout = p.communicate(input=all_seg)[0]

#print(grep_stdout.decode())

# Get cover and set cover flag
try: 
	urllib.request.urlretrieve("https://creatornode.audius.co/ipfs/" + data['data'][0]['cover_art_sizes'] + "/1000x1000.jpg", "cover.jpg")
	cover_flag = 1
except:
	cover_flag = 0

# Get description
try:
	description = data['data'][0]['description']
except:
	description = ""


add_tags(track_id, data['data'][0]['title'], get_artist_name(account), description, 1)

#os.system("mv \"{}.m4a\" \"{}.m4a\"".format(track_id, fix_filename(data['data'][0]['title'])))
shutil.move(f"{track_id}.m4a", f"{fix_filename(data['data'][0]['title'])}.m4a")
try:
	os.mkdir("Files")
except:
	pass
os.system("mv *.m4a Files/")
os.remove("cover.jpg")

print("Done!")