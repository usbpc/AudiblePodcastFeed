import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from book_store import get_all_individual_books, BookSeries, get_series_by_asin

templates = Jinja2Templates(directory='templates')
routes = []

def add_route(path):
    def decorator(f):
        routes.append(Route(path=path, endpoint=f))
    return decorator

@add_route(path='/individual_books')
def individual_books(request: Request):
    books = get_all_individual_books()

    items = list()

    for book in books:
        items.append({
            'title': book.title,
            'audio_url': f'{request.url.scheme}://{request.url.hostname}:{request.url.port}/audio_file/{book.audio_file}',
            'byte_size':  os.stat(f'audio_files/{book.audio_file}').st_size,
            'type': 'audio/x-m4a',
            'guid': book.asin
        })

    data = {
        'title': 'Kevin\'s Audiobooks',
        'description': 'Audiobooks provided as a Podcast Feed for use in Podcast Apps',
        'image_url': 'https://dl.holm.dev/usbpc_logo_512x512.png',
        'items': items
    }
    return templates.TemplateResponse(request, 'podcast.xml.j2', data, media_type='text/xml')


@add_route(path='/series/{asin}')
def book_series(request: Request):
    asin = request.path_params['asin']
    series = get_series_by_asin(asin)

    items = list()

    for book in series.books:
        items.append({
            'title': book.title,
            'audio_url': f'{request.url.scheme}://{request.url.hostname}:{request.url.port}/audio_file/{book.audio_file}',
            'byte_size':  os.stat(f'audio_files/{book.audio_file}').st_size,
            'type': 'audio/x-m4a',
            'guid': book.asin
        })

    data = {
        'title': series.title,
        'description': 'Audiobooks provided as a Podcast Feed for use in Podcast Apps',
        'image_url': 'https://dl.holm.dev/usbpc_logo_512x512.png',
        'items': items
    }

    return templates.TemplateResponse(request, 'podcast.xml.j2', data, media_type='text/xml')

routes.append(Mount('/audio_file', app=StaticFiles(directory='audio_files'), name='audio_files'))
app = Starlette(debug=True, routes=routes)
