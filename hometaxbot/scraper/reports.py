from datetime import date
from typing import Generator

from hometaxbot import models
from hometaxbot.scraper import HometaxScraper, model_from_hometax_json
from hometaxbot.scraper import model_from_hometax_xml


def 전자신고결과조회(scraper: HometaxScraper, begin: date, end: date):
    scraper.request_permission('teht', 'UTERNAAZ43')

    for 세목코드 in {'10': '종합소득세', '14': '원천세', '31': '법인세', '41': '부가세'}:
        for element in scraper.paginate_action_json(
                'ATERNABA016R14', 'UTERNAAZ43', real_screen_id='UTERNAAZ43', subdomain='teht',
                json={
                    "befCallYn": "",
                    "itrfCd": 세목코드,
                    "mdfRtnPyppApplcCtl": "100202 410202 330202 100203 410203 310203 450202 220202 220203 320202 240202 240203",
                    "ntplInfpYn": "Y",
                    "pubcUserNo": scraper.pubcUserNo,
                    "rtnDtEnd": end.strftime("%Y%m%d"),
                    "rtnDtSrt": begin.strftime("%Y%m%d"),
                    "sbmsMatePubcPrslBrkdYn": "Y",
                    "startBsno": "",
                    "tin": "",
                    "txprRgtNo": scraper.selected_trader.납세자번호,
                    "wrtnRtnYn": "N",
                    "rtnCvaId": "",
                    "endBsno": "",
                    "gubun": "",
                    "resultCnt": "0",
                    "pageSize": "0",
                    "pageNum": "0",
                }):
            yield model_from_hometax_json(models.전자신고결과조회, element)


def 납부내역(scraper: HometaxScraper, begin: date, end: date) -> Generator[models.납부내역, None, None]:
    scraper.request_permission('teht')
    for element in scraper.paginate_action_json(
            'ATERMAAA001R01', 'UTERMAAD01', subdomain='teht',
            json={
                "excelYn": "N",
                "inqrClCd": "01",
                'lgnUserTxprDscmNo': scraper.selected_trader.납세자번호,
                "pmtDtEnd": end.strftime("%Y%m%d"),
                "pmtDtStrt": begin.strftime("%Y%m%d"),
                "tin": scraper.tin,
            }):
        yield model_from_hometax_json(models.납부내역, element)


def 환급금조회(scraper: HometaxScraper, begin: date, end: date) -> Generator[models.환급금조회, None, None]:
    scraper.request_permission('teht')
    for element in scraper.paginate_action_json(
            'ATERDAAA001R01', 'UTERDAAA01', subdomain='teht',
            json={
                "inqrClCd": "",
                "strtDt": begin.strftime("%Y%m%d"),
                "endDt": end.strftime("%Y%m%d"),
                'txaaId': '',
                "txaaYn": "N",
                'txprDscmNo': '',
            }):
        yield model_from_hometax_json(models.환급금조회, element)
