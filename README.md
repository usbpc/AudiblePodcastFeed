# Audible downloader and podcast feed generator
AudiblePodcastFeed serves two related functions, it:
* downloads books from the connected audible library and decrypts the audio files.
* provides an RSS podcast feeds organized by book series.

I created AudiblePodcastFeed to allow me to easily listen to my purchased audiobooks using the [overcast podcast app](https://overcast.fm). 
The RSS podcast feeds generated should be compatible with other podcast players, but I have not tested that.

## Setup
This documentation assumes you are familiar with:
* [docker](https://docs.docker.com/get-started/docker-overview/)
* [docker compose](https://docs.docker.com/compose/gettingstarted)
* the linux [command](https://ubuntu.com/tutorials/command-line-for-beginners#1-overview) [line](https://www.digitalocean.com/community/tutorials/linux-commands) interface
* [reverse proxies](https://en.wikipedia.org/wiki/Reverse_proxy)

AudiblePodcastFeed is made to run in a docker container.

## Docker compose
`git clone REPOSITORY build`
```yaml
services:
  audible-podcasts:
    build: ./build
    volumes:
    - metadata:/app/metadata_files
    - audio:/app/audio_files
    environment:
      PODCAST_FEED_IMAGE: "{{ url for cover image }}"
      PODCAST_HASH_SALT: "{{ random string }}"
      AUTH_ENABLED: True
      HTTP_USERNAME: "{{ user }}"
      HTTP_PASSWORD: "{{ password }}"
    restart: unless-stopped
  audible-podcasts-downloader:
    build: ./build
    volumes:
    - ./audible_auth:/app/audible_auth
    - metadata:/app/metadata_files
    - audio:/app/audio_files
    command: python library_downloader.py download
    restart: no

volumes:
	audio:
	metadata:
```

```bash
touch audible_auth
docker compose run -i audible-podcasts-downloader python generate_audible_auth.py --locale DE
```
https://audible.readthedocs.io/en/latest/marketplaces/marketplaces.html#country-codes


## Technical details
The project is written in python and uses the following packages:
* [`audible`](https://pypi.org/project/audible/) for listing and downloading the audiobooks from the connected audible library.
* [`starlette`](https://pypi.org/project/starlette/) for providing the api for the podcast feeds and overview webpage.
* [`jinja2`](https://pypi.org/project/Jinja2/) as the templating engine for the RSS podcast feeds and overview webpage.
* [`uvicorn`](https://pypi.org/project/uvicorn/) as the ASGI web server for running the starlette application.

In addition to the python packages, [`library_downloader.py`](src/library_downloader.py) uses [ffmpeg](https://www.ffmpeg.org/) 
to decrypt the downloaded audio files.