# Audible downloader and podcast feed generator
AudiblePodcastFeed serves two related functions, it:
* downloads books from one connected audible library and decrypts the audio files.
* provides an RSS podcast feeds organized by book series.

I created AudiblePodcastFeed to allow me to easily listen to my purchased 
audiobooks using the [overcast podcast app](https://overcast.fm). 
The RSS podcast feeds generated should be compatible with other podcast players, 
but I have not tested that.

AudiblePodcastFeed is desinged to run in a docker container. Other deployment 
methods are not supported.

## About this documentation
This documentation assumes you are familiar with:
* [docker](https://docs.docker.com/get-started/docker-overview/)
* [docker compose](https://docs.docker.com/compose/gettingstarted)
* the linux [command](https://ubuntu.com/tutorials/command-line-for-beginners#1-overview) [line](https://www.digitalocean.com/community/tutorials/linux-commands) interface
* [reverse proxies](https://en.wikipedia.org/wiki/Reverse_proxy)

## Quick start
### Setup
1. Create a directory with the following `docker-compose.yaml`:
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
    ports:
    - 8080:8080
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
> [!IMPORTANT]
> Replace all the placeholders including the double curly braces.

2. Clone this repository into the build subdirectory:
```bash
git clone REPOSITORY build
```
3. Create a audible authentication file:
```bash
touch audible_auth
docker compose run -i audible-podcasts-downloader python generate_audible_auth.py --locale DE
```
> [!IMPORTANT]
> Replace the locale `DE` with the [marketplace country code](https://audible.readthedocs.io/en/latest/marketplaces/marketplaces.html#country-codes) 
of your audible account.

4. Start the docker compose services
5. Optional: Configure a reverse proxy for https ([see the docs](docs/REVERSE_PROXY.md))
6. Optional: Set up a sheduled job for automatic downloading ([see the docs](docs/AUTOMATE_DOWNLOADING.md))
> [!NOTE]
> By default the audiobooks are only downloaded once on initial startup. 
> To download and decrypted audiobooks added to the connected library after 
> initial startup, start the `audible-podcasts-downloader` service again.

### Usage
1. Open the overview page on the root of the `audible-podcasts` web server. 
http://localhost:8080/, if running on your local machine using the docker 
compose configuration from above.
2. Copy any of the RSS feed links and add to your podcast app.

## Configuration
| Environment variable | Default value              | Description                                                                                                                                                                                           |
| -------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PODCAST_FEED_IMAGE` | None, reqired to be set    | URL of cover image used for podcast feeds.                                                                                                                                                            |
| `PODCAST_HASH_SALT`  | Random 16 character string | Hash salt used to obfuscate download links for audio files. Required since overcast dosen't send http basic auth for downloads.                                                                       |
| `AUTH_ENABLED`       | `True`                     | Used to disable authentication handling in the starlette application. Set to `False` when handeling authentication in an external reverse proxy.                                                      |
| `HTTP_USERNAME`      | `user`                     | Username for http basic auth for the podcast feeds. Should also be set if external auth is used. The overview page uses this value to generate links with authentication to the individual RSS feeds. |
| `HTTP_PASSWORD`      | Random 8 character string  | Password for http basic auth for the podcast feeds. Should also be set if external auth is used.                                                                                                      |

## Technical details
The project is written in python and uses the following packages:
* [`audible`](https://pypi.org/project/audible/) for listing and downloading the audiobooks from the connected audible library.
* [`starlette`](https://pypi.org/project/starlette/) for providing the api for the podcast feeds and overview webpage.
* [`jinja2`](https://pypi.org/project/Jinja2/) as the templating engine for the RSS podcast feeds and overview webpage.
* [`uvicorn`](https://pypi.org/project/uvicorn/) as the ASGI web server for running the starlette application.

In addition to the python packages, [`library_downloader.py`](src/library_downloader.py) uses [ffmpeg](https://www.ffmpeg.org/) 
to decrypt the downloaded audio files.
