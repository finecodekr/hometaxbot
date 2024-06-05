import unittest
from datetime import date
from decimal import Decimal
from typing import List

from hometaxbot.models import 전자신고결과조회
from hometaxbot.scraper import HometaxScraper, reports
from tests import testdata


class TestScrape(unittest.TestCase):
    def test_scrape_세금신고(self):
        scraper = HometaxScraper()
        scraper.login_with_cert(testdata.CORP_CERT, testdata.CORP_PASSWORD)

        results: List[전자신고결과조회] = list(reports.전자신고결과조회(scraper, date(2024, 1, 1), date(2024, 6, 1)))
        self.assertIsInstance(results[0].접수일, date)
        self.assertIsInstance(results[0].금액, Decimal)
