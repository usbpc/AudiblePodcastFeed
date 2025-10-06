import os
import hashlib
import random
import string

from typing import Any
from datetime import datetime, timedelta
from email.utils import format_datetime

from starlette.exceptions import HTTPException
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.config import Config

config = Config(".env")

PODCAST_FEED_IMAGE = config.get("PODCAST_FEED_IMAGE")
HASH_SALT = bytes(config.get("PODCAST_HASH_SALT", default=''.join(random.choices(string.ascii_letters + string.digits, k=16))), 'utf-8')

from book_store import get_all_individual_books, BookSeries, get_series_by_asin, get_podcast_by_asin

templates = Jinja2Templates(directory='templates')
routes = []

def get_salted_hash(path: str) -> str:
    return hashlib.sha256(HASH_SALT + bytes(path, 'utf-8')).hexdigest()

# Copied from starlette utils
def get_route_path(scope: dict[str, Any]) -> str:
    path: str = scope["path"]
    root_path = scope.get("root_path", "")
    if not root_path:
        return path

    if not path.startswith(root_path):
        return path

    if path == root_path:
        return ""

    if path[len(root_path)] == "/":
        return path[len(root_path) :]

    return path

class SaltHashStaticfiles(StaticFiles):
    def get_path(self, scope: dict[str, Any]) -> str:
        """
        Given the ASGI scope, return the `path` string to serve up,
        with OS specific path separators, and any '..', '.' components removed.
        """
        route_path: str = get_route_path(scope)
        first_path_seperator = route_path.find("/", 1)
        if len(route_path) <= 1 or first_path_seperator == -1:
            raise HTTPException(status_code=404)
        hash_from_url = route_path[1:first_path_seperator]
        route_path = route_path[first_path_seperator:]
        computed_hash = get_salted_hash(route_path[1:])
        if hash_from_url != computed_hash:
            raise HTTPException(status_code=404)
        route_path.find("/")

        return os.path.normpath(os.path.join(*route_path.split("/")))

def add_route(path):
    def decorator(f):
        routes.append(Route(path=path, endpoint=f))
    return decorator

def generate_url_prefix(request: Request):
    host = request.headers['x-forwarded-host'] if 'x-forwarded-host' in request.headers else request.url.hostname
    scheme = request.headers['x-forwarded-proto'] if 'x-forwarded-proto' in request.headers else request.url.scheme
    port = int(request.headers['x-forwarded-port']) if 'x-forwarded-port' in request.headers else request.url.port

    if port == 80 and scheme == 'http' or port == 443 and scheme == 'https':
        port = None

    url_prefix = f'{scheme}://{host}:{port}' if port else f'{scheme}://{host}'
    return url_prefix

@add_route(path='/individual_books')
def individual_books(request: Request):
    books = get_all_individual_books()

    url_prefix = generate_url_prefix(request)

    items = list()

    for book in books:

        url = f'{url_prefix}/audio_file/{get_salted_hash(book.audio_file)}/{book.audio_file}'

        items.append({
            'title': book.title,
            'audio_url': url,
            'byte_size':  os.stat(f'audio_files/{book.audio_file}').st_size,
            'type': 'audio/x-m4a',
            'guid': book.asin,
            'pub_date': format_datetime(datetime.strptime(book.pub_date, "%Y-%m-%d")),
        })

    data = {
        'title': 'Kevin\'s Audiobooks',
        'description': 'Audiobooks provided as a Podcast Feed for use in Podcast Apps',
        'image_url': PODCAST_FEED_IMAGE,
        'items': items
    }
    return templates.TemplateResponse(request, 'podcast.xml.j2', data, media_type='text/xml')

@add_route(path='/podcast/{asin}')
def podcast_series(request: Request):
    asin = request.path_params['asin']
    podcast = get_podcast_by_asin(asin)

    items = list()

    url_prefix = generate_url_prefix(request)

    counter = 0
    for book in podcast.books:

        url = f'{url_prefix}/audio_file/{get_salted_hash(book.audio_file)}/{book.audio_file}'

        items.append({
            'title': book.title,
            'audio_url': url,
            'byte_size':  os.stat(f'audio_files/{book.audio_file}').st_size,
            'type': 'audio/x-m4a',
            'guid': book.asin,
            'episode': counter,
            'pub_date': format_datetime(datetime.strptime(book.pub_date, "%Y-%m-%d") + timedelta(minutes=counter)),
        })
        counter += 1

    data = {
        'title': podcast.title,
        'description': 'Audiobooks provided as a Podcast Feed for use in Podcast Apps',
        'image_url': PODCAST_FEED_IMAGE,
        'items': items
    }

    return templates.TemplateResponse(request, 'podcast.xml.j2', data, media_type='text/xml')

@add_route(path='/series/{asin}')
def book_series(request: Request):
    asin = request.path_params['asin']
    series = get_series_by_asin(asin)

    items = list()

    url_prefix = generate_url_prefix(request)

    counter = 0
    for book in series.books:

        url = f'{url_prefix}/audio_file/{get_salted_hash(book.audio_file)}/{book.audio_file}'

        items.append({
            'title': book.title,
            'audio_url': url,
            'byte_size':  os.stat(f'audio_files/{book.audio_file}').st_size,
            'type': 'audio/x-m4a',
            'guid': book.asin,
            'episode': counter,
            'pub_date': format_datetime(datetime.strptime(book.pub_date, "%Y-%m-%d") + timedelta(minutes=counter)),
        })

        counter += 1

    data = {
        'title': series.title,
        'description': 'Audiobooks provided as a Podcast Feed for use in Podcast Apps',
        'image_url': PODCAST_FEED_IMAGE,
        'items': items
    }

    return templates.TemplateResponse(request, 'podcast.xml.j2', data, media_type='text/xml')

routes.append(Mount('/audio_file', app=SaltHashStaticfiles(directory='audio_files'), name='audio_files'))
app = Starlette(debug=True, routes=routes)
