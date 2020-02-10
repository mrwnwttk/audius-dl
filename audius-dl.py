import os
import re
import ssl
import sys
import json
import time
import shutil
import urllib
import urllib.parse
import argparse
import requests
import platform
import tempfile
import subprocess

link = input("Please enter a link: ")

link_array = link.split("/")
account = link_array[3]
track_id = link_array[4].split("-")
track_id = track_id[-1]
title = link_array[4]
title = urllib.parse.unquote(title)
title = title [:-(len(track_id) + 1)]

curl_string = "curl 'https://discoveryprovider3.audius.co/tracks_including_unlisted' -H 'authority: discoveryprovider3.audius.co' -H 'accept: application/json, text/plain, */*' -H 'origin: https://audius.co' -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36' -H 'content-type: application/json;charset=UTF-8' -H 'sec-fetch-site: same-site' -H 'sec-fetch-mode: cors' -H 'referer: " + link + "' -H 'accept-encoding: gzip, deflate, br' -H 'accept-language: en-US,en;q=0.9' --data-binary '{\"tracks\":[{\"id\":" + str(track_id) + ",\"url_title\":\""+ title + "\",\"handle\":\"" + account + "\"}]}' --compressed > dl.txt"
os.system(curl_string)
try:
	os.mkdir("dl")
except:
	pass
with open("dl.txt") as f:
    data = json.loads(f.read())
    for i in range(len(data['data'][0]['track_segments'])):
    	url = data['data'][0]['track_segments'][i]['multihash']
    	print(url)
    	urllib.request.urlretrieve("https://ipfs.io/ipfs/" + url, "dl/" + str(i))

os.chdir("dl")
os.system(("cat * | ffmpeg -y -i pipe: -c:a copy {}.m4a".format(title)))
os.system("mv {}.m4a ../{}.m4a".format(title, title))
os.system("cd ..; rm -rf dl/")
