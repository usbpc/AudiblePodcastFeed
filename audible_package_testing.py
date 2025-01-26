import audible
from audible.aescipher import decrypt_voucher_from_licenserequest

def main():
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

if __name__ == "__main__":
    main()