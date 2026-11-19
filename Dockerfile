FROM python:3.14.10@sha256:e5de6bc932256f8138c2353023dc4fd24d010d72f6b5cb06be126f0a4cd53784

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
    mkdir /app/metadata_files /app/audio_files; \
    chown -R audible:audible /app

USER 1000:1000

VOLUME /app/metadata_files /app/audio_files

EXPOSE 8080/tcp

CMD ["python", "-m", "uvicorn", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "main:app"]
