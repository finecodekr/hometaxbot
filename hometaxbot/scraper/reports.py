import base64
import json
import re
from datetime import date
from io import BytesIO
from typing import Generator

import dateutil.parser
import httpx

from hometaxbot import models
from hometaxbot.scraper import HometaxScraper, model_from_hometax_json, json_minified_dumps


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


def 체납내역(scraper: HometaxScraper, begin: date, end: date) -> Generator[models.체납내역, None, None]:
    # My홈택스 체납
    scraper.request_permission(screen_id='UTXPPBAB73')
    for element in scraper.paginate_action_json(
            'ATXPPBAA001R17', 'UTXPPBAB73',
            json={"endDt": "",
                  "ntplCrpClCd": "03",
                  "strtDt": "",
                  "tin": scraper.tin,
                  "survTtl": ""}):
        yield model_from_hometax_json(models.체납내역, element)


def 고지내역(scraper: HometaxScraper, begin: date, end: date) -> Generator[models.고지내역, None, None]:
    # My홈택스 고지
    scraper.request_permission(screen_id='UTXPPBAB72')
    for element in scraper.paginate_action_json(
            'ATXPPBAA001R11', 'UTXPPBAB72',
            json={"endDt": end.strftime("%Y%m%d"),
                  "ntplCrpClCd": "03",
                  "strtDt": begin.strftime("%Y%m%d"),
                  "tin": scraper.tin,
                  "survTtl": ""}):
        yield model_from_hometax_json(models.고지내역, element)


def 신고서_납부서(scraper: HometaxScraper, begin: date, end: date) -> Generator[models.전자신고_신고서_납부서, None, None]:
    scraper.request_permission(screen_id='UTERNAAZ91')
    for item in scraper.paginate_action_json('ATERNABA016R01',
                                             'UTERNAAZ91',
                                             real_screen_id='UTERNAAZ91',
                                             subdomain='teht',
                                             json={
                                                 "befCallYn": "",
                                                 "dprtUserId": "",
                                                 "itrfCd": "22",
                                                 "mdfRtnPyppApplcCtl": "",
                                                 "ntplInfpYn": "Y",
                                                 "pubcUserNo": scraper.pubcUserNo,
                                                 "rtnDtEnd": end.strftime("%Y%m%d"),
                                                 "rtnDtSrt": begin.strftime("%Y%m%d"),
                                                 "sbmsMatePubcPrslBrkdYn": "N",
                                                 "scrnId": "UTERNAAZ91",
                                                 "startBsno": "",
                                                 "stmnWrtMthdCd": "99",
                                                 "tin": "",
                                                 "txprRgtNo": "",
                                                 "rtnCvaId": "",
                                                 "endBsno": "",
                                                 "gubun": "",
                                             }):

        신고서_clip_uid = clipreport_신고서(scraper, item['rtnCvaId'])
        신고서_data = clip_data(scraper, 신고서_clip_uid)

        납세자_obj = models.납세자(
            납세자번호=신고서_data['pageList'][0]['d'][0]['b'][0][1][2][6][27][3][2]['a'].split(',')[0],
            납세자명=item['txprNm']
        )

        bills_data = scraper.request_action_json('ATERNZZZ005R01', 'UTERNAAZ70', subdomain='teht', json={
            "pubcUserNo": "0",
            "rtnCvaId": item['rtnCvaId'],
            "itrfCd": "22", "txprNo": "", "txprNm": "", "rcatDtm": "", "gubun": "4", "trtpDdt": "", "rcatNo": "",
            "regNo": "", "txamtYn": ""})
        for bill in bills_data['elctPntPblNoInqrDVOList']:
            res = scraper.session.post('https://sesw.hometax.go.kr/serp/clipreport.do', data={
                'param': clipreport_param(bill, cookie_TEHTsessionID=scraper.session.cookies['TEHTsessionID'])
            })
            match = re.search(r"'wait':0.[0-9],'uid':'([^']+)'", res.text)
            if match:
                clip_uid = match.group(1)
            else:
                raise Exception('clip uid not found', res.text)

            clip_data(scraper, clip_uid)

            res = scraper.session.post('https://sesw.hometax.go.kr/serp/ClipReport4/Clip.jsp', data={
                'ClipID': 'R16',
                'aliveReport': 'true',
                'uid': clip_uid,
                'clipUID': clip_uid,
                's_time': 't341'
            })

            res = scraper.session.post('https://sesw.hometax.go.kr/serp/ClipReport4/Clip.jsp', data={
                "ClipID": "R09S1",
                "uid": clip_uid,
                "clipUID": clip_uid,
                "path": "/serp",
                "optionValue": '{"exportType":2,"name":"JUVDJUEwJTg0JUVDJUIyJUI0JUVDJUEwJTgxJUVDJTlBJUE5","pageType":1,"startNum":1,"endNum":1,"option":{"isSplite":false,"spliteValue":1,"userpw":"","textToImage":false,"importOriginImage":false,"removeHyperlink":false,"fileNames":[],"splitPage":0}}',
                "is_ie": 'true',
                "exportN": "JUVDJUEwJTg0JUVDJUIyJUI0JUVDJUEwJTgxJUVDJTlBJUE5",
                "exportType": 2,
            })
            res = scraper.session.post('https://sesw.hometax.go.kr/serp/ClipReport4/Clip.jsp', data={
                'ClipID': 'R09S2',
                'uid': clip_uid,
                'clipUID': clip_uid,
                's_time': 't535'
            })
            with httpx.Client(http2=True, cookies=scraper.session.cookies) as client:
                res = client.post('https://sesw.hometax.go.kr/serp/ClipReport4/Clip.jsp', data={
                    "ClipID": "R09S3",
                    "uid": clip_uid,
                    "clipUID": clip_uid,
                    "path": "/serp",
                    "optionValue": '{"exportType":2,"name":"JUVDJUEwJTg0JUVDJUIyJUI0JUVDJUEwJTgxJUVDJTlBJUE5","pageType":1,"startNum":1,"endNum":1,"option":{"isSplite":false,"spliteValue":1,"userpw":"","textToImage":false,"importOriginImage":false,"removeHyperlink":false,"fileNames":[],"splitPage":0}}',
                    "is_ie": 'true',
                    "exportN": "JUVDJUEwJTg0JUVDJUIyJUI0JUVDJUEwJTgxJUVDJTlBJUE5",
                    "exportType": 2,
                    "isSmartPhone": 'false',
                }, headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7,ja;q=0.6",
                    "Cache-Control": "max-age=0",
                    "Connection": "keep-alive",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Host": "sesw.hometax.go.kr",
                    "Origin": "https://sesw.hometax.go.kr",
                    "Referer": "https://sesw.hometax.go.kr/serp/clipreport.do",
                    "Sec-Fetch-Dest": "iframe",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
                    "sec-ch-ua": '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"macOS"'
                })

                yield models.전자신고_신고서_납부서(
                    납세자=납세자_obj,
                    # 신고내역=models.신고내역(),
                    신고서_data=신고서_data,
                    납부내역=models.납부내역(
                        세무서코드=bill['txhfOgzCd'],
                        세무서명=bill['ogzNm'],
                        납부일=dateutil.parser.parse(bill['trtpDdt']),
                        금액=bill['ogntxSbtrPmtTxamt'],
                        전자납부발행번호=bill['elctPmtPblNo'],
                        신고연월=bill['itrfYm'],
                        결정구분=bill['dcsClCd'],
                        세목=bill['itrfNm'],
                        세목코드=bill['itrfCd'],
                    ),
                    납부서_pdf=BytesIO(res.content),
                )


def clipreport_param(item, cookie_TEHTsessionID):
    return json_minified_dumps({
        "options": {
            "visibles": {
                "open": 0,
                "export": 1,
                "exporthwp": 0
            },
            "exports": {
                "xls": 0,
                "xlsx": 0,
                "pdf": 1,
                "hwp": 0,
                "rtf": 0,
                "ppt": 0,
                "pptx": 0,
                "html5": 0,
                "hancell": 0,
                "doc": 0,
                "jpg": 0,
                "txt": 0,
                "docx": 0
            },
            "fileNames": {
                "xls": "엑셀",
                "all": "전체적용"
            },
            "renderingMode": "client"
        },
        "type": "S",
        "fileName": "te/rm/a/a/RTERMAA001",
        "xpath": "root/pubcRomCmnDVOList/rows",
        "datatype": "json",
        "rptSort": "HTML",
        "reqParams": {
            "attrYm": item['sbmsYm'],
            "pmtYm": item['pymnYm'],
            "scrnId": "01",
            "itrfCd": "22",
            "itrfNm": "양도소득세",
            "itrfYm": item['itrfYm'],
            "dcsClCd": "3",
            "elctPmtPblNo": item['elctPmtPblNo'],
            "txprClsfCd": "02",
            "tin": item['pmtDutyTin'],
            "impsTrgtTin": item['pmtDutyTin'],
            "pmtDutyTin": item['pmtDutyTin'],
            "pmtEdctxDfstxRomAmt": 0,
            "pmtDdt": item['trtpDdt'],
            "pageSize": "40",
            "pageNum": "1",
            "rptType": "HTML",
            "actionId": "ATERMAAA004P01",
            "screenId": "UTERNAAZ70",
            "voSepChar": "|",
            "dataSepChar": ",",
            "valSepChar": ":",
            "useType": "clip",
            "b": "54xTpHwwYcCWbwlheknGN848bfeN79wLsl9NTqdrnq2Ak39",
            "bb": "mmiKII6pJC5fYeNYzkf3dH3JkRhiLXdsxhCAizwbvc"
        },
        "rptParams": {
            "param1": "",
            "param2": ""
        },
        "actionId": "ATERMAAA004P01",
        "targetWas": "https://teht.hometax.go.kr",
        "printType": "in",
        "multiple": False,
        "width": 750,
        "height": 780,
        "viewType": "viewer",
        "cookie": "TEHTsessionID=" + cookie_TEHTsessionID,
    })


def clipreport_신고서(scraper: HometaxScraper, 신고서번호: str):
    res = scraper.session.post('https://sesw.hometax.go.kr/serp/clipreport.do', data={
        'param': json_minified_dumps({
            "options": {
                "visibles": {
                    "open": 0,
                    "export": 0,
                    "exportxls": 0,
                    "exporthwp": 0,
                    "exportpdf": 0
                },
                "exports": {},
                "fileNames": {
                    "all": "양도소득과세표준 신고 및 납부계산서"
                },
                "removeChar": True,
                "renderingMode": "client"
            },
            "type": "S",
            "fileName": "/tt/rn/a/a/RTIRNAA508",
            "reqParams": {
                "rtnCvaId": "202504810000004390869663",
                "rptInqrCl": "11",
                "frmlCd": "C116300",
                "rptDataPageInfoYn": "N",
                "pageNum": "1",
                "ntplInfpYn": "Y",
                "actionId": "ATTRNABA108P01",
                "screenId": "UTERNAAZ34",
                "voSepChar": "|",
                "dataSepChar": ",",
                "valSepChar": ":",
                "useType": "clip",
                "b": "49O4EFVTuvmd8hGce6rQXv6UqzVqLVnCPYZEcAdnbDv6M34",
                "bb": "4NEtRlyrwnOQlAGo4r3imJ9PvSJnjGbTsU9pkVDLBE"
            },
            "actionId": "ATTRNABA108P01",
            "rptSort": "HTML",
            "viewType": "frame",
            "frameName": "iframe2_UTERNAAZ34",
            "targetWas": "https://teht.hometax.go.kr",
            "printType": "in",
            "multiple": False,
            "width": 750,
            "height": 780,
            "cookie": f"TEHTsessionID={scraper.session.cookies['TEHTsessionID']}",
            "datatype": "json"
        })
    })

    match = re.search(r"'wait':0.[0-9],'uid':'([^']+)'", res.text)
    if match:
        return match.group(1)
    else:
        raise Exception('clip uid not found', res.text)


def clip_data(scraper: HometaxScraper, clip_uid: str):
    res = scraper.session.post('https://sesw.hometax.go.kr/serp/ClipReport4/Clip.jsp', data={
        'ClipID': 'R03',
        'uid': clip_uid,
        'clipUID': clip_uid,
        's_time': 't278'
    })

    res = scraper.session.post('https://sesw.hometax.go.kr/serp/ClipReport4/Clip.jsp', data={
        'uid': clip_uid,
        'clipUID': clip_uid,
        'ClipType': 'DocumentPageView',
        'ClipData': json_minified_dumps({"reportkey": clip_uid, "isMakeDocument": True, "pageMethod": 0}),
    })

    return json.loads(base64.b64decode(res.json()['resValue']['viewData']))