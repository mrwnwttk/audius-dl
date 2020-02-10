# sudo apt-get install python3-joblib
import os
import sys
import json
import shutil
import urllib
import urllib.parse
import requests
import subprocess
from joblib import Parallel, delayed
from mutagen.mp3 import EasyMP3
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, APIC, TIT2, TALB, TPE1, TPE2, COMM, USLT, TCOM, TCON, TDRC

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
	print("\033[K", "Fragment: [{}/{}]".format(i, len(data['data'][0]['track_segments'])), "\r", end='')
	sys.stdout.flush()
	urllib.request.urlretrieve("https://ipfs.io/ipfs/" + data['data'][0]['track_segments'][i]['multihash'], "dl/" + "{:04d}".format(i))

link = input("Please enter a link: ")

link_array = link.split("/")
account = link_array[3]
track_id = link_array[4].split("-")
track_id = track_id[-1]
title = link_array[4]
title = urllib.parse.unquote(title)
title = title [:-(len(track_id) + 1)]
#print(title)

curl_string = "curl --silent 'https://discoveryprovider3.audius.co/tracks_including_unlisted' -H 'authority: discoveryprovider3.audius.co' -H 'accept: application/json, text/plain, */*' -H 'origin: https://audius.co' -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36' -H 'content-type: application/json;charset=UTF-8' -H 'sec-fetch-site: same-site' -H 'sec-fetch-mode: cors' -H 'referer: " + link + "' -H 'accept-encoding: gzip, deflate, br' -H 'accept-language: en-US,en;q=0.9' --data-binary '{\"tracks\":[{\"id\":" + str(track_id) + ",\"url_title\":\""+ title + "\",\"handle\":\"" + account + "\"}]}' --compressed > dl.txt"
os.system(curl_string)
try:
	os.mkdir("dl")
except:
	pass

with open("dl.txt") as f:
	data = json.loads(f.read())
	print("Number of fragments: {}".format(len(data['data'][0]['track_segments'])))
	Parallel(n_jobs=8)(delayed(download_fragment)(data,i) for i in range(len(data['data'][0]['track_segments'])))
	print("")

os.chdir("dl")
os.system("cat * | ffmpeg -y -i pipe: -c:a copy \"{}.m4a\" -loglevel panic".format(title, title))
os.system("mv \"{}.m4a\" ../\"{}.m4a\"".format(title, title))
os.chdir("..")
os.system("rm -rf dl/")
os.system("mv \"{}.m4a\" \"{}.m4a\"".format(title, data['data'][0]['title']))
os.system("rm dl.txt")

# Get cover and set cover flag
cover_url = "https://ipfs.io/ipfs/" + data['data'][0]['cover_art_sizes'] + "/original.jpg"
try: 
	urllib.request.urlretrieve(cover_url, "cover.jpg")
	cover_flag = 1
except:
	cover_flag = 0

# Get description
try:
	description = data['data'][0]['description']
except:
	description = ""


add_tags(data['data'][0]['title'], data['data'][0]['title'], get_artist_name(account), description, 1)

try:
	os.mkdir("Files")
except:
	pass
os.system("mv *.m4a Files/")