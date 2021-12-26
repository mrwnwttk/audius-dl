import re
import os
import sys
import json
import time
import shutil
import requests
import subprocess
import urllib.parse
import multiprocessing
from hashids import Hashids
from joblib import Parallel, delayed
from mutagen.mp4 import MP4, MP4Cover

def fix_filename(filename):
	return re.sub(r'[\/\*\<\?\>\|\<\>\:]', '-', filename)

def uniquify(path):
    filename, extension = os.path.splitext(path)
    counter = 1
    while os.path.exists(path):
        path = filename + " (" + str(counter) + ")" + extension
        counter += 1
    return path

def add_tags(filename, title, artist, description, cover):
		tags = MP4(filename + ".m4a").tags
		if description != None:
			tags["desc"] = description
		tags["\xa9nam"] = title
		tags["\xa9alb"] = "Audius"
		tags["\xa9ART"] = artist

		if cover is not None:
			tags["covr"] = [
				MP4Cover(cover[:], imageformat=MP4Cover.FORMAT_JPEG)
			]
		tags.save(filename + ".m4a")

def download_segment(data, i, endpoint):
	global segments_arr
	print("\033[K", "Segment: [{}/{}]".format(i + 1, len(data['data'][0]['track_segments'])), "\r", end='')
	sys.stdout.flush()
	segments_arr[i] = requests.get(f"{endpoint}/ipfs/" + data['data'][0]['track_segments'][i]['multihash']).content

def download_segment_api(data, i, endpoint):
	global segments_arr
	print("\033[K", "Segment: [{}/{}]".format(i + 1, len(data['data']['track_segments'])), "\r", end='')
	sys.stdout.flush()
	segments_arr[i] = requests.get(f"{endpoint}/ipfs/" + data['data']['track_segments'][i]['multihash']).content

def download_deleted_segment(data, i, endpoint):
	global segments_arr
	print("\033[K", "Segment: [{}/{}]".format(i + 1, len(data['track_segments'])), "\r", end='')
	sys.stdout.flush()
	segments_arr[i] = requests.get(f"{endpoint}/ipfs/" + data['track_segments'][i]['multihash']).content


def get_node_endpoint(track_id, endpoint):
	while(True):
		r = requests.get(f"{endpoint}/v1/full/tracks/{track_id}")
		if r.status_code == 200:
			j = json.loads(r.text)
			endpoints = (j['data']['user']['creator_node_endpoint']).split(',')
			return endpoints
		time.sleep(2)

def get_available_endpoint():
	while(True):
		try:
			r = requests.get('https://api.audius.co')
			j = json.loads(r.text)
			return j['data'][0]
		except:
			print("Error occurred while contacting api.audius.co! Trying again in two seconds...")
			time.sleep(2)

def resolve_link(link, endpoint):
	while True:
		try:
			headers = {
				'Accept': 'text/plain'
			}
			
			r = requests.get(f'{endpoint}/v1/resolve', params = { 'url': link }, headers = headers)

			if r.status_code == 200:
				return r.text
			elif r.status_code == 404:
				print("Returned 404, can't download!")
				exit()
			else:
				time.sleep(2)
		except:
			print("An exception occurred while trying to resolve the link, trying again in two seconds...")
			time.sleep(2)
def get_permalink_for_track(id):
	r = requests.get(f'https://audius.co/tracks/{id}')
	return r.url

def get_info_from_permalink(link):
	link_array = link.split("/")
	account = link_array[3]
	# track_id = (link_array[4].split("-"))[-1]

	title = urllib.parse.unquote(link_array[4])
	title = title.replace('"', '\"')
	title = urllib.parse.quote(title)
	return title, account

def select_endpoint(node_endpoints, data):
	print("Checking for available enpoints...")

	working_enpoint_found = False

	for index, e in enumerate(node_endpoints):
		print(f"{e} - ", end='')
		if "error" in requests.get(f"{e}/ipfs/" + data['data'][0]['track_segments'][0]['multihash']).text:
			print("Failed!")
		else:
			print("Success!")
			working_enpoint_found = True
			break

	if working_enpoint_found:
		return index
	else:
		return -1

def download_single_track_from_permalink(link, folder_name=''):
	global segments_arr
	title, account = get_info_from_permalink(link)

	endpoint = get_available_endpoint()
	print(f"API endpoint: {endpoint}")

	# get track id
	u = endpoint + f"/v1/full/tracks?handle={account}&slug={title}"
	r = requests.get(endpoint + f"/v1/full/tracks?handle={account}&slug={title}").json()
	track_id = r["data"]["id"]

	hashids = Hashids(salt="azowernasdfoia", min_length=5)
	# actual track id
	track_id = str(hashids.decode(track_id)[0])

	headers = {
		'content-type': 'application/json;charset=UTF-8',
		'referer': link,
	}

	# Why did Boys Noize have to put " in their titles
	data = '{"tracks":[{"id":' + str(track_id) + ',"url_title":"' + str(title.replace('"', '\"')) + '","handle":"' + str(account) + '"}]}'
	r = requests.post(f'{endpoint}/tracks_including_unlisted', headers=headers, data=data)

	data = json.loads(r.text)

	print("Number of segments: {}".format(len(data['data'][0]['track_segments'])))
	segments_arr = manager.list([None] * len(data['data'][0]['track_segments']))

	r = resolve_link(link, endpoint)
	node_json = json.loads(r)

	node_endpoints = get_node_endpoint(node_json['data']['id'],endpoint)
	print(f"Node endpoints: {' / '.join(node_endpoints)}")

	# Check if the node has not blacklisted the files
	ret = select_endpoint(node_endpoints, data)

	if ret == -1:
		print("Not a single working endpoint found! Exiting...")
		exit()

	selected_node_endpoint = node_endpoints[ret]
	print(f"Selected node endpoint: {selected_node_endpoint}")

	Parallel(n_jobs=8)(delayed(download_segment)(data,i, selected_node_endpoint) for i in range(len(data['data'][0]['track_segments'])))
	all_seg = b''.join(segments_arr)

	global base_path
	os.chdir(base_path)
	try:
		os.mkdir("Files")
	except:
		pass
	os.chdir('Files')

	if folder_name != '':
		folder_name = fix_filename(folder_name)
		try:
			os.mkdir(folder_name)
		except:
			pass
		os.chdir(folder_name)

	p = subprocess.Popen(["ffmpeg", "-loglevel", "panic", "-stats", "-y", "-i", "pipe:", "-c:a", "copy", f"{track_id}.m4a"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
	grep_stdout = p.communicate(input=all_seg)[0]

	print("\n" + (grep_stdout.decode()).rstrip())


	cover = None
	if node_json['data']['artwork'] is None:
		cover = None
	else:
		try:
			cover = requests.get(node_json['data']['artwork']['1000x1000']).content
		except:
			cover = None
	try:
		description = data['data'][0]['description']
	except:
		description = None

	add_tags(track_id, data['data'][0]['title'], node_json['data']['user']['name'], description, cover)
	shutil.move(f"{track_id}.m4a", f"{fix_filename(data['data'][0]['title'])}.m4a")
	print("Done!")

def download_single_track_from_api(track_id, folder_name=''):
	global segments_arr

	endpoint = get_available_endpoint()
	print(f"API endpoint: {endpoint}")

	r = requests.get(f"{endpoint}/v1/full/tracks/" + track_id)
	data = json.loads(r.text)

	while(True):
		try:
			node_endpoints = get_node_endpoint(data['data']['id'], endpoint)
			break
		except:
			print("Failed to get endpoint! Trying again in five seconds!")
			time.sleep(5)
		

	print(f"Node endpoints: {' / '.join(node_endpoints)}")
	selected_node_endpoint = node_endpoints[0]
	print(f"Selected node endpoint: {selected_node_endpoint}")

	print("Number of segments: {}".format(len(data['data']['track_segments'])))
	segments_arr = manager.list([None] * len(data['data']['track_segments']))

	Parallel(n_jobs=8)(delayed(download_segment_api)(data, i, selected_node_endpoint) for i in range(len(data['data']['track_segments'])))
	all_seg = b''.join(segments_arr)

	global base_path
	os.chdir(base_path)
	try:
		os.mkdir("Files")
	except:
		pass
	os.chdir('Files')

	if folder_name != '':
		folder_name = fix_filename(folder_name)
		try:
			os.mkdir(folder_name)
		except:
			pass
		os.chdir(folder_name)

	track_id = data['data']['id']
	p = subprocess.Popen(["ffmpeg", "-loglevel", "panic", "-stats", "-y", "-i", "pipe:", "-c:a", "copy", f"{track_id}.m4a"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
	grep_stdout = p.communicate(input=all_seg)[0]

	print("\n" + (grep_stdout.decode()).rstrip())


	cover = None
	if data['data']['artwork'] is None:
		cover = None
	else:
		try:
			cover = requests.get(data['data']['artwork']['1000x1000']).content
		except:
			cover = None

	try:
		description = data['data']['description']
	except:
		description = None

	add_tags(track_id, data['data']['title'], data['data']['user']['name'], description, cover)
	shutil.move(f"{track_id}.m4a", uniquify(f"{fix_filename(data['data']['title'])}.m4a"))
	print("Done!")

def download_deleted_track(track_json, folder_name='', full_username=''):
	global segments_arr

	endpoint = get_available_endpoint()
	print(f"API endpoint: {endpoint}")

	# TODO: Provide API with list of all known creator nodes
	# Guess a working node endpoint which still has the segments of the track
	node_endpoint_list = ['https://creatornode.audius.co', 'https://creatornode2.audius.co', 'https://audius-content.nz.modulational.com']
	selected_node_endpoint = ""
	for n in node_endpoint_list:
		r = requests.get(f'{n}/ipfs/' + track_json['track_segments'][0]['multihash'])
		if r.status_code == 200:
			selected_node_endpoint = n
			break

	if selected_node_endpoint != "":
		print("Number of segments: {}".format(len(track_json['track_segments'])))
		segments_arr = manager.list([None] * len(track_json['track_segments']))

		Parallel(n_jobs=8)(delayed(download_deleted_segment)(track_json, i, selected_node_endpoint) for i in range(len(track_json['track_segments'])))
		all_seg = b''.join(segments_arr)

		global base_path
		os.chdir(base_path)
		try:
			os.mkdir("Files")
		except:
			pass
		os.chdir('Files')

		if folder_name != '':
			folder_name = fix_filename(folder_name)
			try:
				os.mkdir(folder_name)
			except:
				pass
			os.chdir(folder_name)

		track_id = str(track_json['track_id'])
		p = subprocess.Popen(["ffmpeg", "-loglevel", "panic", "-stats", "-y", "-i", "pipe:", "-c:a", "copy", f"{track_id}.m4a"], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.STDOUT)
		grep_stdout = p.communicate(input=all_seg)[0]

		print("\n" + (grep_stdout.decode()).rstrip())


		cover = None
		if track_json['cover_art'] is None:
			cover = None
		else:
			try:
				cover = requests.get(track_json['artwork']['1000x1000']).content
			except:
				cover = None

		try:
			description = track_json['description']
		except:
			description = None

		print(track_json['title'])
		add_tags(track_id, track_json['title'], full_username, description, cover)
		shutil.move(f"{track_id}.m4a", uniquify(f"{fix_filename(track_json['title'])}.m4a"))
		print("Done!")

def download_album(link):
	endpoint = get_available_endpoint()
	print(f"API endpoint: {endpoint}")

	res = resolve_link(link, endpoint)
	j = json.loads(res)
	user_id = j['data'][0]['user']['id']
	album_id = j['data'][0]['id']
	album_name = j['data'][0]['playlist_name']

	r = requests.get(f"{endpoint}/v1/full/playlists/{album_id}?user_id={user_id}")

	j = json.loads(r.text)
	for index, t in enumerate(j['data'][0]['tracks']):
		print(f"Track [ {index + 1} / {len(j['data'][0]['tracks'])} ]")
		download_single_track_from_api(t['id'], album_name)

def download_profile(link):
	endpoint = get_available_endpoint()
	print(f"API endpoint: {endpoint}")

	res = resolve_link(link, endpoint)
	j = json.loads(res)
	user_id = j['data']['id']
	username = j['data']['handle']

	# Get user info and number of tracks for said user
	user_track_count = j['data']['track_count']
	print(f"Total number of tracks: {user_track_count}")
	tracks = []

	# We only need to make a single request
	if user_track_count < 100:
		r = requests.get(f"{endpoint}/v1/users/{user_id}/tracks")
		j = json.loads(r.text)
		for t in j['data']:
			tracks.append(t['id'])	
	else:
		for offset in range(0, user_track_count, 100):
			r = requests.get(f"{endpoint}/v1/users/{user_id}/tracks?offset={offset}")
			j = json.loads(r.text)
			for t in j['data']:
				tracks.append(t['id'])

	print(f"Found {len(tracks)} track(s)!")

	for index, i in enumerate(tracks):
		print(f"Track [ {index + 1} / {len(tracks)} ]")
		download_single_track_from_api(i, username)

def download_profile_deleted_tracks(link):
	endpoint = get_available_endpoint()
	print(f"API endpoint: {endpoint}")

	res = resolve_link(link, endpoint)
	j = json.loads(res)
	user_id = j['data']['id']
	username = j['data']['handle']
	full_username = j['data']['name']

	# We want to be able to use the API to include deleted tracks, which means we can't use the User ID
	# provided by Audius, instead we have to get a little creative.

	# Get *actual* User ID
	# Uses https://hashids.org/python/
	# See https://audius.co/static/js/utils/route/hashIds.ts
	hashids = Hashids(salt="azowernasdfoia", min_length=5)
	actual_user_id = hashids.decode(user_id)[0]
	r = requests.get(f"{endpoint}/tracks?filter_deleted=false&limit=100&offset=0&user_id={actual_user_id}")
	j = json.loads(r.text)

	deleted_tracks = []

	for t in j['data']:
		if(t['is_delete']):
			deleted_tracks.append(t)
	print(f"Number of deleted tracks: {len(deleted_tracks)}")

	for index, i in enumerate(deleted_tracks):
		print(f"Track [ {index + 1} / {len(deleted_tracks)} ]")
		download_deleted_track(i, username, full_username)

def main():
	if len(sys.argv) < 2:
		link = input("Please enter a link: ")
	else:
		link = sys.argv[1]
	
	if link[-1] == '/':
		link = link[:-1]

	if any(s in link for s in ('/album/', '/playlist/')):
		download_album(link)
		exit()

	if link.split('audius.co')[1].count('/') == 1:
		if '--deleted' in sys.argv:
			download_profile_deleted_tracks(link)
		else:
			download_profile(link)
		exit()
	else:
		download_single_track_from_permalink(link)
		exit()

if __name__ == '__main__':
	base_path = os.getcwd()

	manager = multiprocessing.Manager()
	segments_arr = manager.list([None])
	main()
