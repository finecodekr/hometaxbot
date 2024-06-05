import random
import time
from xml.etree import ElementTree

import requests.adapters
import urllib3

from requests import Response

from hometaxbot import Throttled, HometaxException


class PaginatedResponseGenerator:
    def __init__(self, page_size=10):
        self.num = 1
        self.has_next = True
        self.page_size = page_size

    def elements(self, res: Response):
        try:
            res_xml = parse_response(res)
            yield from res_xml.findall('.//list/map')

            if res_xml.find('.//map[@id="pageInfoVO"]/totalCount') is None:
                raise Exception('홈택스 응답 오류: ' + ElementTree.tostring(res_xml, encoding='utf-8').decode('utf-8'))

            if self.num * self.page_size > int(res_xml.find('.//map[@id="pageInfoVO"]/totalCount').text):
                self.has_next = False
            else:
                self.num += 1
                # 홈택스 쓰로틀링에 걸리는 걸 방지하기 위해 페이지마다 간격을 둔다.
                time.sleep(Throttled.wait)

        except Throttled as e:
            # 홈택스 쓰로틀링에 걸리면 그냥 기다리면 다음 반복 때 그대로 다시 요청하게 된다.
            time.sleep(e.wait)

    def __next__(self):
        if self.has_next:
            return self

        raise StopIteration

    def __iter__(self):
        return self


def nts_generate_random_string(length):
    """
    홈택스 스크립트에 있는 랜덤 스트링 제너레이션 포팅
    :param length: 생성할 스트링 길이
    :return:
    """
    seed = "qwertyuiopasdfghjklzxxcvbnm0123456789QWERTYUIOPASDDFGHJKLZXCVBNBM"
    result = ''
    for i in range(length):
        result += seed[random.randint(0, len(seed) - 1)]
    return result


def check_error_on_response(response):
    if '요청하신 서비스는 현재 서비스 중지 시간 입니다' in response.text:
        raise Throttled(response.text.strip())

    if '반복적인 호출은 시스템에 부하를 줄 수 있습니다' in response.text:
        raise Throttled(response.text.strip())

    if '조회에 실패하였습니다' in response.text:
        raise Throttled(response.text.strip())

    if '서비스 실행 중 오류가 발생하였습니다.' in response.text:
        raise HometaxException(response.text)

    if response.status_code == 400:
        if 'Request Blocked' in response.text:
            raise Throttled(response.text.strip())
        raise HometaxException(response.text)


def parse_response(response):
    """
    :param response: requests.Response
    :return: validated된 reponse를 xml 파싱하여 ElementTree객체로 리턴
    """
    check_error_on_response(response)

    element = ElementTree.fromstring(response.text)
    if find_text_or_none(element, 'errorCd') in ['-9402', '-9404', '-9403', '-9405'] \
            or find_text_or_none(element, 'msg') in ['-9402', '-9404', '-9403', '-9405']:
        raise Throttled('홈택스 이중 로그인 방지로 인해 인증에 실패했습니다. 다시 시도해주세요.')

    return element


def ensure_xml_response(fn, *args, **kwargs):
    try:
        return parse_response(fn(*args, **kwargs))
    except Throttled as e:
        if e.wait:
            time.sleep(e.wait)
            return parse_response(fn(*args, **kwargs))
        else:
            raise


def find_text_or_none(element, tag_name):
    found = element.find('.//' + tag_name)
    if found is not None:
        return found.text
    return None


class CustomHttpAdapter(requests.adapters.HTTPAdapter):
    # "Transport adapter" that allows us to use custom ssl_context.

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_context=self.ssl_context)
