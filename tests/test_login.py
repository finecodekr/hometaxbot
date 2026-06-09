import unittest
from datetime import date

import dateutil.parser

from hometaxbot import AuthenticationFailed
from hometaxbot.scraper.browser import HometaxBot
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


class TestHometaxBot(unittest.TestCase):
    def test_login_with_certificate(self):
        with HometaxBot() as bot:
            bot.login_with_certificate(testdata.CORP_CERT, testdata.CORP_PASSWORD)
            scraper = HometaxScraper()
            scraper.login_with_cookies(bot.cookies())
            self.assertEqual(홈택스사용자구분코드.법인사업자, scraper.user_info.사용자구분)
            self.assertIn('주식회사', scraper.user_info.납세자명)

            self.assertEqual(scraper.selected_trader.사업자구분, 홈택스사용자구분코드.법인사업자)
            self.assertEqual(10, len(scraper.selected_trader.납세자번호))

    def test_login_as_tax_agent(self):
        with HometaxBot() as bot:
            bot.login_with_certificate(testdata.CTA_CERT, testdata.CTA_PASSWORD)
            bot.login_as_tax_agent(testdata.CTA_NO, testdata.CTA_ACCOUNT_PASSWORD)
            scraper = HometaxScraper()
            scraper.login_with_cookies(bot.cookies())
            self.assertIsNotNone(scraper.user_info.홈택스ID)
            self.assertIsNotNone(scraper.user_info.납세자번호)
            self.assertIsNotNone(scraper.user_info.납세자명)

    def test_login_as_tax_agent_sub_account(self):
        with HometaxBot() as bot:
            bot.login_as_tax_agent_sub_account(testdata.CTA_SUB_ACCOUNT,
                                               testdata.CTA_SUB_ACCOUNT_PASSWORD,
                                               testdata.CTA_CERT,
                                               testdata.CTA_PASSWORD,
                                               testdata.CTA_NO,
                                               testdata.CTA_ACCOUNT_PASSWORD)
            scraper = HometaxScraper()
            scraper.login_with_cookies(bot.cookies())
            self.assertIsNotNone(scraper.user_info.홈택스ID)
            self.assertIsNotNone(scraper.user_info.납세자번호)
            self.assertIsNotNone(scraper.user_info.납세자명)

    def test_userid_password(self):
        with HometaxBot() as bot:
            bot.login_with_userid(testdata.ACCOUNT_USERNAME,
                                  testdata.ACCOUNT_PASSWORD,
                                  testdata.ACCOUNT_REGISTRATION_NO)
            scraper = HometaxScraper()
            scraper.login_with_cookies(bot.cookies())
            self.assertEqual(홈택스사용자구분코드.법인사업자, scraper.user_info.사용자구분)
            self.assertIn(testdata.ACCOUNT_COMPANY, scraper.user_info.납세자명)

            self.assertEqual(scraper.selected_trader.사업자구분, 홈택스사용자구분코드.법인사업자)
            self.assertEqual(10, len(scraper.selected_trader.납세자번호))

    def test_userid_error_message(self):
        # 절대 실제 username을 쓰면 안 됨 (비밀번호 오류로 계정이 차단될 수 있음).
        # 존재하지 않는 랜덤 계정으로 로그인을 시도해 dialog 에러 메시지가
        # AuthenticationFailed 예외로 잘 전달되는지 확인한다.
        random_username = 'finecode_nope_zzx9q7k'
        random_password = 'wrong-pw-3l8x2v6a!'
        with HometaxBot() as bot:
            with self.assertRaises(AuthenticationFailed) as ctx:
                bot.login_with_userid(
                    random_username, random_password, testdata.ACCOUNT_REGISTRATION_NO)
            message = str(ctx.exception)
            print(f'AuthenticationFailed message: {message!r}')
            self.assertTrue(message.strip(), 'dialog 에러 메시지가 비어 있음')


class TestSimpleAuth(unittest.TestCase):
    def test_login_with_simple_auth(self):
        driver = HometaxDriver()
        driver.begin_simple_authentication(testdata.SIMPLE_AUTH_PROVIDER,
                                           testdata.SIMPLE_AUTH_REALNAME,
                                           dateutil.parser.parse(testdata.SIMPLE_AUTH_BIRTHDAY),
                                           testdata.SIMPLE_AUTH_PHONENUMBER)

        input('인증하고 나서 아무 키나 눌러')

        driver.confirm_simple_authentication()

        scraper = HometaxScraper()
        scraper.login_with_cookies(driver.driver.get_cookies())
        self.assertIsNotNone(scraper.user_info.홈택스ID)
