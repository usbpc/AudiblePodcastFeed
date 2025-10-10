import argparse
import json
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import List, Any, Callable

import audible
from audible.aescipher import decrypt_voucher_from_licenserequest
import asyncio
import httpx
from pathlib import Path
import logging

from audible.exceptions import NotFoundError

import folder_settings
get_set_of_asins = Callable[[str], set]

_logger = logging.getLogger(__name__)

@dataclass
class ProcessingBook:
    asin: str
    book_data: dict | None = None
    download_link: str | None = None
    filename: str | None = None
    decryption_voucher: dict[str, Any] | None = None

def _make_minimal_series(series: dict):
    return {
        'asin': series['asin'],
        'title': series['title'],
        'sequence': series['sequence']
    }

def _make_minimal_podcast(podcast: dict):
    return {
        'asin': podcast['asin'],
        'title': podcast['title'],
        'sort': podcast['sort']
    }

async def get_non_owned_book_data(audible_client: audible.AsyncClient, asin: str) -> dict:
    try:
        resp = await audible_client.get(f"/1.0/catalog/products/{asin}", params={"response_groups": "contributors, media, price, product_attrs, product_desc, product_details, product_extended_attrs, product_plan_details, product_plans, rating, sample, sku, series, reviews, relationships, review_attrs, category_ladders, claim_code_url, provided_review, rights, customer_rights, goodreads_ratings"})

        item = resp['product']

        audible_book = {
            'asin': item['asin'],
            'title': item['title'],
            'lang': item['language'],
            'release_date': item['release_date']
        }

        if "relationships" in item and item['relationships'] is not None:
            podcasts = list()
            for r in item['relationships']:
                if 'content_delivery_type' in r and r['content_delivery_type'] == 'PodcastParent':
                    podcasts.append(_make_minimal_podcast(r))
            if len(podcasts) > 0:
                audible_book['podcasts'] = podcasts

        if "series" in item and item['series'] is not None:
            series = list()
            for s in item['series']:
                series.append(_make_minimal_series(s))
            audible_book['series'] = series

        return audible_book
    except Exception as e:
        _logger.error(f'Failed to get non-owned book data: {e}')

async def get_book_data(audible_client: audible.AsyncClient, asin: str):
    try:

        resp = await audible_client.get(f"/1.0/library/{asin}", params={"response_groups": "series, product_desc, media, relationships"})
        item = resp['item']

        audible_book = {
            'asin': item['asin'],
            'title': item['title'],
            'lang': item['language'],
            'release_date': item['release_date']
        }

        if item['relationships']:
            podcasts = list()
            for r in item['relationships']:
                if 'content_delivery_type' in r and r['content_delivery_type'] == 'PodcastParent':
                    podcasts.append(_make_minimal_podcast(r))
            if len(podcasts) > 0:
                audible_book['podcasts'] = podcasts

        if item['series']:
            series = list()
            for s in item['series']:
                series.append(_make_minimal_series(s))
            audible_book['series'] = series

        return audible_book

    except NotFoundError:
        return await get_non_owned_book_data(audible_client, asin)
    except Exception as e:
        _logger.error(f'Failed to get owned book data: {e}')

async def metadata_downloader(in_queue: asyncio.Queue, out_queue: asyncio.Queue, audible_client: audible.AsyncClient):
    while True:
        cur = await in_queue.get()

        if cur is None:
            await in_queue.put(None)
            break

        cur.book_data = await get_book_data(audible_client, cur.asin)

        await out_queue.put(cur)

    await out_queue.put(None)

class Downloader:
    def __init__(self, client: httpx.AsyncClient, url: str, dest_folder: str, file_name: str):
        self.client = client
        self.url = url
        self.dest_folder = dest_folder
        self.file_name = file_name
        self.ensure_directory_exists()

    def ensure_directory_exists(self):
        """Ensures the destination directory exists."""
        Path(self.dest_folder).mkdir(parents=True, exist_ok=True)

    async def file_already_downloaded(self, dest_path: Path) -> bool:
        """Checks if the completed file exists and matches the expected size using a HEAD request."""
        if dest_path.exists():
            try:
                response = await self.client.head(self.url, follow_redirects=True)
                response.raise_for_status()

                content_length = int(response.headers.get("Content-Length", 0))
                if dest_path.stat().st_size == content_length:
                    _logger.info(f"File already exists and is complete: {dest_path}")
                    return True
            except Exception as e:
                _logger.error(f"Failed to validate existing file: {e}")
        return False

    async def download(self):
        """Downloads the file from the given URL to the destination folder, with resume capability and chunked writing for large files."""
        try:
            dest_path = Path(self.dest_folder) / self.file_name
            temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

            # Check if the completed file already exists and is valid
            if await self.file_already_downloaded(dest_path):
                return

            # Check if the file already exists and get its size
            existing_file_size = temp_path.stat().st_size if temp_path.exists() else 0

            # Set headers to resume download if the file partially exists
            headers = {"Range": f"bytes={existing_file_size}-"} if existing_file_size > 0 else {}

            # Perform the request
            async with self.client.stream("GET", self.url, headers=headers, follow_redirects=True) as response:
                response.raise_for_status()

                # Append to the temp file if resuming, otherwise write a new temp file
                with open(temp_path, "ab" if existing_file_size > 0 else "wb") as file:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                        file.write(chunk)

            # Rename temp file to final file name upon completion
            temp_path.rename(dest_path)

            _logger.debug(f"Downloaded: {self.url} to {dest_path}")
        except Exception as e:
            _logger.error(f"Failed to download {self.url}: {e}")

async def book_downloader(in_queue: asyncio.Queue, out_queue: asyncio.Queue):
    httpx_client = httpx.AsyncClient(headers= {"User-Agent": "Audible/671 CFNetwork/1240.0.4 Darwin/20.6.0"})

    while True:
        cur: ProcessingBook = await in_queue.get()
        if cur is None:
            await in_queue.put(None)
            break

        _logger.info(f'Downloading "{cur.book_data["title"]}"')
        downloader = Downloader(httpx_client, cur.download_link, folder_settings.DOWNLOAD_FOLDER, cur.filename)
        await downloader.download()

        await out_queue.put(cur)

    await httpx_client.aclose()
    await out_queue.put(None)

async def book_converter(in_queue: asyncio.Queue):
    while True:
        cur: ProcessingBook = await in_queue.get()
        if cur is None:
            await in_queue.put(None)
            break

        tmp_filename = f'{folder_settings.AUDIO_FOLDER}/{cur.filename[:-4]}.m4a'
        final_filename = f'{folder_settings.AUDIO_FOLDER}/{cur.filename[:-4]}.m4b'

        args = [
            '-y',
            '-audible_key', cur.decryption_voucher['key'],
            '-audible_iv', cur.decryption_voucher['iv'],
            '-i', f'{folder_settings.DOWNLOAD_FOLDER}/{cur.filename}',
            '-c', 'copy',
            tmp_filename
        ]

        _logger.debug(f'Running ffmpeg with args: {" ".join(args)}')
        proc = await asyncio.create_subprocess_exec(
            'ffmpeg', *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )

        await proc.wait()

        if proc.returncode != 0:
            _logger.error(f"Something went wrong trying to convert {cur.filename}")
            continue

        os.remove(f'{folder_settings.DOWNLOAD_FOLDER}/{cur.filename}')
        os.rename(tmp_filename, final_filename)

        with open(f'{folder_settings.METADATA_FOLDER}/{cur.asin}.json', 'w') as file:
            file.write(json.dumps({'product': cur.book_data}))

async def metadata_writer(in_queue: asyncio.Queue):
    while True:
        cur: ProcessingBook = await in_queue.get()
        if cur is None:
            await in_queue.put(None)
            break

        with open(f'{folder_settings.METADATA_FOLDER}/{cur.asin}.json', 'w') as file:
            file.write(json.dumps({'product': cur.book_data}))

async def owned_books_asins(audible_client: audible.AsyncClient):
    page = 1

    while True:
        resp = await audible_client.get('1.0/library', params={'num_results': 100, 'sort_by': 'PurchaseDate', 'page': page})
        page += 1

        for item in resp['items']:
            yield item['asin']

        if len(resp['items']) == 0:
            break

async def get_download_license(audible_client: audible.AsyncClient, asin: str):
    resp = await audible_client.post(f"/1.0/content/{asin}/licenserequest",
                       body={"quality": "High", "consumption_type": "Download", "drm_type": "Adrm"})

    dlr = decrypt_voucher_from_licenserequest(audible_client.auth, resp)
    download_link = resp['content_license']['content_metadata']['content_url']['offline_url']

    return download_link, dlr

def _find_m4b_file(book_asin: str, filelist: List):
    try:
        return [x for x in filelist if re.fullmatch(rf".*_?{book_asin}_.*\.m4b", x)][0]
    except IndexError:
        return None

def generate_download_filename(asin: str, download_link: str):
    url = urllib.parse.urlparse(download_link)
    match = re.search(r'[a-zA-Z0-9]+_\d+_\d+_\d', url.path)

    return asin + '_' + match.group(0).upper() + '.aax'

async def download_books_and_metadata(audible_client: audible.AsyncClient):
    existing_metadata = get_set_of_asins()
    filelist = os.listdir(folder_settings.AUDIO_FOLDER)

    metadata_input_queue = asyncio.Queue(maxsize=1)
    downloader_input_queue = asyncio.Queue(maxsize=1)
    ffmpeg_input_queue = asyncio.Queue(maxsize=1)

    metadata = asyncio.create_task(metadata_downloader(metadata_input_queue, downloader_input_queue, audible_client))
    downloader = asyncio.create_task(book_downloader(downloader_input_queue, ffmpeg_input_queue))
    converter = asyncio.create_task(book_converter(ffmpeg_input_queue))

    async for asin in owned_books_asins(audible_client):
        _logger.debug(f'Checking {asin}')
        if asin not in existing_metadata or not _find_m4b_file(asin, filelist):
            url, dlr = await get_download_license(audible_client, asin)
            filename = generate_download_filename(asin, url)
            await metadata_input_queue.put(ProcessingBook(asin=asin, download_link=url, decryption_voucher=dlr, filename=filename))

    await metadata_input_queue.put(None)
    await metadata
    await downloader
    await converter
    _logger.debug("Done Processing Books")

async def update_metadata(audible_client: audible.AsyncClient):
    existing_metadata = get_set_of_asins()

    metadata_input_queue = asyncio.Queue(maxsize=1)
    metadata_output_queue = asyncio.Queue(maxsize=1)

    metadata_in = asyncio.create_task(metadata_downloader(metadata_input_queue, metadata_output_queue, audible_client))
    metadata_out = asyncio.create_task(metadata_writer(metadata_output_queue))

    for asin in existing_metadata:
        _logger.debug(f'Checking {asin}')
        await metadata_input_queue.put(
            ProcessingBook(asin=asin, download_link=None, decryption_voucher=None, filename=None))

    await metadata_input_queue.put(None)
    await metadata_in
    await metadata_out

    _logger.debug("Done Processing Books")

def main():
    parser = argparse.ArgumentParser(description='Audible cli download tool')
    parser.add_argument("--audio-folder", default="audio_files", type=str, help="Path to the audio folder")
    parser.add_argument("--metadata-folder", default="metadata_files", type=str, help="Path to the metadata folder")
    parser.add_argument("--download-folder", default="downloads", type=str, help="Path to the temp download folder")
    subparsers = parser.add_subparsers(dest='command', required=True)

    parser_download = subparsers.add_parser('download', help='Download books and metadata')
    parser_metadata = subparsers.add_parser('metadata', help='Update metadata of downloaded books')

    args = parser.parse_args()

    folder_settings.AUDIO_FOLDER = args.audio_folder
    folder_settings.METADATA_FOLDER = args.metadata_folder

    import book_store
    global get_set_of_asins
    get_set_of_asins = book_store.get_set_of_asins

    to_run = None

    match args.command:
        case 'download':
            to_run = download_books_and_metadata
        case 'metadata':
            to_run = update_metadata

    auth = audible.Authenticator.from_file("../audible_auth")
    client = audible.AsyncClient(auth=auth)

    if to_run is None:
        return

    asyncio.run(to_run(client))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    _logger.setLevel(logging.DEBUG)
    main()