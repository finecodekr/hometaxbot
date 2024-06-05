from datetime import date
from typing import Generator

from hometaxbot import models
from hometaxbot.scraper import HometaxScraper
from hometaxbot.scraper import model_from_hometax_xml


def 전자신고결과조회(scraper: HometaxScraper, begin: date, end: date):
    scraper.request_permission('teht', 'UTERNAAZ43')

    for 세목코드 in {'10': '종합소득세', '14': '원천세', '31': '법인세', '41': '부가세'}:
        for element in scraper.request_paginated_xml(
                'https://teht.hometax.go.kr/wqAction.do'
                '?actionId=ATERNABA016R14&screenId=UTERNAAZ43&popupYn=false&realScreenId=UTERNAAZ43',
                payload=f'<map id="ATERNABA016R14">'
                     f'<pubcUserNo>{scraper.pubcUserNo}</pubcUserNo>'
                     f'<rtnCvaId/>'
                     f'<rtnDtSrt>{begin.strftime("%Y%m%d")}</rtnDtSrt><rtnDtEnd>{end.strftime("%Y%m%d")}</rtnDtEnd>'
                     f'<startBsno/><endBsno/><itrfCd>{세목코드}</itrfCd><befCallYn/><gubun/>'
                     f'<txprRgtNo>{scraper.selected_trader.납세자번호}</txprRgtNo>'
                     f'<ntplInfpYn>Y</ntplInfpYn><sbmsMatePubcPrslBrkdYn>Y</sbmsMatePubcPrslBrkdYn>'
                     f'<tin/><wrtnRtnYn>N</wrtnRtnYn>{{pageInfoVO}}</map>'):
            yield model_from_hometax_xml(models.전자신고결과조회, element)


def 납부내역(scraper: HometaxScraper, begin: date, end: date) -> Generator[models.납부내역, None, None]:
    scraper.request_permission('teht')
    for element in scraper.request_paginated_xml(
            'https://teht.hometax.go.kr/wqAction.do?actionId=ATERMAAA001R01&screenId=UTERMAAD01&popupYn=false&realScreenId=',
            payload='<map id="ATERMAAA001R01">'
                 f'<pmtDtStrt>{begin.strftime("%Y%m%d")}</pmtDtStrt><pmtDtEnd>{end.strftime("%Y%m%d")}</pmtDtEnd>'
                 f'<inqrClCd>01</inqrClCd><tin>{scraper.tin}</tin><excelYn>N</excelYn>{{pageInfoVO}}</map>'):
        yield model_from_hometax_xml(models.납부내역, element)


def 환급금조회(scraper: HometaxScraper, begin: date, end: date) -> Generator[models.환급금조회, None, None]:
    scraper.request_permission('teht')
    for element in scraper.request_paginated_xml(
            'https://teht.hometax.go.kr/wqAction.do?actionId=ATERDAAA001R01&screenId=UTERDAAA01&popupYn=false&realScreenId=',
            payload=f'<map id="ATERDAAA001R01">'
                 f'<strtDt>{begin.strftime("%Y%m%d")}</strtDt><endDt>{end.strftime("%Y%m%d")}</endDt>'
                 f'<inqrClCd/><txaaYn>N</txaaYn>{{pageInfoVO}}</map>'):
        yield model_from_hometax_xml(models.환급금조회, element)
