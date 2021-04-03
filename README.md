# audius-dl
Downloader for Audius

## Installation
In this case the Python 3 instance is named `python3`. Here's an example using Ubuntu:
```
# Install FFmpeg
$ sudo apt-get install ffmpeg
# Install required python modules
$ python3 -m pip install joblib mutagen requests
```

## Features
- Download single tracks
- Download playlists
- Download user profiles
- Download deleted tracks from user profiles with `--deleted`

## Usage
```
$ python3 audius-dl.py https://audius.co/nerouk/tame-impala-disciples-nero-edit-304163
API endpoint: https://audius-metadata-3.figment.io
Number of segments: 34
Node endpoints: https://creatornode.audius.co / https://creatornode2.audius.co / https://creatornode3.audius.co
Selected node endpoint: https://creatornode.audius.co
 Segment: [34/34] 
size=    7936kB time=00:03:22.21 bitrate= 321.5kbits/s speed=5.21e+03x
Done!
```

![](https://i.imgur.com/Y968LF3.png)
