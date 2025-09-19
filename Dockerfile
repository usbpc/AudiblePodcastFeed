FROM python:3.12

WORKDIR /app

COPY book_store.py main.py audible_package_testing.py requirements.txt /app/
COPY templates /app/templates/

RUN set -eux; \
	apt-get update; \
	apt-get install -y --no-install-recommends ffmpeg; \
	apt-get dist-clean

RUN pip install -r requirements.txt

EXPOSE 80/tcp

CMD ["python", "-m", "uvicorn", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "main:app"]
