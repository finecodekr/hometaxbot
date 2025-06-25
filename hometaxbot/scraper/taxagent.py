"""
홈택스에 세무대리인으로 로그인했을 때 보이는 메뉴에서 스크래핑하는 기능들.
"""
from datetime import date

from hometaxbot import models
from hometaxbot.scraper import HometaxScraper


def 수임납세자(scraper: HometaxScraper, begin: date, end: date):
    scraper.session.get('https://hometax.go.kr/websquare/websquare.html?w2xPath=/ui/pp/index_pp.xml&tmIdx=48&tm2lIdx=4804000000&tm3lIdx=4804040000')

    scraper.request_permission(screen_id='index_pp')

    res = scraper.request_action_json('ATXPPCBA001R17', 'index_pp', json={
        "cncClCd": "01",
        "srvcClCd": "01",
        "menuHtrnId": "4800000000",
        "ntplAthYn": "N",
        "ntplBmanAthYn": "N",
        "crpBmanAthYn": "Y",
        "txaaYn": "Y",
        "cshptMrntYn": "",
        "pubcUserNo": scraper.pubcUserNo,
        "dprtUserYn": "N",
        "athCd": "Y",
        "menuId": "",
        "prevMenuId": "",
        "menuTtl": ""
    })
    res = scraper.session.post('https://hometax.go.kr/userAthEvtxMenuUtil', data={'type': 6})
    res = scraper.request_action_json('ATXPPCBA001R019', 'index_pp', json={
        'scrnId': "4804040000", 'pageInfoVO': {'totalCount': "0", 'pageSize': "10", 'pageNum': "1"}
    }, nts_postfix=False)
    res = scraper.request_action_json('ATXPPCBA001R020', 'index_pp', json={
        'scrnId': "4804040000", 'pageInfoVO': {'totalCount': "0", 'pageSize': "10", 'pageNum': "1"}
    }, nts_postfix=False)
    res = scraper.request_action_json('ATXPPAAA001R037', 'index_pp', json={"ttxppal032DVO":{"menuId":""}})

    scraper.request_permission('teht', 'UTEABHAA03')
    for item in scraper.paginate_action_json('ATEABHAA001R10', 'UTEABHAA03', json={
        "afaDtChnfTrgtYn": "",
        "afaEndDt": end.strftime("%Y%m%d"),
        "afaStrtDt": begin.strftime("%Y%m%d"),
        "afdsCl": "1",
        "excelPageNum": "",
        "excelPageSize": "",
        "excelYn": "N",
        "flag": "",
        "txaaAdmNo": scraper.cta_admin_no,
        "txprDscmNoEncCntn": ""
    }, subdomain='teht'):
        yield models.세무대리수임정보(
            납세자=models.납세자(
                납세자번호=item['bsno'],
                납세자명=item['tnmNm'],
                휴대전화번호=item['telnoEncCntn'],
                전자메일주소=item['emlAdrEncCntn'],
                대표자명=item['txprNm'],
                대표자주민등록번호=item['resno']
            ),
            수임일=item['afaDt'],
            동의일=item['agrDt'],
            정보제공범위=''
        )
