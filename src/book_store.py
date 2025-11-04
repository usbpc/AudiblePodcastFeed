import os
import json
import re
from dataclasses import dataclass
from typing import List, Dict
import folder_settings

def get_set_of_asins(path: str = folder_settings.METADATA_FOLDER):
    metadata_files = [x for x in os.listdir(path) if re.fullmatch(r"(?!series)(?!content).*.json", x)]

    asins = set()

    for metadata_filename in metadata_files:
        with open(os.path.join(path, metadata_filename), "r") as f:
            parsed_data = json.load(f)
            asins.add(parsed_data['product']['asin'])

    return asins

def _get_parsed_metadata(path: str):
    metadata_files = [x for x in os.listdir(path) if re.fullmatch(r"(?!series)(?!content).*.json", x)]

    series_books = dict()
    podcast_books = dict()
    individual_books = list()

    for metadata_filename in metadata_files:
        with open(f'{path}/{metadata_filename}', "r") as metadata_file:
            parsed_data = json.load(metadata_file)
            is_individual = True
            if 'series' in parsed_data['product']:
                is_individual = False
                for series in parsed_data['product']['series']:
                    if series['asin'] not in series_books:
                        series_books[series['asin']] = list()
                    series_books[series['asin']].append(parsed_data['product'])
            if 'podcasts' in parsed_data['product']:
                is_individual = False
                for podcast in parsed_data['product']['podcasts']:
                    if podcast['asin'] not in podcast_books:
                        podcast_books[podcast['asin']] = list()
                    podcast_books[podcast['asin']].append(parsed_data['product'])
            if is_individual:
                individual_books.append(parsed_data['product'])

    for series_asin, book_data in series_books.items():
        book_data.sort(key=lambda x: list(filter(lambda y: y['asin'] == series_asin, x['series']))[0]['sequence'])

    for podcast_asin, book_data in podcast_books.items():
        book_data.sort(key=lambda x: float(list(filter(lambda y: y['asin'] == podcast_asin, x['podcasts']))[0]['sort']))

    return individual_books, series_books, podcast_books

def _find_m4b_file(book_asin: str, filelist: List):
    return [x for x in filelist if re.fullmatch(rf".*_?{book_asin}_.*\.m4b", x)][0]

@dataclass
class Book:
    title: str
    asin: str
    audio_file: str
    pub_date: str

def _book_from_dict(d: Dict, filelist: List) -> Book:
    return Book(
        title=d['title'],
        asin=d['asin'],
        audio_file=_find_m4b_file(d['asin'], filelist=filelist),
        pub_date=d['release_date'],
    )

@dataclass
class BookSeries:
    title: str
    asin: str
    books: List[Book]

@dataclass
class Podcast:
    title: str
    asin: str
    books: List[Book]

def _make_book_series(asin: str, books: List[Dict], filelist: List) -> BookSeries:
    title = list(filter(lambda x: x['asin'] == asin, books[0]['series']))[0]['title']
    return BookSeries(
        title=title,
        asin=asin,
        books= [_book_from_dict(d, filelist) for d in books],
    )

def _make_book_podcast(asin: str, books: List[Dict], filelist: List) -> Podcast:
    title = list(filter(lambda x: x['asin'] == asin, books[0]['podcasts']))[0]['title']
    return Podcast(
        title=title,
        asin=asin,
        books= [_book_from_dict(d, filelist) for d in books],
    )

def get_all_individual_books() -> List[Book]:
    filelist = os.listdir(folder_settings.AUDIO_FOLDER)
    books, _, _ = _get_parsed_metadata(folder_settings.METADATA_FOLDER)
    return sorted([_book_from_dict(d, filelist) for d in books], key=lambda s: s.title)

def get_series_by_asin(asin: str) -> BookSeries:
    filelist = os.listdir(folder_settings.AUDIO_FOLDER)
    _, series, _ = _get_parsed_metadata(folder_settings.METADATA_FOLDER)
    return _make_book_series(asin=asin, books=series[asin], filelist=filelist)

def get_podcast_by_asin(asin: str) -> Podcast:
    filelist = os.listdir(folder_settings.AUDIO_FOLDER)
    _, _, podcasts = _get_parsed_metadata(folder_settings.METADATA_FOLDER)
    return _make_book_podcast(asin=asin, books=podcasts[asin], filelist=filelist)

def get_audio_file_from_asin(asin: str) -> str:
    filelist = os.listdir(folder_settings.AUDIO_FOLDER)
    return _find_m4b_file(asin, filelist)

def get_series() -> List[BookSeries]:
    filelist = os.listdir(folder_settings.AUDIO_FOLDER)
    book_series = list()
    _, series, _ = _get_parsed_metadata(folder_settings.METADATA_FOLDER)
    for series_asin, book_data in series.items():
        book_series.append(_make_book_series(asin=series_asin, books=book_data, filelist=filelist))
    book_series.sort(key=lambda s: s.title)
    return book_series

def get_podcasts() -> List[Podcast]:
    filelist = os.listdir(folder_settings.AUDIO_FOLDER)
    book_series = list()
    _, _, podcasts = _get_parsed_metadata(folder_settings.METADATA_FOLDER)
    for series_asin, book_data in podcasts.items():
        book_series.append(_make_book_series(asin=series_asin, books=book_data, filelist=filelist))
    book_series.sort(key=lambda s: s.title)
    return book_series
