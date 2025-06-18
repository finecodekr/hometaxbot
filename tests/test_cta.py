from datetime import date
from unittest import TestCase

from hometaxbot.models import 세목코드
from hometaxbot.scraper import HometaxScraper, reports
from tests import testdata


class TestCTA(TestCase):
    def test_login_세무사(self):
        scraper = HometaxScraper()
        scraper.login_with_cert(testdata.CTA_CERT, testdata.CTA_PASSWORD)
        scraper.login_as_tax_accountant(testdata.CTA_NO, testdata.CTA_ACCOUNT_PASSWORD)

        for 납부서_obj in reports.신고서_납부서(scraper, 세목코드.양도소득세, date(2025, 5, 1), date(2025, 5, 31)):
            self.assertIsNotNone(납부서_obj.납부내역.금액)
            break
