import base64
import json
import logging
import os
import re
import ssl
import subprocess
import time
from datetime import datetime
from http import HTTPStatus
from typing import List, TypedDict, TypeVar
from urllib.parse import unquote_plus, unquote
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

import requests
import yaml
from cryptography.hazmat.primitives._serialization import Encoding
from requests import JSONDecodeError

from hometaxbot import HometaxException
from hometaxbot import random_second, AuthenticationFailed, Throttled
from hometaxbot.crypto import load_cert, open_files, validate_cert_expiry, k4, snake_oil_encrypt
from hometaxbot.models import 홈택스사용자구분코드, 홈택스사용자, 납세자, 세무대리인, 세무대리수임정보
from hometaxbot.scraper.requestutil import nts_generate_random_string, ensure_xml_response, parse_response, \
    check_error_on_response, CustomHttpAdapter, json_minified_dumps


class HometaxScraper:
    LOGIN_SUCCESS_CODE = 'S'
    HOMETAX_REQUEST_TIMEOUT = 7
    PAGE_SIZE = 10
    DOWNLOAD_PAGE_SIZE = 1000

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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        })
        # self.session.headers['Content-Type'] = 'application/json'
        self.cta_admin_no = None

    def login_with_cert(self, cert_paths: List[str], prikey_password):
        """
        홈택스 공인인증서 로그인
        """
        nts = random_second()
        self.session.post('https://hometax.go.kr/wqAction.do?actionId=ATXPPCBA001R17&screenId=index_pp&popupYn=false&realScreenId=',
                          data='{"cncClCd":"01","srvcClCd":"01","menuHtrnId":"100900","ntplAthYn":"N","ntplBmanAthYn":"","crpBmanAthYn":"","txaaYn":"","cshptMrntYn":"","pubcUserNo":"","dprtUserYn":"","athCd":"N","menuId":"","prevMenuId":"","menuTtl":""}<nts<nts>nts>59h3OdIFTyGfSN5JWA5ycXWy2NySYP0nOT5DAy4zN848')
        self.request_permission(screen_id='UTXPPABA01')
        self.session.post('https://hometax.go.kr/jsp/magicNX/getMLSession.jsp', data='')
        self.session.post('https://hometax.go.kr/wqAction.do?actionId=ATXPPABA001A25&screenId=UTXPPABA01&popupYn=false&realScreenId=', data='{"ipUData":""}<nts<nts>nts>60sSHhJ0npixTDedljXKTgyCTViu40xfLWs6aimQmq8A49')
        self.session.post('https://hometax.go.kr/wqAction.do?actionId=ATXPPCBA001R020&screenId=UTXPPABA01&popupYn=false', json={"scrnId": "0900000000", "pageInfoVO": {"totalCount" : "0", "pageSize" : "10", "pageNum" : "1"} })

        res = self.session.post("https://www.hometax.go.kr/wqAction.do?actionId=ATXPPZXA001R01&screenId=UTXPPABA01",
                                data=f"{{}}{nts}dGGBLG2rRWBeuYMviAZyJjAphI9Y3wCmWhg1y84EU{nts - 11}",
                                headers={'Content-Type': 'application/json'})
        if res.status_code == HTTPStatus.NOT_FOUND:
            raise HometaxException('홈택스 서버에 접속할 수 없습니다. 잠시 후 다시 시도해주세요.')
        pckEncSsn = res.json()['pkcEncSsn']

        with open_files(cert_paths) as files:
            sign = load_cert(files, prikey_password)
            validate_cert_expiry(sign)

        if len(cert_paths) == 1:
            p = subprocess.Popen(['openssl', 'pkcs12', '-info', '-provider', 'legacy', '-provider', 'default',
                                  '-in', cert_paths[0], '-nodes', '-nocerts', '-passin',
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
        cert = sign.pub_cert.public_bytes(Encoding.PEM).decode('utf-8')

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
                                }, headers={"content-type": "application/x-www-form-urlencoded; charset=UTF-8"})

        result_code_match = re.search(r"'code' : '(.)'", res.text)
        if result_code_match is None:
            raise HometaxException(f'홈택스 서버 오류입니다. 홈택스 응답: {res.text}')

        result_code = result_code_match.group(1)
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
        self.request_permission(screen_id='UTXPPABA14')

        nts = random_second()
        res = self.request_action(
            action_id='ATXPPABA003R02',
            screen_id='UTXPPABA14',
            payload=json.dumps({
                "crpBmanPkcRgtNbSu": "",
                "crpPkcRgtVrfYn": "",
                "ntplBmanCrpBmanCl": "",
                "tin": "",
                "txprDscmNo": registration_no}
            ) + f'<nts<nts>nts>{nts}mAGVLUUQsmZ8Uv9YJj9bAtbDAQARJTjesj6HaT{nts - 11}').json()

        res = self.request_action(
            'ATXPPZXA001R01',
            'UTXPPABA14',
            payload=f"{{}}<nts<nts>nts>{nts}dGGBLG2rRWBeuYMviAZyJjAphI9Y3wCmWhg1y84EU{nts - 11}").json()
        pckEncSsn = res['pkcEncSsn']

        with open_files(cert_paths) as files:
            sign = load_cert(files, prikey_password)

        if len(cert_paths) == 1:
            p = subprocess.Popen(['openssl', 'pkcs12', '-info', '-provider', 'legacy', '-provider', 'default',
                                  '-in', cert_paths[0], '-nodes', '-nocerts', '-passin',
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
        cert = sign.pub_cert.public_bytes(Encoding.PEM).decode('utf-8')

        res = self.request_action(
            action_id='ATXPPABA001C01',
            screen_id='UTXPPABA14',
            payload=json.dumps({
                'cert': cert,
                'hashCntn': '',
                'logSgnt': logSgnt,
                'pkcCertClCd': '',
                'pkcEncSsn': '',
                'randomEnc': randomEnc,
                'skey': '',
                'tin': '',
                'txprDscmNo': registration_no,
            }) + f'</map><nts<nts>nts>{nts}b8FxcemzOmtdbg6smXGQTS9XHdH665qRZQSiW1XfXTg{nts - 11}').json()
        if res['resultMsg']['result'] != self.LOGIN_SUCCESS_CODE:
            if res['resultMsg']['msg'] in ['선택하신 인증서는 이미 등록된 인증서 입니다.']:
                return res['resultMsg']['msg']
            raise Exception(res['resultMsg']['msg'])
        return res['resultMsg']['msg']

    def fetch_user_and_traders(self):
        self.deselect_trader()

        res_json = self.session.post('https://www.hometax.go.kr/permission.do',
                                params={"screenId": "index"},
                                data='<map id="postParam"><popupYn>false</popupYn></map>'.encode('utf-8'),
                                headers={'Content-Type': "application/xml; charset=UTF-8"}).json()
        self.check_authenticated(res_json)
        pubcUserNo = res_json['resultMsg']['sessionMap']['pubcUserNo']
        nts = random_second()
        res_json = self.request_action(
            action_id='ATXPPAAA001R22',
            screen_id='UTXPPAAA10',
            payload=json.dumps({"pubcUserNo": pubcUserNo, "userType": "B", "cncClCd": "", "arsPswdAltYn": "", "jntCnt": ""})
                    + f'<nts<nts>nts>{nts}BfI2b32na00UC4Gq5TCUjAlsw7uURISbBokVb2ShBc0{nts - 11}').json()

        self.user_info = model_from_hometax_json(홈택스사용자, res_json['pubcUserJnngInfrAdmDVO'])
        # self.user_tin = res_json.find('.//map[@id="sessionMap"]/tin').text
        if self.user_info.사용자구분 == 홈택스사용자구분코드.개인:
            self.개인사업자_list = self.fetch_traders()
        else:
            self.selected_trader = self.trader_info()

    def fetch_traders(self):
        nts = random_second()
        res_json = self.request_action(
            action_id='ATXPPAAA003R01',
            screen_id='UTXPPAAA24',
            payload=f'{{}}'
                    f'<nts<nts>nts>{nts}NJ3QcOLdNy8YZIojAqeUQiS6YP653gruVRI9JbNVw{nts - 11}').json()
        elements = res_json.get('bmanBscInfrInqrDVOList')

        if elements is None:
            if res_json.find('.//msg') is None or '사업자 변경대상이 아님' not in res_json.find('.//msg').text:
                logging.error(ElementTree.tostring(res_json, encoding='unicode'), stack_info=True)
            return []

        return [{
            '사업자등록번호': element['txprDscmNoEncCntn'],
            'tin': element['tin'],
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

    def cookies(self):
        COOKIE_ATTRS = ["version", "name", "value", "port", "domain", "path", "secure", "expires", "discard", "comment",
                        "comment_url", "rfc2109"]
        return [{attr: getattr(cookie, attr) for attr in COOKIE_ATTRS} for cookie in self.session.cookies]

    def request_action_xml(self, action_id, screen_id, real_screen_id='', payload: str = None):
        return ensure_xml_response(self.request_action,
                                   action_id,
                                   screen_id,
                                   real_screen_id=real_screen_id,
                                   payload=payload.encode('utf8'),
                                   content_type='application/xml; charset=UTF-8')

    def request_action_json(self, action_id, screen_id, json: dict, real_screen_id='', popup_yn='false', subdomain: str = None, nts_postfix=True):
        # TODO 응답 오류 처리
        # 오류 예시: {'resultMsg': {'detailMsg': '', 'msg': '6개월이상은 조회할 수 없습니다. \n 조회에 실패 실패하였습니다.', 'exceptType': 'APPLICATION', 'serviceTxId': 'PTEET1103_ATEETBDA001R01_T00799_1731908564438', 'detailLogYn': 'N', 'code': 'ETICMZ0008', 'result': 'F'}}
        res = self.session.post(f'https://{subdomain + '.' if subdomain else ''}hometax.go.kr/wqAction.do',
                                params={"actionId": action_id, "screenId": screen_id, "popupYn": popup_yn,
                                         "realScreenId": real_screen_id},
                                data=self.nts_postfix_added(json) if nts_postfix else json_minified_dumps(json),
                                headers={'Content-Type': 'application/json'}, timeout=20)
        try:
            data = res.json()
            if data['resultMsg']['result'] != self.LOGIN_SUCCESS_CODE:
                raise HometaxException(data['resultMsg']['detailMsg'] or data['resultMsg']['msg'])
            return data
        except JSONDecodeError as e:
            raise HometaxException(f'홈택스 응답오류: {res.text}')


    def paginate_action_json(self, action_id, screen_id, json: dict, real_screen_id='', subdomain: str = None,
                             page_begin=1, page_end=None):
        page = page_begin
        while True:
            pageInfoVO = {
                'pageNum': page, 'pageSize': self.PAGE_SIZE, 'totalCount': 0
            }
            data = self.request_action_json(action_id, screen_id,
                                            json | {'pageInfoVO': pageInfoVO},
                                            real_screen_id, subdomain=subdomain)
            try:
                yield from data[next(k for k in data if k.endswith('VOList'))]
            except StopIteration:
                return

            if 'pageInfoVO' not in data:
                return # 페이지 정보가 없으면 더 이상 페이지가 없다고 가정한다.

            if data['pageInfoVO']['totalCount'] is None:
                raise Exception(f'홈택스 응답 오류: {data}')

            if page_end and page >= page_end:
                return

            if page * self.PAGE_SIZE > data['pageInfoVO']['totalCount']:
                return

            page += 1
            # 홈택스 쓰로틀링에 걸리는 걸 방지하기 위해 페이지마다 간격을 둔다.
            time.sleep(Throttled.wait)

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
        res = self.request_action(action_id='ATXPPAAA003A01',
                            screen_id='UTXPPAAA24',
                            payload=json.dumps({'tin': found['tin']}) +
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
            data=json_minified_dumps({"tin": self.tin, "txprClsfCd": '02', "txprDscmNo": "", "txprDscmNoClCd": "",
                                      "txprDscmDt": "", "searchOrder": "02/01", "outDes": "bmanBscInfrInqrDVO",
                                      "txprNm": "", "crpTin": "", "mntgTxprIcldYn": "", "resnoAltHstrInqrYn": "",
                                      "resnoAltHstrInqrBaseDtm": "", "sameBmanInqrYn": "N", "rpnBmanRetrYn": "N"})
                 + f'<nts<nts>nts>{nts}rjNjDYrX04H1ZeoLR7s39xGAggSKKn7ZTGjjfyMK0{nts - 11}',
            headers={'Content-Type': "application/json"})

        element = res.json()['bmanBscInfrInqrDVO']
        if element is None:
            logging.error(f'trader_info none element: {res.text}', extra=dict(text=res.text), stack_info=True)
            raise Exception('사업자 정보를 불러오지 못했습니다. 다시 시도해주세요.')

        self.request_permission(screen_id='UTXPPBAA69')
        nts = random_second()
        # 마이홈택스 - 기타 세무정보 - 사업자등록사항 및 담당자 안내
        res = self.session.post(
            "https://hometax.go.kr/wqAction.do?actionId=ATXPPBAA001R36&screenId=UTXPPBAA70&popupYn=true&realScreenId=",
            data=json.dumps({"rprsTin": "", "tin": self.tin})
                 + f'</map><nts<nts>nts>{nts}74JxrC2hphMsLLv7deT0nri5fT4KO9iHHdSTK9SATM{nts - 11}',
            headers={'Content-Type': "application/xml; charset=UTF-8"})

        detail = res.json().get('bmanBscInfrInqrDVOList')
        if detail is None:
            raise Throttled('사업자 등록사항을 불러오지 못했습니다. 다시 시도해주세요.')

        사업자상태 = element.get('txprStatNm')
        사업자등록사항 = next(
            (d for d in detail if d['txprDscmNoEncCntn'].replace('-', '') == element['txprDscmNoEncCntn']),
            None)

        return 납세자(
            납세자번호=element['txprDscmNoEncCntn'],
            사업자구분=홈택스사용자구분코드[element['txprDclsNm']],
            전자메일주소=element['pfbEml'],
            휴대전화번호=element['pfbTelno'],
            주소=element['roadAdr'],
            납세자명=element['txprNm'] if element['txprNm'] else element['rprsTxprNm'],
            대표자주민등록번호=element['rprsResno'].replace('-', ''),
            법인등록번호=element.get('crpno'),
            대표자명=element['rprsTxprNm'],
            업종코드=element.get('tfbCd', element.get('xmtxOrgMtfbCd', 'ZZZZZZ')),
            업태=element.get('bcNm', element.get('xmtxOrgMbcNm')) if 사업자상태 != '폐업' else None,
            종목=element.get('itmNm', element.get('xmtxOrgMitmNm')) if 사업자상태 != '폐업' else None,
            개업일=datetime.strptime(element['txprDscmDt'], '%Y%m%d').date(),
            폐업일=element.get('cfbDt') and datetime.strptime(element['cfbDt'], '%Y%m%d').date(),
            사업장소재지=element['rprsRoadAdr'],
            사업장전화번호=element['rprsHmTelno'],
            간이과세여부='간이과세자' in 사업자등록사항['bmanClNm'] if 사업자등록사항 is not None else False,
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

        response = self.session.post(f'{base_url}/permission.do?screenId={screen_id}', json={}, timeout=20)

        root = response.json()
        if subdomain and ('sessionMap' not in root['resultMsg']):
            token = self.session.post(f'https://hometax.go.kr/token.do?query=_{nts_generate_random_string(20)}', json={}).json()
            root = self.session.post(f'{base_url}/permission.do?screenId={screen_id}&domain=hometax.go.kr',
                                     json=token | {'popupYn': False,},
                                     timeout=20).json()

        if 'sessionMap' in root['resultMsg']:
            self.tin = root['resultMsg']['sessionMap']['tin']
            self.pubcUserNo = root['resultMsg']['sessionMap']['pubcUserNo']
            self.txprClsfCd = root['resultMsg']['sessionMap']['txprClsfCd']  # TODO 이 값을 요청할 때 쓰는 게 맞는지 확인 필요.
        elif subdomain:
            raise Throttled(60, '홈택스 로그인 권한 획득에 실패했습니다. 다시 시도해주세요.')

        self.subdomain = subdomain

    def request_xml(self, url, payload):
        return parse_response(self.session.post(
            url,
            data=self.nts_postfix_added(payload),
            headers={'Content-Type': "application/xml; charset=UTF-8"}
        ))

    def request_paginated_xml(self, url, payload: str):
        page = 1
        while True:
            res_xml = self.request_xml(url, payload.format(
                pageInfoVO=f'<map id="pageInfoVO">'
                           f'<pageSize>{self.PAGE_SIZE}</pageSize><pageNum>{page}</pageNum>'
                           '<totalCount>0</totalCount>'
                           f'</map>'))

            yield from res_xml.findall('.//list/map')

            if res_xml.find('.//map[@id="pageInfoVO"]/totalCount') is None:
                raise Exception('홈택스 응답 오류: ' + ElementTree.tostring(res_xml, encoding='utf-8').decode('utf-8'))

            if page * self.PAGE_SIZE > int(res_xml.find('.//map[@id="pageInfoVO"]/totalCount').text):
                return

            page += 1
            # 홈택스 쓰로틀링에 걸리는 걸 방지하기 위해 페이지마다 간격을 둔다.
            time.sleep(Throttled.wait)

    def nts_postfix_added(self, data: json):
        second = datetime.now().strftime('%0S')
        payload = json_minified_dumps(data)
        return payload + f'<nts<nts>nts>{int(second) + 11}{k4(payload, second, userId=self.user_info.홈택스ID)}{second}'

    def check_authenticated(self, res_json: dict):
        if 'resultMsg' not in res_json:
            raise Exception('홈택스 응답 오류: ' + json.dumps(res_json, ensure_ascii=False))

        if 'sessionMap' not in res_json['resultMsg']:
            raise AuthenticationFailed('홈택스에 로그인되지 않은 상태입니다.')

    def fetch_세무대리수임정보(self):
        data = self.request_action_json('ATXPPBAA001R18', 'UTXPPBAB61', {})
        for item in data['txaaInfrDVOList']:
            yield 세무대리수임정보(
                납세자=납세자(납세자번호=item['txprDscmNoEncCntn'], 납세자명=item['txprTnm']),
                세무대리인=세무대리인(
                    상호=item['txaaAdmTnmNm'],
                    사업자번호=item['bsno'],
                    전화번호=item['txaaAdmTelno'],
                    관리번호=item['txaaAdmNoEncCntn']
                ),
                정보제공범위=item['infrOfrRngCdNm'],
                수임일=item['afaDt'],
            )

    def 사업자등록상태(self):
        data = self.request_action_json('ATTABZAA001R08', 'UTEABAAA13', {
            "dongCode": self.selected_trader.납세자번호[3:5],
            "inqrTrgtClCd": "1",
            "mobYn": "N",
            "psbSearch": "Y",
            "pubcUserNo": self.pubcUserNo,
            "txprDscmNo": self.selected_trader.납세자번호,
            "userReqInfoVO": {}
        })
        result = {
            '등록상태': data['trtCntn']
        }
        result['면세구분'] = '면세' if any([keyword in result['등록상태'] for keyword in ['면세', '고유번호가 부여된 단체']]) else '과세'
        if '전환된 날짜' in result['등록상태']:
            try:
                result['과세유형전환'] = dict(
                    전환일자=datetime.strptime(re.search(r'전환된 날짜는 (.+?) 입니다.', result['등록상태']).group(1), '%Y년 %m월 %d일').date(),
                    전환유형=re.search(r'부가가치세 (.+?) 입니다.', result['등록상태']).group(1)
                )
            except Exception as e:
                logging.error(e)
        return result

    def login_as_tax_accountant(self, ctn_no, cta_password):
        res = self.request_action_json('ATXPPCBA001R17', 'index_pp', json={
            "cncClCd": "01", "srvcClCd": "01", "menuHtrnId": "100900", "ntplAthYn": "N", "ntplBmanAthYn": "N",
            "crpBmanAthYn": "Y", "txaaYn": "Y", "cshptMrntYn": "", "pubcUserNo": self.pubcUserNo,
            "dprtUserYn": "N", "athCd": "Y", "menuId": "", "prevMenuId": "", "menuTtl": ""})

        self.request_permission(screen_id='UTEABHAA19')

        res = self.request_action_json('ATXPPAAA006R43', 'UTEABHAA19', json={"ttxppal032DVO":{"menuId":""}})

        res = self.session.post('https://hometax.go.kr/pubcLogin.do?operate=txaaLogin', data={
            'txaaAdmNo': ctn_no,
            'txaaPswd': snake_oil_encrypt(cta_password),
        })

        login_res = self.parse_cta_login_response(res.text)
        postfix_str = datetime.today().strftime("%Y_%m_%d")
        res = self.session.get(
            f'https://teht.hometax.go.kr/pubcLogin.do?operate=txaaSession&txaaAdmNo={login_res[1]["lgnRsltCd"]}&postfix={postfix_str}')

        self.request_permission(screen_id='index_pp')
        res = self.session.post(
            'https://hometax.go.kr/wqAction.do?actionId=ATXPPCBA001R17&screenId=index_pp&popupYn=false&realScreenId=',
            data=json.dumps({
                "cncClCd": "01",
                "srvcClCd": "01",
                "menuHtrnId": "1100000000",
                "ntplAthYn": "N",
                "ntplBmanAthYn": "N",
                "crpBmanAthYn": "Y",
                "txaaYn": "Y",
                "cshptMrntYn": "",
                "pubcUserNo": self.pubcUserNo,
                "dprtUserYn": "N",
                "athCd": "Y",
                "menuId": "",
                "prevMenuId": "",
                "menuTtl": ""}) + '<nts<nts>nts>32k8yZmB2hWqWIwyDqt5v50oHY58M4RpVphs78jPDZg21',
            headers={'Content-Type': 'application/json'}
        )
        if res.json()['resultMsg']['result'] != self.LOGIN_SUCCESS_CODE:
            raise AuthenticationFailed('홈택스에 로그인되지 않은 상태입니다.')

        self.cta_admin_no = ctn_no

    def parse_cta_login_response(self, data: str) -> tuple[str, dict, str]:
        callback_pattern = r'(?<=nts_loginSystemCallback\()(.*?)(?=\);)'
        data1 = re.search(callback_pattern, data).group(0)
        data1 = re.sub(r'(?=\'errMsg\')(.*?)(?=\'lgnRsltCd\')', '', data1)
        data1 = data1.replace("'", '"')

        decode_pattern = r'(?<=decodeURIComponent\()(.*?)(?=\);)'
        data2 = re.search(decode_pattern, data).group(0)
        data2 = re.sub(r'(?=\'lgnRsltCd\')(.*?)(?=\'pswdErrNbcnt\')', '', data2)
        data2 = data2.replace("'", '"')

        sys_code = re.search(r'(?<=").*?(?=")', data1).group(0)

        json_str = re.search(r'(?<=\,)(.*?)(?<=\})', data1).group(0)
        parsed_json = json.loads(json_str)

        err_msg = re.search(r'(?<=").*?(?=")', data2).group(0)
        err_msg = unquote(err_msg).replace('+', ' ').replace('\\n', '\n')

        return sys_code, parsed_json, err_msg


with open(os.path.dirname(__file__) + '/hometax_xml_fields.yml', encoding='utf-8') as f:
    HOMETAX_XML_FIELDS = yaml.safe_load(f)


def model_from_hometax_xml(model_class, element: Element):
    return model_class(**{HOMETAX_XML_FIELDS[model_class.__name__][child.tag]: child.text
                          for child in element if HOMETAX_XML_FIELDS[model_class.__name__].get(child.tag)})


T = TypeVar("T")


def model_from_hometax_json(model_class: T, data: dict) -> T:
    return model_class(**{HOMETAX_XML_FIELDS[model_class.__name__][key]: value
                          for key, value in data.items() if HOMETAX_XML_FIELDS[model_class.__name__].get(key)})


def find_first_value(element, *names, default=''):
    for name in names:
        if element.find(name) is not None and element.find(name).text:
            return element.find(name).text

    return default
