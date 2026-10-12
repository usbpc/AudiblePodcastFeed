FROM python:3.15@sha256:83ff73aa50b76c95eba4d765137d3ad023b36355f9ddc161dced40d35dbf8d99

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
