import base64
import binascii
import logging
import os
import hashlib
import random
import string

from typing import Any
from datetime import datetime, timedelta
from email.utils import format_datetime

from starlette.authentication import AuthenticationBackend, AuthenticationError, AuthCredentials, SimpleUser
from starlette.exceptions import HTTPException
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.config import Config

import folder_settings

config = Config(".env")

PODCAST_FEED_IMAGE = config.get("PODCAST_FEED_IMAGE")
HASH_SALT = bytes(config.get("PODCAST_HASH_SALT", default=''.join(random.choices(string.ascii_letters + string.digits, k=16))), 'utf-8')
AUTH_ENABLED = config.get("AUTH_ENABLED", default=True)
HTTP_USER = config.get("HTTP_USERNAME", default="user")

try:
    HTTP_PASSWORD = config.get("HTTP_PASSWORD")
except KeyError as exc:
    HTTP_PASSWORD = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    logging.warning(f"No HTTP_PASSWORD set, the password will be randomly generated on each start! Current password: {HTTP_PASSWORD}. ")

folder_settings.AUDIO_FOLDER = config.get("AUDIO_FOLDER", default="audio_files")
folder_settings.METADATA_FOLDER = config.get("METADATA_FOLDER", default="metadata_files")

class BasicAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn):
        if "Authorization" not in conn.headers:
            return

        auth = conn.headers["Authorization"]
        try:
            scheme, credentials = auth.split()
            if scheme.lower() != 'basic':
                return
            decoded = base64.b64decode(credentials).decode("ascii")
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise AuthenticationError('Invalid basic auth credentials')

        username, _, password = decoded.partition(":")
        if username != HTTP_USER or password != HTTP_PASSWORD:
            return
        return AuthCredentials(["authenticated"]), SimpleUser(username)

from folder_settings import AUDIO_FOLDER
from book_store import get_all_individual_books, get_series_by_asin, get_podcast_by_asin, get_series

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

def generate_book_url_prefix(request: Request):
    host = request.headers['x-forwarded-host'] if 'x-forwarded-host' in request.headers else request.url.hostname
    scheme = request.headers['x-forwarded-proto'] if 'x-forwarded-proto' in request.headers else request.url.scheme
    port = int(request.headers['x-forwarded-port']) if 'x-forwarded-port' in request.headers else request.url.port

    if port == 80 and scheme == 'http' or port == 443 and scheme == 'https':
        port = None

    url_prefix = f'{scheme}://{host}:{port}' if port else f'{scheme}://{host}'
    return url_prefix

def generate_auth_url_prefix(request: Request):
    host = request.headers['x-forwarded-host'] if 'x-forwarded-host' in request.headers else request.url.hostname
    scheme = request.headers['x-forwarded-proto'] if 'x-forwarded-proto' in request.headers else request.url.scheme
    port = int(request.headers['x-forwarded-port']) if 'x-forwarded-port' in request.headers else request.url.port

    if port == 80 and scheme == 'http' or port == 443 and scheme == 'https':
        port = None

    url_prefix = f'{scheme}://{HTTP_USER}:{HTTP_PASSWORD}@{host}:{port}' if port else f'{scheme}://{host}'
    return url_prefix

def auth_check(request: Request):
    if AUTH_ENABLED and not request.user.is_authenticated:
        raise HTTPException(status_code=401, headers={'WWW-Authenticate': 'Basic realm="audiobook podcasts"'})

@add_route(path='/individual_books')
def individual_books(request: Request):
    auth_check(request)
    books = get_all_individual_books()

    url_prefix = generate_book_url_prefix(request)

    items = list()

    for book in books:

        url = f'{url_prefix}/audio_file/{get_salted_hash(book.audio_file)}/{book.audio_file}'

        items.append({
            'title': book.title,
            'audio_url': url,
            'byte_size':  os.stat(f'{AUDIO_FOLDER}/{book.audio_file}').st_size,
            'type': 'audio/x-m4a',
            'guid': book.asin,
            'pub_date': format_datetime(datetime.strptime(book.pub_date, "%Y-%m-%d")),
        })

    data = {
        'title': 'Audiobooks not in any series',
        'description': 'Audiobooks provided as a Podcast Feed for use in Podcast Apps',
        'image_url': PODCAST_FEED_IMAGE,
        'items': items
    }
    return templates.TemplateResponse(request, 'podcast.xml.j2', data, media_type='text/xml')

@add_route(path='/podcast/{asin}')
def podcast_series(request: Request):
    auth_check(request)
    asin = request.path_params['asin']
    podcast = get_podcast_by_asin(asin)

    items = list()

    url_prefix = generate_book_url_prefix(request)

    counter = 0
    for book in podcast.books:

        url = f'{url_prefix}/audio_file/{get_salted_hash(book.audio_file)}/{book.audio_file}'

        items.append({
            'title': book.title,
            'audio_url': url,
            'byte_size':  os.stat(f'{AUDIO_FOLDER}/{book.audio_file}').st_size,
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

@add_route(path='/')
def overview(request: Request):
    auth_check(request)
    series_books = get_series()
    individual_books = get_all_individual_books()
    return templates.TemplateResponse(request, 'overview.html.j2', {'series_books': series_books, 'individual_books': individual_books, 'url_prefix': generate_auth_url_prefix(request)}, media_type='text/html')

@add_route(path='/series/{asin}')
def book_series(request: Request):
    auth_check(request)
    asin = request.path_params['asin']
    series = get_series_by_asin(asin)

    items = list()

    url_prefix = generate_book_url_prefix(request)

    counter = 0
    for book in series.books:

        url = f'{url_prefix}/audio_file/{get_salted_hash(book.audio_file)}/{book.audio_file}'

        items.append({
            'title': book.title,
            'audio_url': url,
            'byte_size':  os.stat(f'{AUDIO_FOLDER}/{book.audio_file}').st_size,
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

routes.append(Mount('/audio_file', app=SaltHashStaticfiles(directory=AUDIO_FOLDER), name='audio_files'))

middleware = [
    Middleware(AuthenticationMiddleware, backend=BasicAuthBackend())
]
app = Starlette(debug=True, routes=routes, middleware=middleware)
