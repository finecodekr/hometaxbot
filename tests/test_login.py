import time
import unittest
from datetime import date

import dateutil.parser

from hometaxbot.scraper.webdriver import HometaxDriver
from tests import testdata

from hometaxbot.models import 홈택스사용자구분코드, 세목코드
from hometaxbot.scraper import HometaxScraper, reports


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
        self.assertIsNotNone(scraper.selected_trader.휴대전화번호)
        self.assertEqual(scraper.user_info.납세자번호, scraper.selected_trader.납세자번호)
        self.assertIsInstance(scraper.selected_trader.개업일, date)

        수임 = next(scraper.fetch_세무대리수임정보())
        self.assertEqual(scraper.user_info.납세자번호, 수임.납세자.납세자번호)
        self.assertEqual(6, len(수임.세무대리인.관리번호))

        self.assertEqual('과세', scraper.사업자등록상태()['면세구분'])


class TestSimpleAuth(unittest.TestCase):
    def test_login_with_simple_auth(self):
        driver = HometaxDriver()
        driver.begin_simple_authentication(
            testdata.SIMPLE_AUTH_PROVIDER,
            testdata.SIMPLE_AUTH_REALNAME,
            dateutil.parser.parse(testdata.SIMPLE_AUTH_BIRTHDAY),
            testdata.SIMPLE_AUTH_PHONENUMBER,
        )

        input('인증하고 나서 아무 키나 눌러')

        driver.confirm_simple_authentication()

        scraper = HometaxScraper()
        scraper.login_with_cookies(driver.driver.get_cookies())
        self.assertIsNotNone(scraper.user_info.홈택스ID)
