import base64
import hashlib
import logging
import os
import re
import ssl
import subprocess
from datetime import datetime
from http import HTTPStatus
from typing import List, TypedDict
from urllib.parse import unquote_plus
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

import requests
import yaml
from OpenSSL import crypto

from hometaxbot import HometaxException
from hometaxbot import random_second, AuthenticationFailed, Throttled
from hometaxbot.crypto import load_cert, open_files, validate_cert_expiry
from hometaxbot.models import 홈택스사용자구분코드, 홈택스사용자, 납세자
from hometaxbot.scraper.requestutil import nts_generate_random_string, ensure_xml_response, parse_response, \
    check_error_on_response, CustomHttpAdapter


class HometaxScraper:
    LOGIN_SUCCESS_CODE = 'S'
    HOMETAX_REQUEST_TIMEOUT = 7

    user_info: 홈택스사용자 = None
    selected_trader: 납세자 = None
    개인사업자_list: List[TypedDict('개인사업자', {'사업자등록번호': str, 'tin': str})] = []
    tin: str = None
    user_tin: str = None
    pubcUserNo: str = None
    subdomain: str = None

    def __init__(self):
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        self.session = requests.session()
        self.session.mount('https://', CustomHttpAdapter(ctx))

    def login_with_cert(self, cert_paths: List[str], prikey_password):
        """
        홈택스 공인인증서 로그인
        """
        nts = random_second()
        res = self.session.post("https://www.hometax.go.kr/wqAction.do?actionId=ATXPPZXA001R01&screenId=UTXPPABA01",
                                data=f"<map></map><nts<nts>nts>{nts}dGGBLG2rRWBeuYMviAZyJjAphI9Y3wCmWhg1y84EU{nts - 11}")
        if res.status_code == HTTPStatus.NOT_FOUND:
            raise HometaxException('홈택스 서버에 접속할 수 없습니다. 잠시 후 다시 시도해주세요.')
        pckEncSsn = parse_response(res).find('.//pkcEncSsn').text

        with open_files(cert_paths) as files:
            sign = load_cert(files, prikey_password)
            validate_cert_expiry(sign)

        if len(cert_paths) == 1:
            p = subprocess.Popen(['openssl', 'pkcs12', '-info', '-in', cert_paths[0], '-nodes', '-nocerts', '-passin',
                                  f'pass:{prikey_password}'], stdout=subprocess.PIPE)
            prikey_dumped, _ = p.communicate()
            ID_KISA_NPKI_RAND_NUM = '1.2.410.200004.10.1.1.3'
            result = re.search(f'{ID_KISA_NPKI_RAND_NUM}: (.*)\n-----BEGIN PRIVATE KEY-----', prikey_dumped.decode())
            rand_num = result.group(1)
            randomEnc = base64.b64encode(bytearray.fromhex(rand_num)).decode('utf8')
        else:
            randomEnc = base64.b64encode(sign._rand_num.asOctets()).decode('utf-8')

        content = f'{pckEncSsn}$' \
                  f'{str(hex(sign.serialnum())).replace("x", "")}$' \
                  f'{datetime.now().strftime("%Y%m%d%H%M%S")}$' \
                  f'{base64.b64encode(sign.sign(pckEncSsn.encode("utf-8"))).decode("utf-8")}'
        logSgnt = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        cert = crypto.dump_certificate(crypto.FILETYPE_PEM, sign.pub_cert).decode('utf-8')

        res = self.session.post("https://www.hometax.go.kr/pubcLogin.do",
                                params={"domain": "hometax.go.kr", "mainSys": "Y"},
                                data={
                                    "logSgnt": logSgnt,
                                    "cert": cert,
                                    "randomEnc": randomEnc,
                                    "pkcLoginYnImpv": 'Y',
                                    "pkcLgnClCd": '03',
                                    "scrnId": 'UTXPPABA01&',
                                    "userScrnRslnXcCnt": 1680,
                                    "userScrnRslnYcCnt": 1050
                                })
        result_code = re.search(r"'code' : '(.)'", res.text).group(1)
        if result_code != self.LOGIN_SUCCESS_CODE:
            err_msg = re.search(r"'errMsg' : decodeURIComponent\('(.+?)'\)", res.text).group(1)
            unquoted = unquote_plus(err_msg).replace('+', ' ').replace('\\n', '\n')
            auth_errors = ['홈택스에 등록된 인증서가 아닙니다', '폐지된 인증서입니다']
            if len([e for e in auth_errors if e in unquoted]):
                raise AuthenticationFailed(re.sub(r'\[[^\]]+\]', '', unquoted))
            else:
                logging.exception(res.text)
                raise Exception(unquoted)

        self.fetch_user_and_traders()

    def register_cert(self, registration_no, cert_paths, prikey_password):
        """
        공동인증서를 홈택스에 등록한다.
        """
        nts = random_second()
        res = self.session.post("https://www.hometax.go.kr/wqAction.do?actionId=ATXPPZXA001R01&screenId=UTXPPABA14",
                                data=f"<map></map><nts<nts>nts>{nts}dGGBLG2rRWBeuYMviAZyJjAphI9Y3wCmWhg1y84EU{nts - 11}")
        if res.status_code == HTTPStatus.NOT_FOUND:
            raise Throttled('홈택스 서버에 접속할 수 없습니다. 잠시 후 다시 시도해주세요.')
        pckEncSsn = parse_response(res).find('.//pkcEncSsn').text

        with open_files(cert_paths) as files:
            sign = load_cert(files, prikey_password)

        if len(cert_paths) == 1:
            p = subprocess.Popen(['openssl', 'pkcs12', '-info', '-in', cert_paths[0], '-nodes', '-nocerts', '-passin',
                                  f'pass:{prikey_password}'], stdout=subprocess.PIPE)
            prikey_dumped, _ = p.communicate()
            ID_KISA_NPKI_RAND_NUM = '1.2.410.200004.10.1.1.3'
            result = re.search(f'{ID_KISA_NPKI_RAND_NUM}: (.*)\n-----BEGIN PRIVATE KEY-----', prikey_dumped.decode())
            rand_num = result.group(1)
            randomEnc = base64.b64encode(bytearray.fromhex(rand_num)).decode('utf8')
        else:
            randomEnc = base64.b64encode(sign._rand_num.asOctets()).decode('utf-8')

        content = f'{pckEncSsn}$' \
                  f'{str(hex(sign.serialnum())).replace("x", "")}$' \
                  f'{datetime.now().strftime("%Y%m%d%H%M%S")}$' \
                  f'{base64.b64encode(sign.sign(pckEncSsn.encode("utf-8"))).decode("utf-8")}'
        logSgnt = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        cert = crypto.dump_certificate(crypto.FILETYPE_PEM, sign.pub_cert).decode('utf-8')

        res = self.session.post(
            "https://hometax.go.kr/wqAction.do?actionId=ATXPPABA001C01&screenId=UTXPPABA14&popupYn=false&realScreenId=",
            data=f'<map id="ATXPPABA001C01">'
                 f'<txprDscmNo>{registration_no}</txprDscmNo>'
                 f'<logSgnt>{logSgnt}</logSgnt>'
                 f'<cert>{cert}</cert>'
                 f'<rnd/>'
                 f'<randomEnc>{randomEnc}</randomEnc><hashCntn/>'
                 f'</map><nts<nts>nts>{nts}b8FxcemzOmtdbg6smXGQTS9XHdH665qRZQSiW1XfXTg{nts - 11}',
            headers={'Content-Type': "application/xml; charset=UTF-8"})
        result_code = parse_response(res).find('.//result').text
        if result_code != self.LOGIN_SUCCESS_CODE:
            err_msg = parse_response(res).find('.//msg').text
            if err_msg in ['선택하신 인증서는 이미 등록된 인증서 입니다.']:
                return err_msg
            raise Exception(err_msg)
        return parse_response(res).find('.//msg').text

    def fetch_user_and_traders(self):
        self.deselect_trader()

        res = self.session.post('https://www.hometax.go.kr/permission.do',
                                params={"screenId": "index"},
                                data='<map id="postParam"><popupYn>false</popupYn></map>'.encode('utf-8'),
                                headers={'Content-Type': "application/xml; charset=UTF-8"})
        pubcUserNo = parse_response(res).find('.//pubcUserNo').text
        nts = random_second()
        res_xml = self.request_action_xml(
            action_id='ATXPPAAA001R22',
            screen_id='UTXPPAAA10',
            payload=f'<map id="ATXPPAAA001R22"><pubcUserNo>{pubcUserNo}</pubcUserNo><userType>N</userType><cncClCd/>'
                    f'<arsPswdAltYn/><jntCnt/></map><nts<nts>nts>{nts}BfI2b32na00UC4Gq5TCUjAlsw7uURISbBokVb2ShBc0{nts - 11}')

        self.user_info = model_from_hometax_xml(홈택스사용자, res_xml.find('.//map[@id="pubcUserJnngInfrAdmDVO"]'))
        self.user_tin = res_xml.find('.//map[@id="sessionMap"]/tin').text

        if self.user_info.사용자구분 == 홈택스사용자구분코드.개인:
            self.개인사업자_list = self.fetch_traders()
        else:
            self.selected_trader = self.trader_info()

    def fetch_traders(self):
        nts = random_second()
        res_xml = self.request_action_xml(
            action_id='ATXPPAAA003R01',
            screen_id='UTXPPAAA24',
            payload=f'<map id="ATXPPAAA003R01"/>'
                    f'<nts<nts>nts>{nts}NJ3QcOLdNy8YZIojAqeUQiS6YP653gruVRI9JbNVw{nts - 11}')
        elements = res_xml.find('.//list[@id="bmanBscInfrInqrDVOList"]')

        if elements is None:
            if res_xml.find('.//msg') is None or '사업자 변경대상이 아님' not in res_xml.find('.//msg').text:
                logging.error(ElementTree.tostring(res_xml, encoding='unicode'), stack_info=True)
            return []

        return [{
            '사업자등록번호': element.find('txprDscmNoEncCntn').text,
            'tin': element.find('tin').text,
        } for element in elements]

    def login_with_cookies(self, cookies):
        """
        짧은 시간 안에 여러 번 스크래핑할 때는 반복적으로 공동인증서 로그인을 사용하기보다 한 번 로그인하고 그 쿠키를 재활용한다.
        """
        for cookie in cookies:
            if 'httpOnly' in cookie:
                http_only = cookie.pop('httpOnly')
                cookie['rest'] = {'httpOnly': http_only}
            if 'expiry' in cookie:
                cookie['expires'] = cookie.pop('expiry')
            self.session.cookies.set(**cookie)

        self.fetch_user_and_traders()

    def request_action_xml(self, action_id, screen_id, real_screen_id='', payload: str = None):
        return ensure_xml_response(self.request_action,
                                   action_id,
                                   screen_id,
                                   real_screen_id=real_screen_id,
                                   payload=payload.encode('utf8'),
                                   content_type='application/xml; charset=UTF-8')

    def request_action(self, action_id, screen_id, real_screen_id='', payload=None, content_type='application/xml; charset=UTF-8'):
        return self.session.post('https://hometax.go.kr/wqAction.do',
                                 params={
                                     "actionId": action_id,
                                     "screenId": screen_id,
                                     "popupYn": "false",
                                     "realScreenId": real_screen_id
                                 },
                                 data=payload,
                                 headers={'Content-Type': content_type}, timeout=20)

    def select_trader(self, 사업자등록번호):
        if self.user_info.사용자구분 != 홈택스사용자구분코드.개인:
            return

        try:
            found = next(filter(lambda trader: trader['사업자등록번호'] == 사업자등록번호, self.개인사업자_list))
        except StopIteration:
            raise AuthenticationFailed(f'홈택스에서 사업자등록번호 "${사업자등록번호}"인 사업자를 찾을 수 없습니다.')

        nts = random_second()
        self.request_permission(screen_id='UTXPPAAA24')
        self.request_action(action_id='ATXPPAAA003A01',
                            screen_id='UTXPPAAA24',
                            payload=f'<map id="ATXPPAAA003A01"><tin>{found["tin"]}</tin></map>'
                                    f'<nts<nts>nts>{nts}YOp3ShJZFIhX5xqYRB0ELzlkd0EehhPVkHF6mjLJk{nts - 11}')
        self.tin = None
        self.request_permission(screen_id='index')
        if self.tin != found['tin']:
            logging.exception(f'사업자 선택에 실패했습니다. user_tin : {self.user_tin} target: {found["tin"]} result: {self.tin}')
            raise Throttled(60 * 5, '사업자 선택에 실패했습니다. 다시 시도해주세요.')

        self.selected_trader = self.trader_info()

    def deselect_trader(self):
        """
        개인 인증서로 로그인한 경우 사업자가 선택되어 있는 상태에서 개인이 선택된 상태로 변경한다.
        개인사업자나 법인 인증서의 경우는 홈택스 응답에서 에러가 나지만 무시한다.
        :return:
        """
        nts = random_second()
        self.request_permission(screen_id='UTXPPAAA24')
        res = self.request_action(action_id='ATXPPAAA003A01',
                                  screen_id='UTXPPAAA24',
                                  payload=f'<map id="ATXPPAAA003A01"><tin>ORIGIN</tin></map>'
                                          f'<nts<nts>nts>{nts}YOp3ShJZFIhX5xqYRB0ELzlkd0EehhPVkHF6mjLJk{nts - 11}', )
        self.selected_trader = None

    def trader_info(self, debug=False):
        self.request_permission('teht', 'UTEABGAA21')
        nts = random_second()
        res = self.session.post(
            "https://teht.hometax.go.kr/wqAction.do?actionId=ATTABZAA001R17&screenId=UTEABGAA21&popupYn=false&realScreenId=",
            data=f'<map id="ATTABZAA001R17">'
                 f'<tin>{self.tin}</tin>'
                 f'<txprClsfCd>02</txprClsfCd>'
                 f'<txprDscmNo/><txprDscmNoClCd/><txprDscmDt/>'
                 f'<searchOrder>02/01</searchOrder>'
                 f'<outDes>bmanBscInfrInqrDVO</outDes>'
                 f'<txprNm/><crpTin/><mntgTxprIcldYn/><resnoAltHstrInqrYn/><resnoAltHstrInqrBaseDtm/>'
                 f'</map><nts<nts>nts>{nts}74JxrC2hphMsLLv7deT0nri5fT4KO9iHHdSTK9SATM{nts - 11}',
            headers={'Content-Type': "application/xml; charset=UTF-8"})

        element = parse_response(res).find('.//map[@id="bmanBscInfrInqrDVO"]')
        if element is None:
            logging.error(f'trader_info none element: {res.text}', extra=dict(text=res.text), stack_info=True)
            raise Exception('사업자 정보를 불러오지 못했습니다. 다시 시도해주세요.')

        self.request_permission(screen_id='UTXPPBAA69')
        nts = random_second()
        res = self.session.post(
            "https://hometax.go.kr/wqAction.do?actionId=ATXPPBAA001R36&screenId=UTXPPBAA69&popupYn=false&realScreenId=",
            data=f'<map id="ATXPPBAA001R36">'
                 '<survTtl/>'
                 f'<tin>{self.tin}</tin>'
                 f'</map><nts<nts>nts>{nts}74JxrC2hphMsLLv7deT0nri5fT4KO9iHHdSTK9SATM{nts - 11}',
            headers={'Content-Type': "application/xml; charset=UTF-8"})

        detail = parse_response(res).findall('.//list[@id="bmanBscInfrInqrDVOList"]/map')
        if detail is None:
            raise Throttled('사업자 등록사항을 불러오지 못했습니다. 다시 시도해주세요.')

        사업자상태 = element.find('txprStatNm').text if element.find('txprStatNm') is not None else None
        사업자등록사항 = next(
            (d for d in detail if d.find('txprDscmNoEncCntn').text.replace('-', '') == element.find('txprDscmNoEncCntn').text),
            None)

        return 납세자(
            납세자번호=element.find('txprDscmNoEncCntn').text,
            사업자구분=홈택스사용자구분코드[element.find('txprDclsNm').text],
            전자메일주소=element.find('pfbEml').text,
            휴대전화번호=element.find('pfbTelno').text,
            주소=element.find('roadAdr').text,
            납세자명=element.find('txprNm').text if element.find('txprNm').text else element.find('rprsTxprNm').text,
            대표자주민등록번호=element.find('rprsResno').text.replace('-', ''),
            법인등록번호=element.find('crpno').text if element.find('crpno') is not None else None,
            대표자명=element.find('rprsTxprNm').text,
            업종코드=find_first_value(element, 'tfbCd', 'xmtxOrgMtfbCd', default='ZZZZZZ'),
            업태=find_first_value(element, 'bcNm', 'xmtxOrgMbcNm') if 사업자상태 != '폐업' else None,
            종목=find_first_value(element, 'itmNm', 'xmtxOrgMitmNm') if 사업자상태 != '폐업' else None,
            개업일=datetime.strptime(element.find('txprDscmDt').text, '%Y%m%d').date(),
            폐업일=element.find('cfbDt') and datetime.strptime(element.find('cfbDt').text, '%Y%m%d').date(),
            사업장소재지=element.find('rprsRoadAdr').text,
            사업장전화번호=element.find('rprsHmTelno').text,
            간이과세여부='간이과세자' in 사업자등록사항.find('bmanClNm').text if 사업자등록사항 is not None else False,
        )

    def request_permission(self, subdomain=None, screen_id=None):
        """
        목록조회에 필요한 세션을 얻어옴 = > TEETsessionID
        subdomain:
            - teet: '세금계산서'
            - tecr: '현금영수증매출'
            - teht: '카드매출'
        :return:
        tin: 권한을 얻은 사업자의 홈택스 고유의 식별자
        """
        if self.subdomain == subdomain and self.tin and self.pubcUserNo:
            return

        if screen_id is None:
            screen_id = 'UTEETBAA99'

        base_url = 'https://'
        if subdomain is None:
            base_url += 'hometax.go.kr'
        else:
            base_url += f'{subdomain}.hometax.go.kr'

        response = self.session.post(f'{base_url}/permission.do',
                          data='<map id="postParam"><popupYn>false</popupYn></map>'.encode('utf-8'),
                          params={"screenId": screen_id},
                          headers={'Content-Type': "application/xml; charset=UTF-8"}, timeout=20)
        if '<errorMsg>login</errorMsg>' in response.text:
            response = self.session.get("https://hometax.go.kr/token.do",
                                        params={
                                            "query": f'_{nts_generate_random_string(20)}',
                                            "postfix": datetime.today().strftime('%Y_%m_%d')
                                        },
                                        headers={'Content-Type': "application/xml; charset=UTF-8"})
            check_error_on_response(response)
            ssoToken = re.search(r'nts_reqPortalCallback\("(.*)"\)', response.text).group(1)

            response = self.session.post(f'{base_url}/permission.do',
                                         data=('<map id="postParam">' \
                                               f'{ssoToken}' \
                                               '<popupYn>false</popupYn>' \
                                               '</map>'.encode('utf-8')),
                                         params={"screenId": screen_id, "domain": "hometax.go.kr"},
                                         headers={'Content-Type': "application/xml; charset=UTF-8"})
            if '<errorMsg>login</errorMsg>' in response.text:
                raise Throttled(60, '홈택스 로그인 권한 획득에 실패했습니다. 다시 시도해주세요.')

        root = parse_response(response)
        self.tin = root.find('.//tin').text
        self.pubcUserNo = root.find('.//pubcUserNo').text
        self.subdomain = subdomain


with open(os.path.dirname(__file__) + '/hometax_xml_fields.yml', encoding='utf-8') as f:
    HOMETAX_XML_FIELDS = yaml.safe_load(f)


def model_from_hometax_xml(model_class, element: Element):
    return model_class(**{HOMETAX_XML_FIELDS[model_class.__name__][child.tag]: child.text
                          for child in element if HOMETAX_XML_FIELDS[model_class.__name__].get(child.tag)})


def find_first_value(element, *names, default=''):
    for name in names:
        if element.find(name) is not None and element.find(name).text:
            return element.find(name).text

    return default
