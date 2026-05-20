import logging
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, Page, sync_playwright


logger = logging.getLogger(__name__)


class HometaxController:
    def __init__(self, user_data_dir: Path = None, headless=True):
        self.user_data_dir = Path(user_data_dir).resolve() if user_data_dir else None
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Page = None
        self.dialog_messages = []

    def __enter__(self):
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def is_running(self):
        return self.context is not None and self.page is not None and not self.page.is_closed()

    def launch(self):
        if self.is_running():
            return self.page

        if not self.playwright:
            self.playwright = sync_playwright().start()

        launch_args = [
            "--window-size=1440,900",
            "--disable-popup-blocking",
            "--disable-features=Translate,MediaRouter,PasswordManager,AutofillServerCommunication,AutofillEnableAccountWalletStorage",
            "--password-store=basic",
            "--use-mock-keychain",
        ]

        if self.user_data_dir:
            logger.info("브라우저 실행: persistent context")
            self.context = self.playwright.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                args=launch_args,
                viewport={"width": 1440, "height": 900} if self.headless else None,
            )
            self.browser = self.context.browser
        else:
            logger.info("브라우저 실행: temporary context")
            self.browser = self.playwright.chromium.launch(headless=self.headless, args=launch_args)
            self.context = self.browser.new_context(
                viewport={"width": 1440, "height": 900} if self.headless else None
            )

        for page in list(self.context.pages):
            if page.opener() is None and not page.url.startswith("devtools://"):
                continue
            logger.debug("보조 페이지 닫기: %s", page.url)
            page.close()

        if self.context.pages:
            for page in reversed(self.context.pages):
                if page.opener() is None and not page.url.startswith("devtools://"):
                    self.page = page
                    break
            else:
                self.page = self.context.pages[-1]
        else:
            self.page = self.context.new_page()

        def accept_dialog(dialog):
            logger.info("브라우저 dialog 수락: %r", dialog.message)
            self.dialog_messages.append(dialog.message)
            dialog.accept()

        self.page.on("dialog", accept_dialog)
        return self.page

    def close(self):
        logger.debug("브라우저 종료")
        if self.context:
            self.context.close()
        elif self.browser:
            self.browser.close()
        self.browser = None
        self.context = None
        self.page = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

    def open_hometax(self):
        page = self.launch()
        logger.info("홈택스 접속")
        page.goto("https://hometax.go.kr")
        self.close_hometax_popups()
        return page

    def login_with_userid(self, username, password, registration_no):
        logger.info("홈택스 아이디 로그인 시작: username=%s", username)
        self.open_hometax()

        self.page.get_by_text("아이디 로그인").first.click()

        self.page.locator("#mf_txppWframe_loginboxFrame_iptUserId").fill(username)
        self.page.locator("#mf_txppWframe_loginboxFrame_iptUserPw").fill(password)
        self.page.locator("input.btn_idlogin:visible").click()
        logger.info("홈택스 아이디/비밀번호 제출")

        digits = "".join(ch for ch in str(registration_no) if ch.isdigit())
        if len(digits) < 7:
            raise ValueError("registration_no는 주민등록번호 앞 7자리가 필요합니다.")

        self.page.locator('input[name="iptUserJuminNo1"]:visible').fill(digits[:6])
        self.page.locator('input[name="iptUserJuminNo2"]:visible').fill(digits[6])
        self.page.locator('input[value="확인"]:visible').click()
        logger.info("아이디 로그인 2차 인증 제출")

        self.page.locator("a[title='로그아웃']").text_content()
        self.page.get_by_text("님께 추천하는 메뉴").or_(
            self.page.get_by_text("세무 업무 가이드 맵")
        ).or_(
            self.page.get_by_text("세무일정별 자주 찾는 메뉴")
        ).first.text_content()
        logger.info("홈택스 로그인 완료: %s", self.page.url)
        self.close_hometax_popups()

    def cookies(self):
        cookies = self.context.cookies()
        logger.debug("브라우저 쿠키 반환: %d개", len(cookies))
        return cookies

    def close_hometax_popups(self):
        logger.debug("홈택스 팝업 정리")
        for selector in ["#__occui_root__ .occui_bt_close", ".occui_bt_close"]:
            try:
                close_buttons = self.page.locator(selector).all()
            except PlaywrightError as error:
                logger.warning("홈택스 안내 팝업 조회 실패: selector=%s, error=%s", selector, error)
                continue

            for close_button in close_buttons:
                try:
                    logger.debug("홈택스 안내 팝업 닫기: selector=%s", selector)
                    close_button.click(force=True)
                except PlaywrightError as error:
                    logger.warning("홈택스 안내 팝업 닫기 실패: selector=%s, error=%s", selector, error)

        try:
            message_buttons = self.page.locator('.w2popup_window input[type="button"][value="확인"]').all()
        except PlaywrightError as error:
            logger.warning("홈택스 메시지 팝업 조회 실패: error=%s", error)
            return

        for button in message_buttons:
            try:
                logger.debug("홈택스 메시지 팝업 확인")
                button.click(force=True)
            except PlaywrightError as error:
                logger.warning("홈택스 메시지 팝업 확인 실패: error=%s", error)
