import audible
from audible.aescipher import decrypt_voucher_from_licenserequest
import asyncio
import httpx
from pathlib import Path

from book_store import get_set_of_asins


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
                    print(f"File already exists and is complete: {dest_path}")
                    return True
            except Exception as e:
                print(f"Failed to validate existing file: {e}")
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

            print(f"Downloaded: {self.url} to {dest_path}")
        except Exception as e:
            print(f"Failed to download {self.url}: {e}")


def notes():
    auth = audible.Authenticator.from_login_external(locale='DE')

    client = audible.Client(auth=auth)

    resp = client.get("library", page=2)

    resp = client.post("/1.0/content/B0D94V646D/licenserequest", body={"quality":"High","consumption_type":"Download","drm_type":"Adrm"})

    """ffmpeg -audible_key 'f670c3ace7f14bc076ad9e8ca8ce7623' -audible_iv '00d332e4c0d505db5f8890ef3516def5' -i bk_acx0_406211de_lc_128_44100_2.aax -c copy output.m4a"""

    resp['content_license']['content_metadata']['content_url']['offline_url']

    dlr = decrypt_voucher_from_licenserequest(auth, resp)

    resp = client.get("/1.0/library/B0D94V646D", params={"response_groups": "series, product_desc, media"})
    resp["item"]["series"]
    resp["item"]["title"]

def load_library_from_audible(audible_client: audible.Client):
    page = 1

    items = list()

    while True:
        resp = audible_client.get('1.0/library', params={'num_results': 100, 'sort_by': 'PurchaseDate', 'page': page})
        page += 1

        items.extend(resp['items'])

        if len(resp['items']) == 0:
            break

    return items

def main():
    auth = audible.Authenticator.from_file("audible_auth")
    client = audible.Client(auth=auth)

    items = load_library_from_audible(client)

    downloaded_asins = get_set_of_asins()

    for item in items:
        print(item['title'], end=': ')
        if item['asin'] in downloaded_asins:
            print('Already downloaded')
        else:
            print('Need to download')







if __name__ == "__main__":
    main()