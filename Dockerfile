FROM python:3.12

WORKDIR /app

RUN set -eux; \
	apt-get update; \
	apt-get install -y --no-install-recommends ffmpeg; \
	apt-get dist-clean

COPY src /app/

RUN pip install -r requirements.txt

RUN set -eux; \
    groupadd -g 1000 audible; \
    useradd -m -u 1000 -g 1000 -s /bin/bash audible; \
    chown -R audible:audible /app

USER 1000:1000

RUN mkdir metadata_files audio_files; \
	touch audible_auth

VOLUME /app/metadata_files /app/audio_files /app/audible_auth

EXPOSE 8080/tcp

CMD ["python", "-m", "uvicorn", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "main:app"]
