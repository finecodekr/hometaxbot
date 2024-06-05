from typing import List

import typer

from hometaxbot.crypto import load_cert, open_files
from hometaxbot.scraper import HometaxScraper

app = typer.Typer()


@app.command()
def certinfo(cert: List[str], cert_password):
    with open_files(cert) as files:
        sign = load_cert(files, cert_password)
        print('cert_class:', sign.cert_class(), '/ cn:', sign.cn(), '/ serialnum:', sign.serialnum())


scrape = typer.Typer()


@app.command()
def register_cert(registration_no, cert: List[str] = None, cert_password=None):
    scraper = HometaxScraper()
    res = scraper.register_cert(registration_no, cert, cert_password)
    print(res)


if __name__ == "__main__":
    app()