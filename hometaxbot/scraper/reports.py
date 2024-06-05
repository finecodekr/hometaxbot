from datetime import date

from hometaxbot import models
from hometaxbot.scraper import HometaxScraper
from hometaxbot.scraper import model_from_hometax_xml


def 전자신고결과조회(scraper: HometaxScraper, begin: date, end: date):
    scraper.request_permission('teht', 'UTERNAAZ43')

    for 세목코드 in {'10': '종합소득세', '14': '원천세', '31': '법인세', '41': '부가세'}:
        for element in scraper.request_paginated_xml(
                'https://teht.hometax.go.kr/wqAction.do'
                '?actionId=ATERNABA016R14&screenId=UTERNAAZ43&popupYn=false&realScreenId=UTERNAAZ43',
                payload_before_page_info=f'<map id="ATERNABA016R14">'
                     f'<pubcUserNo>{scraper.pubcUserNo}</pubcUserNo>'
                     f'<rtnCvaId/>'
                     f'<rtnDtSrt>{begin.strftime("%Y%m%d")}</rtnDtSrt><rtnDtEnd>{end.strftime("%Y%m%d")}</rtnDtEnd>'
                     f'<startBsno/><endBsno/><itrfCd>{세목코드}</itrfCd><befCallYn/><gubun/>'
                     f'<txprRgtNo>{scraper.selected_trader.납세자번호}</txprRgtNo>'
                     f'<ntplInfpYn>Y</ntplInfpYn><sbmsMatePubcPrslBrkdYn>Y</sbmsMatePubcPrslBrkdYn>'
                     f'<tin/><wrtnRtnYn>N</wrtnRtnYn>'):
            yield model_from_hometax_xml(models.전자신고결과조회, element)
