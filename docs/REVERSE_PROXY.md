# Routes and reverse proxy
This documentation lists the routes

## Endpoints
The following endpoints need **authentication**:
```
GET /
GET /individual_audiobooks
GET /podcast/{asin}
GET /series/{asin}
```
> The curly in the paths indicate path parameters. The [asin](https://en.wikipedia.org/wiki/Amazon_Standard_Identification_Number) 
> is a unique identifier assinged by amazon to all items. This includes 
> audiobooks, book series and audible podcasts. An asin looks like [`B07X2RPHYG`](https://www.audible.de/series/B07X2RPHYG). 
> All URLs to an item on audible contain an asin.

The root path (`/`) displays a **overview page** with links to all RSS feeds. 
All the other paths are RSS feeds for use in a podcast app.

With `AUTH_ENABLED=True` AudiblePodcastFeed requires **http basic authentication** 
(or **basic auth** for short) for the endpoints listed above. Basic auth is
supported by the podcast app Overcast for RSS feeds. Since I use Overcast, basic 
auth is the authentication I have implemented.

With `AUTH_ENABLED=False` basic auth handling in AudiblePodcastFeed can be 
disabled. This can be used to let the reverse proxy handle authentication. 

> Note: `HTTP_USERNAME` and `HTTP_PASSWORD` shoud still be configured when `AUTH_ENABLED=False`

---

The following endpoint **does not** need authentication:
```
GET /audio_file/{hash}/{filename}
```


## Example with treafik

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
      AUTH_ENABLED: False
      HTTP_USERNAME: "{{ user }}"
      HTTP_PASSWORD: "{{ password }}"
    labels:
      - "traefik.enable=true"
      - "traefik.http.middlewares.audible-auth.basicauth.users={{ user and password hashed using htpasswd }}"
      - "traefik.http.routers.audible-podcasts-audio-router.rule=Host(`{{ your domain }}`) && PathPrefix(`/audio_file`)"
      - "traefik.http.routers.audible-podcasts-audio-router.entrypoints=https"
      - "traefik.http.routers.audible-podcasts-audio-router.tls.certresolver=letsencrypt"
      - "traefik.http.routers.audible-podcasts-audio-router.service=audible-podcasts-service"
      - "traefik.http.routers.audible-podcasts-router.rule=Host(`{{ your domain }}`)"
      - "traefik.http.routers.audible-podcasts-router.entrypoints=https"
      - "traefik.http.routers.audible-podcasts-router.tls.certresolver=letsencrypt"
      - "traefik.http.routers.audible-podcasts-router.service=audible-podcasts-service"
      - "traefik.http.routers.audible-podcasts-router.middlewares=audible-auth"
      - "traefik.http.services.audible-podcasts-service.loadbalancer.server.port=8080"
    restart: unless-stopped
  audible-podcasts-downloader:
    build: ./build
    volumes:
    - ./audible_auth:/app/audible_auth
    - metadata:/app/metadata_files
    - audio:/app/audio_files
    command: python library_downloader.py download
    restart: no
  reverse-proxy:
    image: traefik:v3.5
    command:
      - "--providers.docker"
      - "--entryPoints.https.http3"
      - "--entryPoints.https.address=:443"
      - "--entryPoints.http.address=:80"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=http"
      - "--certificatesresolvers.letsencrypt.acme.email={{ your email }}"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - letsencrypt:/letsencrypt

volumes:
	audio:
	metadata:
  letsencrypt:
```
> Note: when used in docker-compose.yml all dollar signs in the hash need to be doubled for escaping.
> To create user:password pair, it's possible to use this command:
> echo $(htpasswd -nB user) | sed -e s/\\$/\\$\\$/g
>
> Also, note that dollar signs should NOT be doubled when not evaluated (e.g. Ansible docker_container module).
\- From the [traefik documentation about the BasicAuth Middleware](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/basicauth/)
