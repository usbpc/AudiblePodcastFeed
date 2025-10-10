import argparse

import audible

def main():
    parser = argparse.ArgumentParser(description='Audible cli auth tool')


    parser.add_argument('--locale', required=True, dest='locale',
                        help='Base URL for the pi-hole instance to control')
    parser.add_argument('--auth-file', default="audible_auth", dest='file',)

    args = parser.parse_args()

    auth = audible.Authenticator.from_login_external(locale=args.locale)
    auth.to_file(args.file)


if __name__ == "__main__":
    main()
