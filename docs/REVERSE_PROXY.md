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
      - "traefik.http.middlewares.audible-auth.basicauth.users=user:$apr1$hf3tPfIO$QbkMLXacYfcOTvPcPQB950"
      - "traefik.http.routers.audible-podcasts-audio-router.rule=Host(`{{ your domain }}`) && PathPrefix(`/audio_file`)"
      - "traefik.http.routers.audible-podcasts-audio-router.entrypoints=https"
      - "traefik.http.routers.audible-podcasts-audio-router.tls.certresolver=letsencrypt"
      - "traefik.http.routers.audible-podcasts-audio-router.service=audible-podcasts-service"
      - "traefik.http.routers.audible-podcasts-router.rule=Host(`{{ your domain }}`)"
      - "traefik.http.routers.audible-podcasts-router.entrypoints=https"
      - "traefik.http.routers.audible-podcasts-router.tls.certresolver=letsencrypt"
      - "traefik.http.routers.audible-podcasts-router.service=audible-podcasts-service"
      - "traefik.http.routers.audible-podcasts-router.middlewares=audible-auth@file"
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

https://doc.traefik.io/traefik/reference/routing-configuration/http/middlewares/basicauth/