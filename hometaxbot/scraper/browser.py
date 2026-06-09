import logging
import time
from pathlib import Path

from playwright.sync_api import (Error as PlaywrightError, Page,
                                 TimeoutError as PlaywrightTimeoutError,
                                 sync_playwright)

from hometaxbot import AuthenticationFailed


logger = logging.getLogger(__name__)


class HometaxBot:
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

    def already_logged_in(self):
        try:
            return self.page is not None and self.page.locator("a[title='로그아웃']").count() > 0
        except PlaywrightError:
            return False

    def launch(self):
        if self.is_running():
            return self.page

        if not self.playwright:
            self.playwright = sync_playwright().start()

        launch_args = [
            "--window-size=1440,900",
            "--disable-popup-blocking",
            "--disable-features=Translate,MediaRouter,PasswordManager,"
            "AutofillServerCommunication,AutofillEnableAccountWalletStorage",
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
                viewport={"width": 1440, "height": 900} if self.headless else None)

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
        last_error = None
        for attempt in range(3):
            try:
                page.goto("https://hometax.go.kr", wait_until="load")
                break
            except PlaywrightError as error:
                last_error = error
                logger.warning("홈택스 진입 실패(%d/3): %s", attempt + 1, error)
                time.sleep(2)
        else:
            raise last_error

        self.page.locator("a[title='로그인']").or_(
            self.page.locator("text=로그아웃").first
        ).first.wait_for(state="visible")
        self.close_hometax_popups()
        return page

    def login_with_certificate(self, certificate, password, open_login_page=True):
        if isinstance(certificate, (str, Path)):
            certificate = str(certificate)
        else:
            certificate = [str(path) for path in certificate]
            if len(certificate) == 1:
                certificate = certificate[0]

        logger.info("홈택스 인증서 로그인 시작")
        if open_login_page:
            self.open_login_page()
            if self.already_logged_in():
                logger.info("이미 로그인 상태라 인증서 로그인을 건너뜀")
                logger.info("홈택스 인증서 로그인 완료: %s", self.page.url)
                return
            self.wait_cert_login_ready()
            self.close_hometax_popups()

        logger.info("공동·금융인증서 버튼 클릭")
        frame = self.open_cert_dialog()
        logger.info("인증서 iframe 대기")
        self.wait_cert_idle(frame)
        logger.info("브라우저 인증서 선택")
        frame.locator("#in_browser").click()
        self.wait_cert_idle(frame)
        frame.wait_for_selector("#filefile2")
        logger.info("인증서 파일 입력")
        frame.locator("#filefile2").set_input_files(certificate)
        logger.info("인증서 비밀번호 입력")
        self.set_cert_password(frame, password)

        try:
            logger.info("비밀번호 레이아웃 숨김")
            frame.evaluate(
                """
                () => {
                    const layout = document.getElementById('add_browser_password_layout');
                    if (layout) {
                        layout.style.display = 'none';
                        layout.style.pointerEvents = 'none';
                    }
                }
                """
            )
        except PlaywrightError:
            logger.debug("비밀번호 레이아웃 숨김 생략")

        logger.info("인증서 로그인 확인 클릭")
        frame.evaluate("() => document.querySelector('.n_blue_btn #btn_common_confirm').click()")
        state = self.cert_login_state(frame)
        if state == "wrong_password":
            raise AuthenticationFailed("PFX 인증서 비밀번호가 틀렸습니다.")
        if state == "cloud_prompt":
            logger.info("인증서 클라우드 저장 취소")
            frame.locator("a.occui_bt_gray2", has_text="취소").click(force=True)
            frame.wait_for_function(
                """
                () => !document.body.innerText.includes('인증서 클라우드서비스에 저장할까요?')
                """
            )
            if frame.locator("a.occui_bt_blue", has_text="확인").count():
                logger.info("인증서 클라우드 저장 취소 확인")
                frame.locator("a.occui_bt_blue", has_text="확인").click(force=True)
                frame.wait_for_function(
                    """
                    () => !document.querySelector('a.occui_bt_blue')
                    """
                )
            state = self.cert_login_state(frame)
        if state == "cert_password_prompt":
            logger.info("인증서 비밀번호 재입력")
            frame.evaluate(
                """
                value => {
                    const input = document.getElementById('input_cert_pw');
                    input.disabled = false;
                    input.removeAttribute('disabled');
                    input.value = value;
                    input.setAttribute('value', value);
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
                """, password
            )
            logger.info("인증서 최종 확인 클릭")
            frame.evaluate("() => document.getElementById('btn_confirm_iframe').click()")
            self.wait_after_cert_login()
            state = "done"
        if state != "done":
            raise AuthenticationFailed(f"인증서 로그인 상태 확인 실패: {state}")

        self.wait_after_cert_login()
        if not self.tax_agent_confirmation_visible() and not self.agent_login_visible():
            self.wait_hometax_main()
        self.close_hometax_popups()
        logger.info("홈택스 인증서 로그인 완료: %s", self.page.url)

    def login_as_tax_agent(self, cta_admin_no, cta_password):
        logger.info("세무대리인 로그인 시작")
        self.wait_after_cert_login()
        if self.tax_agent_confirmation_visible():
            logger.info("세무대리인 관리번호 로그인 확인")
            self.page.wait_for_function(
                """
                () => !Array.from(document.querySelectorAll('.w2_proc_modal')).some(
                    element => element.offsetParent !== null
                )
                """
            )
            if self.tax_agent_confirmation_visible():
                try:
                    self.page.locator("xpath=//input[@value='확인']").first.click(force=True)
                except PlaywrightError:
                    logger.debug("세무대리인 관리번호 로그인 확인 버튼이 이미 사라짐")
        self.page.locator("xpath=//input[@title='세무대리인 관리번호 입력']").first.wait_for()
        if not self.agent_login_visible():
            raise AuthenticationFailed("세무대리인 로그인 입력창을 찾지 못했습니다.")

        logger.info("세무대리인 관리번호 입력")
        self.page.locator("xpath=//input[@title='세무대리인 관리번호 입력']").fill(cta_admin_no)
        logger.info("세무대리인 비밀번호 입력")
        self.page.locator("xpath=//input[@title='비밀번호 입력']").fill(cta_password)
        logger.info("세무대리인 로그인 버튼 클릭")
        self.page.locator("xpath=//input[@value='로그인']").click()
        self.wait_tax_agent_login_done()
        logger.info("세무대리인 로그인 완료: %s", self.page.url)

    def login_as_tax_agent_sub_account(self, username, password,
                                       certificate, cert_password,
                                       cta_admin_no, cta_password):
        logger.info("홈택스 세무대리인 부서사용자 로그인 시작: username=%s", username)
        self.open_hometax()
        self.login_with_id(username, password)
        self.wait_cert_login_ready()
        self.close_hometax_popups()
        self.login_with_certificate(certificate, cert_password, open_login_page=False)
        self.login_as_tax_agent(cta_admin_no, cta_password)
        self.wait_hometax_main()
        logger.info("홈택스 세무대리인 부서사용자 로그인 완료: %s", self.page.url)

    def login_with_userid(self, username, password, registration_no):
        logger.info("홈택스 아이디 로그인 시작: username=%s", username)
        self.open_hometax()

        self.page.get_by_text("아이디 로그인").first.click()

        self.page.locator("#mf_txppWframe_loginboxFrame_iptUserId").fill(username)
        self.page.locator("#mf_txppWframe_loginboxFrame_iptUserPw").fill(password)
        dialog_count = len(self.dialog_messages)
        self.page.locator("input.btn_idlogin:visible").click()
        logger.info("홈택스 아이디/비밀번호 제출")

        digits = "".join(ch for ch in str(registration_no) if ch.isdigit())
        if len(digits) < 7:
            raise ValueError("registration_no는 주민등록번호 앞 7자리가 필요합니다.")

        jumin1 = self.page.locator('input[name="iptUserJuminNo1"]:visible')
        for _ in range(30):
            if len(self.dialog_messages) > dialog_count:
                raise AuthenticationFailed(self.dialog_messages[-1])
            try:
                if jumin1.is_visible():
                    break
            except PlaywrightError:
                pass
            self.page.wait_for_timeout(1000)
        else:
            if len(self.dialog_messages) > dialog_count:
                raise AuthenticationFailed(self.dialog_messages[-1])
            raise AuthenticationFailed("시간 초과로 로그인에 실패했습니다.")

        jumin1.fill(digits[:6])
        self.page.locator('input[name="iptUserJuminNo2"]:visible').fill(digits[6])
        dialog_count = len(self.dialog_messages)
        self.page.locator('input[value="확인"]:visible').click()
        logger.info("아이디 로그인 2차 인증 제출")

        logout_button = self.page.locator("a[title='로그아웃']")
        for _ in range(30):
            if len(self.dialog_messages) > dialog_count:
                raise AuthenticationFailed(self.dialog_messages[-1])
            try:
                if logout_button.is_visible():
                    break
            except PlaywrightError:
                pass
            self.page.wait_for_timeout(1000)
        else:
            if len(self.dialog_messages) > dialog_count:
                raise AuthenticationFailed(self.dialog_messages[-1])
            raise AuthenticationFailed("시간 초과로 로그인에 실패했습니다.")
        self.page.get_by_text("님께 추천하는 메뉴").or_(
            self.page.get_by_text("세무 업무 가이드 맵")
        ).or_(
            self.page.get_by_text("세무일정별 자주 찾는 메뉴")
        ).or_(
            self.page.get_by_text("세무대리인 맞춤 메뉴")
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

    def open_login_page(self):
        logger.info("홈택스 로그인 화면 열기")
        self.open_hometax()
        login_button = self.page.locator("a[title='로그인']:visible").first
        if login_button.count() > 0 and login_button.is_visible():
            logger.info("로그인 버튼 클릭")
            login_button.click()
            self.wait_login_page_ready()
            self.close_hometax_popups()
        else:
            logger.info("이미 로그인 상태")

    def wait_login_page_ready(self):
        self.wait_id_login_ready()

    def wait_id_login_ready(self):
        logger.info("로그인 화면 로딩 대기")
        self.page.wait_for_function(
            """
            () => {
                const visible = el => {
                    if (!el || !el.isConnected) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                           rect.width > 0 && rect.height > 0;
                };
                const loginPage = document.title.includes('로그인') &&
                                  location.href.includes('menuCd=index3');
                const certLogin = document.querySelector('#mf_txppWframe_anchor13');
                const simpleLogin = document.querySelector('#mf_txppWframe_anchor14');
                const idLogin = document.querySelector('#mf_txppWframe_anchor15');
                const mobileIdLogin = document.querySelector('#mf_txppWframe_anchor16');
                const bioLogin = document.querySelector('#mf_txppWframe_anchor17');
                const certButton = document.querySelector('#mf_txppWframe_anchor22');
                const idInput = document.querySelector(
                    '#mf_txppWframe_iptUserId, #mf_txppWframe_loginboxFrame_iptUserId, input[name="iptUserId"]'
                );
                const pwInput = document.querySelector(
                    '#mf_txppWframe_iptUserPw, #mf_txppWframe_loginboxFrame_iptUserPw, input[name="iptUserPw"]'
                );
                if (!loginPage || !idInput || !pwInput) return false;
                if (visible(idInput) && visible(pwInput)) return true;
                return visible(certLogin) &&
                       (certLogin.innerText || '').includes('공동') &&
                       visible(simpleLogin) &&
                       visible(idLogin) &&
                       idLogin.getAttribute('title') === '아이디 로그인' &&
                       (idLogin.innerText || '').includes('아이디 로그인') &&
                       visible(mobileIdLogin) &&
                       visible(bioLogin) &&
                       visible(certButton) &&
                       (certButton.innerText || '').includes('공동') &&
                       (certButton.innerText || '').includes('금융인증서') &&
                       !visible(idInput) &&
                       !visible(pwInput);
            }
            """
        )

    def login_with_id(self, username, password):
        logger.info("아이디 로그인 탭 선택")
        self.page.get_by_text("아이디 로그인").first.click()
        logger.info("아이디/비밀번호 입력")
        self.page.locator(
            "#mf_txppWframe_iptUserId:visible, "
            "#mf_txppWframe_loginboxFrame_iptUserId:visible, "
            "input[name='iptUserId']:visible"
        ).first.fill(username)
        self.page.locator(
            "#mf_txppWframe_iptUserPw:visible, "
            "#mf_txppWframe_loginboxFrame_iptUserPw:visible, "
            "input[name='iptUserPw']:visible"
        ).first.fill(password)
        logger.info("로그인 버튼 클릭")
        self.page.locator('.basicLogin a[title="로그인"]:visible, input.btn_idlogin:visible').first.click()

    def agent_login_visible(self):
        locator = self.page.locator("xpath=//input[@title='세무대리인 관리번호 입력']")
        return locator.count() > 0 and locator.first.is_visible()

    def tax_agent_confirmation_visible(self):
        confirm_button = self.page.locator("xpath=//input[@value='확인']")
        if confirm_button.count() == 0 or not confirm_button.first.is_visible():
            return False
        body = self.page.locator("body").inner_text()
        return (
            "세무대리인 권한을 가진 사용자 입니다." in body
            and "세무대리 관리번호로 로그인 하시겠습니까?" in body
        )

    def wait_tax_agent_login_done(self):
        logger.info("세무대리인 로그인 완료 대기")
        self.page.wait_for_function(
            """
            () => {
                const visible = el => {
                    if (!el || !el.isConnected) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                           rect.width > 0 && rect.height > 0;
                };
                const body = document.body ? document.body.innerText : '';
                const agentInput = document.querySelector("input[title='세무대리인 관리번호 입력']");
                const mainReady = body.includes('님께 추천하는 메뉴') ||
                                  body.includes('세무 업무 가이드 맵') ||
                                  body.includes('세무일정별 자주 찾는 메뉴') ||
                                  body.includes('세무대리인 맞춤 메뉴');
                let tin = '';
                let txaaYn = '';
                try {
                    tin = $c.util.nts_getSession($p, 'tin');
                    txaaYn = $c.util.nts_getSession($p, 'txaaYn');
                } catch(e) {}
                return body.includes('로그아웃') &&
                       !!tin &&
                       txaaYn === 'Y' &&
                       !visible(agentInput) &&
                       !body.includes('세무대리인 로그인') &&
                       mainReady &&
                       (location.href.includes('menuCd=index4') ||
                        location.href.includes('menuCd=index_txaa') ||
                        body.includes('나의 홈택스'));
            }
            """
        )

    def wait_hometax_main(self):
        self.page.bring_to_front()
        logger.info("메인 페이지 로딩 대기")
        self.page.wait_for_function(
            """
            () => {
                const visible = el => {
                    if (!el || !el.isConnected) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                           rect.width > 0 && rect.height > 0;
                };
                const body = document.body ? document.body.innerText : '';
                const agentInput = document.querySelector("input[title='세무대리인 관리번호 입력']");
                const mainReady = body.includes('님께 추천하는 메뉴') ||
                                  body.includes('세무 업무 가이드 맵') ||
                                  body.includes('세무일정별 자주 찾는 메뉴') ||
                                  body.includes('세무대리인 맞춤 메뉴');
                let tin = '';
                try { tin = $c.util.nts_getSession($p, 'tin'); } catch(e) {}
                return !!(window.$c && window.$c.pp && window.$c.pp.goPotMenu) &&
                       body.includes('로그아웃') &&
                       !!tin &&
                       !visible(agentInput) &&
                       !body.includes('세무대리인 로그인') &&
                       mainReady;
            }
            """
        )

    def wait_cert_login_ready(self):
        logger.info("인증서 로그인 준비 대기")
        self.page.wait_for_function(
            """
            () => {
                const visible = el => {
                    if (!el || !el.isConnected) return false;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' &&
                           rect.width > 0 && rect.height > 0;
                };
                const body = document.body ? document.body.innerText : '';
                const frame = document.getElementById('dscert');
                const certButton = document.querySelector('a.certibtn[title="공동·금융인증서 새창열림"]');
                const agentInput = document.querySelector("input[title='세무대리인 관리번호 입력']");
                const taxAgentConfirm = body.includes('세무대리인 권한을 가진 사용자 입니다.') &&
                                        body.includes('세무대리 관리번호로 로그인 하시겠습니까?');
                let tin = '';
                try { tin = $c.util.nts_getSession($p, 'tin'); } catch(e) {}
                return (frame && frame.src && frame.src !== 'about:blank') ||
                       visible(certButton) ||
                       visible(agentInput) ||
                       taxAgentConfirm ||
                       !!tin;
            }
            """
        )

    def cert_frame(self):
        self.page.wait_for_selector("#dscert")
        self.wait_frame_src("dscert")
        frame = self.page.frame(name="dscert")
        if frame is None:
            raise AuthenticationFailed("인증서 iframe을 찾지 못했습니다.")
        frame.wait_for_selector("#in_browser")
        return frame

    def wait_frame_src(self, frame_name):
        self.page.wait_for_function(
            f"""
            () => {{
                const frame = document.getElementById('{frame_name}');
                return frame && frame.src && frame.src !== 'about:blank';
            }}
            """
        )

    def wait_cert_idle(self, frame):
        try:
            frame.wait_for_function(
                """
                () => {
                    const modal = document.querySelector('.blockUI');
                    return !modal;
                }
                """
            )
        except PlaywrightTimeoutError:
            pass

    def open_cert_dialog(self):
        if self.page.evaluate(
            """
            () => {
                const frame = document.getElementById('dscert');
                return Boolean(frame && frame.src && frame.src !== 'about:blank');
            }
            """
        ):
            return self.cert_frame()

        self.page.locator("a.certibtn:visible, "
                          "a[title='공동·금융인증서 새창열림']:visible").first.click()
        return self.cert_frame()

    def set_cert_password(self, frame, password):
        frame.evaluate("""
            value => {
                const input = document.getElementById('add_browser_password');
                input.disabled = false;
                input.removeAttribute('disabled');
                input.value = value;
                input.setAttribute('value', value);
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            """, password)

    def cert_login_result_state(self):
        return self.page.evaluate(
            """
            () => {
                const visible = el => el && el.offsetParent !== null;
                const body = document.body ? document.body.innerText : '';
                const certFrame = document.getElementById('dscert');
                const success = Boolean(
                    (
                        body.includes('세무대리인 권한을 가진 사용자 입니다.') &&
                        body.includes('세무대리 관리번호로 로그인 하시겠습니까?') &&
                        document.querySelector("input[value='확인']")
                    ) ||
                    visible(document.querySelector("input[title='세무대리인 관리번호 입력']")) ||
                    Array.from(document.querySelectorAll('a, span, button, input')).some(
                        element => visible(element) && (element.innerText || element.value || '').trim() === '로그아웃'
                    )
                );
                const dedicatedLoginPage = document.title.includes('로그인') &&
                                           body.includes('국세청 홈택스에 오신것을 환영합니다.');
                const loginPage = dedicatedLoginPage && !visible(certFrame) && !success && (
                    visible(document.querySelector("a[title='로그인']")) ||
                    visible(document.querySelector("input[title='아이디 입력']")) ||
                    Array.from(document.querySelectorAll('a, button, input')).some(
                        element => visible(element) &&
                                   (element.innerText || element.value || element.title || '').includes('아이디 로그인')
                    )
                );
                return success ? 'done' : (loginPage ? 'login_page' : false);
            }
            """
        )

    def wait_after_cert_login(self):
        logger.info("인증서 로그인 후 상태 확인")
        state = self.page.wait_for_function(
            """
            () => {
                const visible = el => el && el.offsetParent !== null;
                const body = document.body ? document.body.innerText : '';
                const certFrame = document.getElementById('dscert');
                const success = Boolean(
                    (
                        body.includes('세무대리인 권한을 가진 사용자 입니다.') &&
                        body.includes('세무대리 관리번호로 로그인 하시겠습니까?') &&
                        document.querySelector("input[value='확인']")
                    ) ||
                    visible(document.querySelector("input[title='세무대리인 관리번호 입력']")) ||
                    Array.from(document.querySelectorAll('a, span, button, input')).some(
                        element => visible(element) && (element.innerText || element.value || '').trim() === '로그아웃'
                    )
                );
                if (success) {
                    delete window.__hometaxCertLoginPageSince;
                    return 'done';
                }

                const dedicatedLoginPage = document.title.includes('로그인') &&
                                           body.includes('국세청 홈택스에 오신것을 환영합니다.');
                const loginPage = dedicatedLoginPage && !visible(certFrame) && (
                    visible(document.querySelector("a[title='로그인']")) ||
                    visible(document.querySelector("input[title='아이디 입력']")) ||
                    Array.from(document.querySelectorAll('a, button, input')).some(
                        element => visible(element) &&
                                   (element.innerText || element.value || element.title || '').includes('아이디 로그인')
                    )
                );
                if (!loginPage) {
                    delete window.__hometaxCertLoginPageSince;
                    return false;
                }
                window.__hometaxCertLoginPageSince = window.__hometaxCertLoginPageSince || Date.now();
                return Date.now() - window.__hometaxCertLoginPageSince >= 3000 ? 'login_page' : false;
            }
            """
        ).json_value()
        if state == "login_page":
            raise AuthenticationFailed("인증서 로그인 후 로그인 상태가 아닙니다.")

    def cert_login_state(self, frame):
        self.page.wait_for_function(
            """
            () => {
                const frame = document.getElementById('dscert');
                const doc = frame && frame.contentWindow ? frame.contentWindow.document : null;
                return Boolean(
                    (
                        document.body.innerText.includes('세무대리인 권한을 가진 사용자 입니다.') &&
                        document.body.innerText.includes('세무대리 관리번호로 로그인 하시겠습니까?') &&
                        document.querySelector("input[value='확인']")
                    ) ||
                    document.querySelector("input[title='세무대리인 관리번호 입력']") ||
                    Array.from(document.querySelectorAll('a, span, button, input')).some(
                        element => element.offsetParent !== null &&
                                   (element.innerText || element.value || '').trim() === '로그아웃'
                    ) ||
                    (doc && doc.body && doc.body.innerText.includes('PFX 인증서 비밀번호가 틀렸습니다.')) ||
                    (doc && doc.body && doc.body.innerText.includes('인증서 클라우드서비스에 저장할까요?')) ||
                    (doc && doc.body && doc.body.innerText.includes('비밀번호를 다시 입력하세요.'))
                );
            }
            """
        )
        if frame.get_by_text("PFX 인증서 비밀번호가 틀렸습니다.").count():
            return "wrong_password"
        if frame.get_by_text("인증서 클라우드서비스에 저장할까요?").count():
            return "cloud_prompt"
        if frame.get_by_text("비밀번호를 다시 입력하세요.").count():
            return "cert_password_prompt"
        if (
            self.tax_agent_confirmation_visible()
            or self.agent_login_visible()
            or self.page.locator("a[title='로그아웃']").count() > 0
        ):
            return "done"
        if not self.page.locator("a[title='로그인']").first.is_visible():
            return "done"
        raise AuthenticationFailed("인증서 로그인 후 상태를 확인하지 못했습니다.")

HometaxController = HometaxBot
