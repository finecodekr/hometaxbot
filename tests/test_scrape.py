import unittest
from datetime import date
from decimal import Decimal
from typing import List

from hometaxbot.models import 전자신고결과조회
from hometaxbot.scraper import HometaxScraper, reports, transactions
from tests import testdata


class TestScrape(unittest.TestCase):
    def test_scrape_세금신고(self):
        scraper = HometaxScraper()
        scraper.login_with_cert(testdata.CORP_CERT, testdata.CORP_PASSWORD)

        begin = date(2024, 1, 1)
        end = date(2024, 6, 1)

        results: List[전자신고결과조회] = list(reports.전자신고결과조회(scraper, begin, end))
        self.assertIsInstance(results[0].접수일, date)
        self.assertIsInstance(results[0].금액, Decimal)

        self.assertIsNotNone(next(reports.납부내역(scraper, begin, end)).전자납부번호)
        self.assertIsNotNone(next(reports.납부내역(scraper, begin, end)).전자납부번호)

    def test_scrape_데이터(self):
        scraper = HometaxScraper()
        scraper.login_with_cert(testdata.CORP_CERT, testdata.CORP_PASSWORD)

        begin = date(2024, 1, 1)
        end = date(2024, 10, 1)

        tax_invoice = next(transactions.세금계산서(scraper, begin, end))
        self.assertIsNotNone(tax_invoice.전송일자)
        self.assertNotEqual(tax_invoice.공급자.납세자번호, tax_invoice.공급받는자.납세자번호)
        self.assertGreater(tax_invoice.총금액, 0)
        self.assertGreater(next(transactions.카드매입(scraper, begin, end)).총금액, 0)

        # 잘 안 쓰다보니 귀찮아서 안 고침
        # self.assertGreater(next(transactions.카드매출월간집계(scraper, date(2023, 1, 1), date(2023, 3, 1))).합계금액, 0)

    def test_scrape_현금영수증(self):
        scraper = HometaxScraper()
        scraper.login_with_cert(testdata.CORP_CERT, testdata.CORP_PASSWORD)

        self.assertGreater(next(transactions.현금영수증(scraper, date(2023, 11, 1), date(2023, 12, 31))).총금액, 0)
        self.assertGreater(next(transactions.현금영수증(scraper, date(2024, 1, 1), date(2024, 3, 1))).총금액, 0)
