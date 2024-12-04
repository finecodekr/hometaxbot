import unittest
from datetime import date

from tests import testdata

from hometaxbot.models import 홈택스사용자구분코드
from hometaxbot.scraper import HometaxScraper


class TestHometaxLogin(unittest.TestCase):
    def test_login_개인인증서(self):
        scraper = HometaxScraper()
        scraper.login_with_cert(testdata.PERSONAL_CERT, testdata.PERSONAL_PASSWORD)
        self.assertEqual(scraper.user_info.사용자구분, 홈택스사용자구분코드.개인)
        self.assertIsNotNone(scraper.user_info.납세자명)
        self.assertIsNotNone(scraper.user_info.납세자번호)
        self.assertIsNone(scraper.selected_trader)

        scraper.select_trader(scraper.개인사업자_list[0]['사업자등록번호'])
        self.assertEqual(scraper.selected_trader.사업자구분, 홈택스사용자구분코드.개인사업자)
        self.assertEqual(10, len(scraper.selected_trader.납세자번호))
        self.assertIsNotNone(scraper.selected_trader.사업장소재지)
        self.assertIsNotNone(scraper.selected_trader.사업장전화번호)
        self.assertEqual(scraper.user_info.납세자번호, scraper.selected_trader.대표자주민등록번호)

    def test_login_법인인증서(self):
        scraper = HometaxScraper()
        scraper.login_with_cert(testdata.CORP_CERT, testdata.CORP_PASSWORD)

        self.assertEqual(홈택스사용자구분코드.법인사업자, scraper.user_info.사용자구분)
        self.assertIn('주식회사', scraper.user_info.납세자명)

        self.assertEqual(scraper.selected_trader.사업자구분, 홈택스사용자구분코드.법인사업자)
        self.assertEqual(10, len(scraper.selected_trader.납세자번호))
        self.assertIsNotNone(scraper.selected_trader.사업장소재지)
        self.assertIsNotNone(scraper.selected_trader.사업장전화번호)
        self.assertEqual(scraper.user_info.납세자번호, scraper.selected_trader.납세자번호)
        self.assertIsInstance(scraper.selected_trader.개업일, date)

        self.assertEqual(6, len(next(scraper.fetch_세무대리인()).관리번호))