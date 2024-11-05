import json
import random
import re
import time
from xml.etree import ElementTree

import requests.adapters
import urllib3

from requests import Response

from hometaxbot import Throttled, HometaxException


def action_params(action, screen):
    return f"actionId={action}&screenId={screen}&popupYn=false&realScreenId="


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

    element = ElementTree.fromstring(re.sub(' xmlns="[^"]+"', '', response.text, count=1))
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


class XMLValueFinder:
    element: ElementTree.Element

    def __init__(self, element):
        self.element = element

    def get(self, path, default=None):
        found = self.element.find(path)
        if found is not None:
            return found.text

        return default

    def sub_finders(self, path):
        return (XMLValueFinder(e) for e in self.element.findall(path))


def get_quarter_by_date(date):
    return int((date.month - 1) / 3 + 1)


def json_minified_dumps(obj):
    return json.dumps(obj, separators=(',', ':'))