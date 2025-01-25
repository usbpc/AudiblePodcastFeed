FROM python:3.8

WORKDIR /app

COPY book_store.py main.py requirements.txt /app/
COPY templates /app/templates/

RUN pip install -r requirements.txt

EXPOSE 80/tcp

CMD ["python", "-m", "uvicorn", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "main:app"]