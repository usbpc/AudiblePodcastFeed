# Routes and reverse proxy
This document:
* lists and explains the endpoints served
* explains the resoning behind endpoint design
* shows how to set up https with traefik as a reverse proxy

## Endpoints
The endpoints are noted in this document as the [HTTP request method](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Methods)
followed by the absolute path of the endpoint. A endpoint noted as
```
GET /my/awesome/endpoint
```
can be called using curl with
```bash
curl -X GET https://{SERVER}/my/awesome/endpoint
```
where `{SERVER}` is the server that is providing the endpoint.

### Authenticated
```
GET /
GET /individual_audiobooks
GET /podcast/{asin}
GET /series/{asin}
```
> [!NOTE]
> The curly in the paths indicate path parameters.  
> The [asin](https://en.wikipedia.org/wiki/Amazon_Standard_Identification_Number)
> is a unique identifier assinged by amazon to all items. This includes
> audiobooks, book series and audible podcasts. An asin looks like [`B07X2RPHYG`](https://www.audible.de/series/B07X2RPHYG). 
> All URLs to an item on audible contain an asin.

The root path (`/`) displays a **overview page** with links to all RSS feeds. 
All the other paths are RSS feeds for use in a podcast app.

With `AUTH_ENABLED=True` AudiblePodcastFeed requires **http basic authentication** 
(or **basic auth** for short) for the endpoints listed above. *Basic auth* is
supported by the podcast app Overcast for RSS feeds. Because I use Overcast, 
*basic auth* is the authentication I have implemented.

With `AUTH_ENABLED=False` *basic auth* handling in AudiblePodcastFeed can be 
disabled. This can be used to let a reverse proxy handle authentication. 

> [!WARNING]
> `HTTP_USERNAME` and `HTTP_PASSWORD` still need be configured when *basic auth* 
> is disabled in AudiblePodcastFeed by setting `AUTH_ENABLED=False`.

### Unauthenticated

```
GET /audio_file/{hash}/{filename}
```
> [!NOTE]
> The curly braces in the paths indicate path parameters.

This endpoint is unauthenticated, because the podcast app Overcast dosen't
support authentication for media file downloads.

The `filename` parameter is a filename as downloaded and decrypted by 
`library_downloader.py`. 

To still allow for *some* security the URL for the media files is designed to 
be hard to guess. For that reason, the `hash` parameter is part of the path. 
The  `hash` parameter is the sha256 hash of the  `filename` parameter and 
`PODCAST_HASH_SALT` environment variable concatonated.
> Python code that generates the `hash`:
> `hashlib.sha256(PODCAST_HASH_SALT + bytes(filename, 'utf-8')).hexdigest()`

## Traefik reverse proxy example

To set up AudiblePodcastFeed behind a traefik reverse proxy the following 
`docker-compose.yml` can be used:

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
      - "traefik.http.routers.audible-podcasts-router.rule=Host(`{{ your domain }}`) && PathPrefix(`/audio_file`)"
      - "traefik.http.routers.audible-podcasts-router.entrypoints=https"
      - "traefik.http.routers.audible-podcasts-router.tls.certresolver=letsencrypt"
      - "traefik.http.routers.audible-podcasts-router.service=audible-podcasts-service"
      - "traefik.http.routers.audible-podcasts-router-authenticated.rule=Host(`{{ your domain }}`)"
      - "traefik.http.routers.audible-podcasts-router-authenticated.entrypoints=https"
      - "traefik.http.routers.audible-podcasts-router-authenticated.tls.certresolver=letsencrypt"
      - "traefik.http.routers.audible-podcasts-router-authenticated.service=audible-podcasts-service"
      - "traefik.http.routers.audible-podcasts-router-authenticated.middlewares=audible-auth"
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
> [!IMPORTANT]
> Replace all the placeholders including the double curly braces.

> [!TIP]
> When used in docker-compose.yml all dollar signs in the hash need to be doubled for escaping.  
> To create user:password pair, it's possible to use this command:  
> `echo $(htpasswd -nB user) | sed -e s/\\$/\\$\\$/g`
>
> Also, note that dollar signs should NOT be doubled when not evaluated (e.g. Ansible docker_container module).  
> \- From the [Traefik documentation about the BasicAuth Middleware](https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/basicauth/)

### Explanation of the docker compose file
The above docker compose file specifies a `reverse-proxy` service in addition
to the `audible-podcasts` and `audible-podcasts-downloader` services shown
in the [readme](../README.md). [Traefik](https://traefik.io) is used as the 
reverse proxy software. Traefik is configured to
* serve http on tcp port 80.
* serve https on tcp port 443.
* serve http3 on udp port 443.
* generate TLS certificates using [Let's Encrypt](https://letsencrypt.org/).

This is configured with the command line arguments on the `reverse-proxy` service:
```
- "--providers.docker"
- "--entryPoints.https.http3"
- "--entryPoints.https.address=:443"
- "--entryPoints.http.address=:80"
- "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
- "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=http"
- "--certificatesresolvers.letsencrypt.acme.email={{ your email }}"
- "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
```

Traefik is further configured by the labels on the `audible-podcasts` service.
One **Traefik service** named `audible-podcasts-service` is configured:
```
- "traefik.http.services.audible-podcasts-service.loadbalancer.server.port=8080"
```
The *Traefik service* `audible-podcasts-service` tells Treafik to connect to the
`audible-podcasts` service on port `8080`.

Two **Traefik routers** are configured to connect to the *Traefik service* 
`audible-podcasts-service`:
* the *Treafik router* named `audible-podcasts-router` for the 
unauthenticated endpoint:
```
- "traefik.http.routers.audible-podcasts-router.rule=Host(`{{ your domain }}`) && PathPrefix(`/audio_file`)"
- "traefik.http.routers.audible-podcasts-router.entrypoints=https"
- "traefik.http.routers.audible-podcasts-router.tls.certresolver=letsencrypt"
- "traefik.http.routers.audible-podcasts-router.service=audible-podcasts-service"
```
* the *Traefik router* named `audible-podcasts-router-authenticated` for the 
authenticated endpoints:
```
- "traefik.http.routers.audible-podcasts-router-authenticated.rule=Host(`{{ your domain }}`)"
- "traefik.http.routers.audible-podcasts-router-authenticated.entrypoints=https"
- "traefik.http.routers.audible-podcasts-router-authenticated.tls.certresolver=letsencrypt"
- "traefik.http.routers.audible-podcasts-router-authenticated.service=audible-podcasts-service"
- "traefik.http.routers.audible-podcasts-router-authenticated.middlewares=audible-auth"
```

Both *Traefik routers* are configured to
* only allow https access.
* generate TLS certificates with Let's Encrypt.

The `audible-podcasts-router-authenticated` *Traefik router* is configured to use
the **Traefik middleware** named `audible-auth`.

```
- "traefik.http.middlewares.audible-auth.basicauth.users={{ user and password hashed using htpasswd }}"
```
The `audible-auth` *Traefik middleware* is configured to require *basic auth* to
access any endpoints configured in *Traefik routers* using this *Traefik middleware*.
