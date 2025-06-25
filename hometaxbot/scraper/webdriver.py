import base64
import logging
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from hometaxbot import HometaxException

WAIT_LONG = 20
WAIT_SHORT = 3


class HometaxDriver:
    def __init__(self, download_folder=None, headless=True):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless')

        options.add_argument('--no-sandbox')  # https://github.com/theintern/intern/issues/878
        options.add_argument(
            '--disable-dev-shm-usage')  # https://developers.google.com/web/tools/puppeteer/troubleshooting - Tips

        self.download_folder = download_folder or str(Path.home() / 'Downloads')

        preferences = {"download.default_directory": self.download_folder,
                       "directory_upgrade": True,
                       "safebrowsing.enabled": True}
        options.add_experimental_option("prefs", preferences)

        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.close()
        self.driver.quit()

    def login_with_cert(self, cert_path, password):
        self.home()
        self.wait_and_click(By.LINK_TEXT, '로그인')

        self.wait_loading()
        WebDriverWait(self.driver, 10).until(lambda locator: self.driver.execute_script('return Boolean(window.WebSquare.uiplugin.editor)'))
        while True:
            try:
                WebDriverWait(self.driver, WAIT_SHORT).until_not(
                    expected_conditions.presence_of_element_located((By.CLASS_NAME, 'blockUI')))
                self.wait_and_click(By.XPATH, './/i[text()[contains(., "공동·금융인증서")]]/../..')
                self.wait(By.ID, 'dscert', delay=WAIT_SHORT)
                self.driver.switch_to.frame('dscert')

                WebDriverWait(self.driver, WAIT_SHORT).until(
                    expected_conditions.presence_of_element_located((By.CLASS_NAME, 'blockUI')))
                WebDriverWait(self.driver, WAIT_LONG).until_not(
                    expected_conditions.presence_of_element_located((By.CLASS_NAME, 'blockUI')))
                self.wait_and_click(By.ID, 'in_browser')
                break
            except TimeoutException as e:
                print('retry...', e)
                self.driver.switch_to.default_content()
                pass

        self.wait_for_blockui_disappeared()
        self.driver.find_element(By.ID, 'filefile2').send_keys(cert_path)
        # self.driver.find_element(By.ID, 'add_browser_password').send_keys(password)
        self.driver.execute_script(f'document.getElementById("add_browser_password").value = "{password}"')

        try:
            self.driver.execute_script('document.getElementById("add_browser_password_layout").style.display = "none"')
        except:
            pass

        self.driver.find_element(By.CSS_SELECTOR, '.n_blue_btn #btn_common_confirm').click()
        try:
            self.wait_and_click(By.CLASS_NAME, 'occui_bt_close', WAIT_SHORT)
        except:
            pass

        self.driver.switch_to.default_content()

    def login_as_tax_agent(self, ctn_no, cta_password):
        for element in self.driver.find_elements(By.CLASS_NAME, 'w2textbox'):
            self.wait_and_click(By.XPATH, '//input[@value="확인"]')
            self.wait(By.XPATH, '//input[@title="세무대리인 관리번호 입력"]')
            (self.driver.find_element(By.XPATH, '//input[@title="세무대리인 관리번호 입력"]')
                .send_keys(ctn_no))
            (self.driver.find_element(By.XPATH, '//input[@title="비밀번호 입력"]')
                .send_keys(cta_password))
            self.wait_and_click(By.XPATH, '//input[@value="로그인"]')
            break

    def wait_for_blockui_disappeared(self, delay=WAIT_LONG):
        WebDriverWait(self.driver, delay).until(
            expected_conditions.presence_of_element_located((By.CLASS_NAME, 'blockUI')))
        WebDriverWait(self.driver, delay).until_not(
            expected_conditions.presence_of_element_located((By.CLASS_NAME, 'blockUI')))

    def login(self, username, password):
        self.home()
        self.wait_and_click(By.LINK_TEXT, '로그인')

        WebDriverWait(self.driver, WAIT_LONG).until(lambda locator: self.driver.execute_script('return !!window.jQuery && window.jQuery.active == 0'))
        self.switch_to_txpp_frame()
        self.wait_and_click(By.LINK_TEXT, '아이디 로그인')
        self.driver.execute_script(self.javascript_for_login(username, password))

        self.driver.get('https://hometax.go.kr')
        self.wait(By.LINK_TEXT, '로그아웃')

        # self.wait_and_click(By.CSS_SELECTOR, '.login_state a:first-child')
        # self.wait(By.NAME, 'txppIframe')
        #
        # self.driver.switch_to.frame('txppIframe')
        # self.wait(By.NAME, 'iptUserId').send_keys(username)
        # self.driver.find_element_by_xpath('//input[@name="iptUserPw"]').send_keys(password)
        # self.wait_loading()
        # self.driver.find_element_by_class_name('login_box').find_element_by_xpath('//input[@type="button"][@value="로그인"]').click()

    def home(self):
        self.driver.get('https://hometax.go.kr')
        # self.driver.get('https://hometax.go.kr/websquare/websquare_cdn.html?w2xPath=/ui/pp/index.xml')
        self.wait_loading()

    @staticmethod
    def javascript_for_login(username, password):
        return re.sub(r'\s', '', f"""
            window.$.post('/pubcLogin.do?domain=hometax.go.kr&mainSys=Y', {{
                ssoLoginYn: 'Y',
                secCardLoginYn: '',
                secCardId: '',
                cncClCd: '01',
                id: '{base64.b64encode(username.encode('utf-8')).decode('utf-8')}',
                pswd: '{password}',
                ssoStatus: '',
                portalStatus: '',
                scrnId: 'UTXPPABA01',
                userScrnRslnXcCnt: '1680',
                userScrnRslnYcCnt: '1050'
            }}).then(function(res) {{ 
                eval(res)
            }})
        """)

    def wait(self, by, value, delay=WAIT_LONG):
        WebDriverWait(self.driver, delay).until(expected_conditions.presence_of_element_located((by, value)))
        return self.driver.find_element(by, value)

    def wait_and_click(self, by, value, delay=WAIT_LONG):
        WebDriverWait(self.driver, delay).until(expected_conditions.element_to_be_clickable((by, value))).click()

    def wait_loading(self):
        WebDriverWait(self.driver, WAIT_LONG).until(expected_conditions.invisibility_of_element((By.CLASS_NAME, 'w2_modal')))
        WebDriverWait(self.driver, WAIT_LONG).until(expected_conditions.invisibility_of_element((By.CLASS_NAME, 'w2_proc_modal')))
        WebDriverWait(self.driver, WAIT_LONG).until(lambda locator: self.driver.execute_script('return !!window.jQuery && window.jQuery.active == 0'))

    def close(self):
        self.driver.close()
        self.driver.quit()

    def account_info(self):
        self.wait_loading()
        self.wait_and_click(By.CSS_SELECTOR, '.user_info a.btn_info')
        self.wait_loading()
        self.switch_to_txpp_frame()

        info = {}
        WebDriverWait(self.driver, 10).until(expected_conditions.visibility_of_any_elements_located((By.CSS_SELECTOR, 'table.tbl_form')))
        tables = self.driver.find_elements(By.CSS_SELECTOR, 'table.tbl_form')
        if tables[0].is_displayed():
            # 개인
            table = tables[0]
        else:
            # 사업자
            table = tables[1]

        for tr in table.find_elements(By.TAG_NAME, 'tr'):
            for th, td in zip(tr.find_elements(By.TAG_NAME, 'th'), tr.find_elements(By.TAG_NAME, 'td')):
                info[th.text] = td.text

        table = self.driver.find_element(By.CSS_SELECTOR, 'table.tbl_form2')
        for tr in table.find_elements(By.TAG_NAME, 'tr'):
            for th, td in zip(tr.find_elements(By.TAG_NAME, 'th'), tr.find_elements(By.TAG_NAME, 'td')):
                info[th.text] = td.text.split('\n')[0]

        return info

    def switch_to_txpp_frame(self):
        self.driver.switch_to.default_content()
        self.driver.switch_to.frame('txppIframe')

    def upload_report(self, report_type, filename):
        self.wait_and_click(By.LINK_TEXT, '신고/납부')
        self.switch_to_txpp_frame()
        if report_type == '종합소득세':
            self.wait_and_click(By.LINK_TEXT, '종합소득세')
            # 100000000000710000 window close
            self.wait_and_click(By.LINK_TEXT, '일반 신고')
            self.wait_and_click(By.CSS_SELECTOR, '#grpt02l0501')  # 파일변환 신고 클릭
            self.accept_alert()
        elif report_type == '부가가치세':
            self.wait_and_click(By.LINK_TEXT, '부가가치세')
            self.wait_and_click(By.LINK_TEXT, '파일 변환신고\n(회계프로그램)')
        else:
            raise Exception(f'{report_type} is not supported')

        # file upload
        self.wait(By.ID, 'raonkuploader_frame_fileList')
        self.driver.switch_to.frame('raonkuploader_frame_fileList')
        self.driver.find_element(By.CSS_SELECTOR, 'input[type="file"]').send_keys(filename)
        self.switch_to_txpp_frame()
        self.driver.find_element(By.CSS_SELECTOR, "input[value='형식검증하기']").click()
        self.accept_alert()
        WebDriverWait(self.driver, WAIT_LONG).until(
            expected_conditions.presence_of_element_located((By.ID, 'UTERNAAZ65_iframe')))
        self.driver.switch_to.frame('UTERNAAZ65_iframe')
        self.driver.find_element(By.ID, 'input1').send_keys('12345678')
        self.driver.find_element(By.CSS_SELECTOR, 'input[value="확인"]').click()

        result = {
            'result': [],
            'errors': [],
            'wetax': False,
            'wetax_retry': 0
        }
        time.sleep(1)
        self.switch_to_txpp_frame()
        self.driver.find_element(By.CSS_SELECTOR, "input[value='형식검증결과확인']").click()

        if self.cell('#grid1_body_table', 1, 3).text != '0' and self.cell('#grid1_body_table', 2, 2).text != '0':
            self.cell('#grid1_body_table', 1, 3).find_element(By.TAG_NAME, 'a').click()
            result['errors'] = self.driver.find_element(By.ID, 'group2792_UTERNAAZ45').text.split('\n')
            self.wait_and_click(By.CSS_SELECTOR, 'input[value="이전"]')

        self.switch_to_txpp_frame()

        if self.cell('#grid1_body_table', 1, 4).text != '1':
            result['result'] = '형식검증오류'
            return result

        self.driver.find_element(By.CSS_SELECTOR, "input[value='내용검증하기']").click()
        time.sleep(3)
        self.driver.find_element(By.CSS_SELECTOR, "input[value='내용검증결과확인']").click()

        if self.cell('#grid1_body_table', 1, 5).text != '0' and self.cell('#grid1_body_table', 2, 3).text != '0':
            result['errors'] = list(self.report_validation_errors('#grid1_body_table', 5))

        if self.cell('#grid1_body_table', 1, 6).text != '1':
            result['result'] = '내용검증오류'
            return result

        self.switch_to_txpp_frame()
        self.driver.find_element(By.CSS_SELECTOR, "input[value='전자파일제출']").click()
        self.driver.find_element(By.CSS_SELECTOR, "input[type='radio']").click()
        self.driver.find_element(By.CSS_SELECTOR, "input[value='전자파일 제출하기']").click()
        self.accept_alert()
        self.accept_alert()

        self.driver.switch_to.frame('UTERNAAZ02_iframe')
        self.driver.find_element(By.CSS_SELECTOR, "input[value='닫기']").click()
        result['result'] = '신고완료'
        return result

    def send_report_to_wetax(self, 대표자주민등록번호, 전화번호):
        self.wait_and_click(By.LINK_TEXT, '신고/납부')
        self.switch_to_txpp_frame()
        self.wait_and_click(By.LINK_TEXT, '종합소득세')

        self.driver.find_element(By.LINK_TEXT, '신고내역 조회 (접수증 · 납부서)').click()
        self.driver.find_element(By.CSS_SELECTOR, 'input[value="조회하기"]').click()
        self.accept_alert()
        self.wait_and_click(By.CSS_SELECTOR, 'td#ttirnam101DVOListDes_cell_0_37')
        self.accept_alert()
        self.wait_and_click(By.ID, 'jumin')
        self.driver.find_element(By.ID, 'jumin').send_keys(대표자주민등록번호[-7:])
        self.wait_and_click(By.ID, 'btn_jumin')
        self.accept_alert()
        self.wait_and_click(By.ID, 'checkSingo')
        self.driver.find_element(By.ID, 'moTel').send_keys(전화번호)
        self.wait_and_click(By.ID, 'btn_regi')
        self.accept_alert()

        return True

    def report_validation_errors(self, table, col):
        # 현재 종합소득세만 동작
        self.cell(table, 1, col).find_element(By.TAG_NAME, 'a').click()
        self.wait_and_click(By.CSS_SELECTOR, 'table.gridHeaderTableDefault tr td a')
        self.driver.switch_to.window('UTERNAAZ13')
        for tr in self.driver.find_elements(By.CSS_SELECTOR, '#ErrBrkdInqrDVOListDes_body_table tr'):
            if not tr.find_elements(By.TAG_NAME, 'td'):
                continue

            print(dict(zip(['서식명', '메시지유형', '항목명', '내용검증 오류내역'], [td.text for td in tr.find_elements(By.TAG_NAME, 'td')])))

        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[0])
        self.switch_to_txpp_frame()
        self.wait_and_click(By.CSS_SELECTOR, 'input[value="이전"]')

    def cell(self, table_selector, row, col):
        return self.driver.find_element(By.CSS_SELECTOR, f'{table_selector} tr:nth-child({row}) td:nth-child({col})')

    def accept_alert(self):
        try:
            WebDriverWait(self.driver, 3).until(expected_conditions.alert_is_present(), 'timeout')

            alert = self.driver.switch_to.alert
            alert.accept()

        except TimeoutException:
            logging.warning("no alert")
