import csv
import json
import time
from datetime import date
from decimal import Decimal
from io import StringIO

import dateutil.parser
from dateutil.relativedelta import relativedelta

from hometaxbot import models, Throttled
from hometaxbot.models import 수입문서, 납세자, 연락처, 세금계산서품목
from hometaxbot.scraper import HometaxScraper, parse_response
from hometaxbot.scraper.requestutil import XMLValueFinder, action_params, get_quarter_by_date
from hometaxbot.scraper.util import split_date_range

invoice_type_choices = {
    '전자세금계산서': '01',
    '전자세금계산서_위수탁': '02',
    '전자계산서': '03',
    '전자계산서_위수탁': '04',
}


def 세금계산서(scraper: HometaxScraper, begin: date, end: date):
    scraper.request_permission('teet')
    for invoice_type in invoice_type_choices:
        for 매입매출 in ['매입', '매출']:
            위수탁 = '위수탁' in invoice_type
            prhSlsClCd = "01" if 매입매출 == "매출" else "02"
            if 위수탁:
                prhSlsClCd = "02"

            조회기준코드 = {
                '작성일자': '01',
                '발급일자': '02',
                '전송일자': '03',
            }

            for period_begin, period_end in split_date_range(begin, end, relativedelta(months=3)):
                params = {
                    "bmanCd": "00",
                    "dmnrMpbNo": "",
                    "dmnrTxprDscmNo": "",
                    "dtCl": 조회기준코드["전송일자"],
                    "etxivClsfCd": "all",
                    "etxivKndCd": "all",
                    "inqrDtEnd": period_end.strftime("%Y%m%d"),
                    "inqrDtStrt": period_begin.strftime("%Y%m%d"),
                    "isnTypeCd": "all",
                    "pageNum": "",
                    "pageSize": "10",
                    "prhSlsClCd": prhSlsClCd,
                    "screenId": "",
                    "splrMpbNo": "",
                    "splrTxprDscmNo": "",
                    "tnmNm": "",
                    "cstnBmanMpbNo": "",
                    "cstnBmanTin": scraper.tin if 위수탁 else "",
                    "dmnrTin": scraper.tin if 매입매출 == "매입" and not 위수탁 else "",
                    "dmnrTnmNm": "",
                    "etxivClCd": invoice_type_choices[invoice_type],
                    "gubunCd": "",
                    "mCd": "",
                    "mqCd": "",
                    "qCd": "",
                    "splrTin": scraper.tin if 매입매출 == "매출" and not 위수탁 else "",
                    "splrTnmNm": "",
                    "tmsnDtIn": "",
                    "tmsnDtOut": "",
                    "yCd": ""
                }
                first_page = scraper.request_action_json("ATEETBDA001R01", 'UTEETBDA01', json={
                    "cstnInfoYn": "",
                    "fleDwldYn": "",
                    "fleTp": "",
                    "icldCstnBmanInfr": "",
                    "icldLsatInfr": "N",
                    "resnoSecYn": "Y",
                    "srtClCd": "1",
                    "srtOpt": "02",
                    "etxivIsnBrkdTermDVOPrmt": params
                }, subdomain='teet')

                if first_page['pageInfoVO']['totalCount'] == 0:
                    continue

                for page in range(1, first_page['pageInfoVO']['totalCount'] // scraper.DOWNLOAD_PAGE_SIZE + 2):
                    pageInfoVO = {
                        'pageSize': scraper.DOWNLOAD_PAGE_SIZE,
                        'pageNum': page,
                        'totalCount': first_page['pageInfoVO']['totalCount']
                    }
                    res = scraper.session.post('https://teet.hometax.go.kr/wqAction.do', data={
                        'downloadParam': json.dumps({
                            "cstnInfoYn": "", "fleDwldYn": "Y", "fleTp": "txt", "icldCstnBmanInfr": "",
                            "icldLsatInfr": "", "resnoSecYn": "Y", "srtClCd": "1", "srtOpt": "01",
                            "affectedCnt": 0,
                            "pageInfoVO": pageInfoVO,
                            "excelPageInfoVO": pageInfoVO,
                            "etxivIsnBrkdTermDVOPrmt": params,
                        }),
                        'actionId': 'ATEETBDA005R04',
                        'screenId': 'UTEETBDA01',
                        'noopen': False,
                        'downloadView': 'Y'
                    })

                    reader = StringIO(res.content.decode('utf8'))
                    for i in range(4):
                        next(reader)

                    dict_reader = csv.DictReader(reader, delimiter='\t')
                    for row in dict_reader:
                        yield scrape_세금계산서_detail(scraper, row['승인번호'].replace('-', ''), row['전송일자'])
                        time.sleep(Throttled.wait)


def scrape_세금계산서_detail(scraper: HometaxScraper, etan, 전송일자):
    """전송일자는 세금계산서 XML 내에 없고 홈택스 시스템에서 관리하는 값이기 때문에 외부에서 전달 받아야 한다."""
    scraper.request_permission('teet')
    etan = etan.replace('-', '')
    res = scraper.session.post("https://teet.hometax.go.kr/wqAction.do",
                               data={
                                   'downloadParam': json.dumps({
                                       "fileDwnYn": "Y",
                                       "etan": etan,
                                       "etxivIsnBrkdTermDVOPrmt": {
                                           "etan": etan,
                                           "screenId": "UTEETBDA01",
                                           "slsPrhClCd": "01",
                                           "etxivClCd": "",
                                           "etxivClsfCd": "",
                                           "etxivMpbNo": "0",
                                           "etxivTin": scraper.tin,
                                           "pageNum": 1,
                                           "focus": "resultGrid_cell_0_11",
                                           "layerPopup": "Y",
                                           "callbackFn": "mf_txppWframe___close_callback_Func__1730730392626_2",
                                           "__popupName": "전자세금계산서 상세조회 팝업",
                                           "popupID": "UTEETBDA38"
                                       }
                                   }).replace(' ', ''),
                                   'actionId': 'ATEETBDA001R02',
                                   'screenId': 'UTEETBDA38',
                                   "downloadView": "Y",
                                   "noopen": False,
                               },
                               headers={'Content-Type': "application/x-www-form-urlencoded"})

    res.encoding = 'UTF-8'
    finder = XMLValueFinder(parse_response(res))

    return models.세금계산서(
        승인번호=finder.get('TaxInvoiceDocument/IssueID'),
        전송일자=전송일자,
        작성일자=finder.get('TaxInvoiceDocument/IssueDateTime'),
        세금계산서분류=finder.get('TaxInvoiceDocument/TypeCode')[:2],
        세금계산서종류=finder.get('TaxInvoiceDocument/TypeCode')[2:],
        영수청구코드=finder.get('TaxInvoiceDocument/PurposeCode'),
        수정코드=finder.get('TaxInvoiceDocument/AmendmentStatusCode'),
        당초승인번호=finder.get('TaxInvoiceDocument/OriginalIssueID'),
        비고=finder.get('TaxInvoiceDocument/DescriptionText'),
        수입문서참조=finder.get('TaxInvoiceDocument/ReferencedImportDocument') and 수입문서(
            신고번호=finder.get('TaxInvoiceDocument/ReferencedImportDocument/ID'),
            일괄발급시작일=finder.get('TaxInvoiceDocument/ReferencedImportDocument/AccetablePeriod/StartDateTime'),
            일괄발급종료일=finder.get('TaxInvoiceDocument/ReferencedImportDocument/AccetablePeriod/EndDateTime'),
            총건=finder.get('TaxInvoiceDocument/ReferencedImportDocument/ItemQuantity')),
        공급자=납세자(
            납세자번호=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/ID'),
            납세자명=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/NameText'),
            대표자명=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/SpecifiedPerson/NameText'),
            주소=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/SpecifiedAddress/LineOneText'),
            업태=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/TypeCode'),
            종목=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/ClassificationCode'),
            업종코드=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/ClassificationCode')),
        공급자연락처=연락처(
            부서명=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/DefinedContact/DepartmentNameText'),
            이름=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/DefinedContact/PersonNameText'),
            전화번호=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/DefinedContact/TelephoneCommunication'),
            이메일=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/DefinedContact/URICommunication')),
        공급받는자=납세자(
            납세자번호=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/ID'),
            납세자명=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/NameText'),
            대표자명=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/SpecifiedPerson/NameText'),
            주소=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/SpecifiedAddress/LineOneText'),
            업태=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/TypeCode'),
            종목=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/ClassificationCode'),
            업종코드=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/ClassificationCode')),
        공급받는자연락처=연락처(
            부서명=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/PrimaryDefinedContact/DepartmentNameText'),
            이름=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/PrimaryDefinedContact/PersonNameText'),
            전화번호=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/PrimaryDefinedContact/TelephoneCommunication'),
            이메일=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/PrimaryDefinedContact/URICommunication')),
        공급받는자연락처2=연락처(
            부서명=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/SecondaryDefinedContact/DepartmentNameText'),
            이름=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/SecondaryDefinedContact/PersonNameText'),
            전화번호=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/SecondaryDefinedContact/TelephoneCommunication'),
            이메일=finder.get('TaxInvoiceTradeSettlement/InvoiceeParty/SecondaryDefinedContact/URICommunication')),
        위수탁자=납세자(
            납세자번호=finder.get('TaxInvoiceTradeSettlement/BrokerParty/ID'),
            납세자명=finder.get('TaxInvoiceTradeSettlement/BrokerParty/NameText'),
            대표자명=finder.get('TaxInvoiceTradeSettlement/BrokerParty/SpecifiedPerson/NameText'),
            주소=finder.get('TaxInvoiceTradeSettlement/BrokerParty/SpecifiedAddress/LineOneText'),
            업태=finder.get('TaxInvoiceTradeSettlement/BrokerParty/TypeCode'),
            종목=finder.get('TaxInvoiceTradeSettlement/BrokerParty/ClassificationCode'),
            업종코드=finder.get('TaxInvoiceTradeSettlement/BrokerParty/ClassificationCode')),
        위수탁자연락처=연락처(
            부서명=finder.get('TaxInvoiceTradeSettlement/BrokerParty/SecondaryDefinedContact/DepartmentNameText'),
            이름=finder.get('TaxInvoiceTradeSettlement/BrokerParty/SecondaryDefinedContact/PersonNameText'),
            전화번호=finder.get('TaxInvoiceTradeSettlement/BrokerParty/SecondaryDefinedContact/TelephoneCommunication'),
            이메일=finder.get('TaxInvoiceTradeSettlement/BrokerParty/SecondaryDefinedContact/URICommunication')),
        결제방법코드=finder.get('TaxInvoiceTradeSettlement/SpecifiedPaymentMeans/TypeCode'),
        결제금액=finder.get('TaxInvoiceTradeSettlement/SpecifiedPaymentMeans/PaidAmount'),
        공급가액=finder.get('TaxInvoiceTradeSettlement/SpecifiedMonetarySummation/ChargeTotalAmount'),
        세액=finder.get('TaxInvoiceTradeSettlement/SpecifiedMonetarySummation/TaxTotalAmount'),
        총금액=finder.get('TaxInvoiceTradeSettlement/SpecifiedMonetarySummation/GrandTotalAmount'),
        품목=[세금계산서품목(
            일련번호=f.get('SequenceNumeric'),
            공급일자=f.get('PurchaseExpiryDateTime'),
            품목명=f.get('NameText'),
            규격=f.get('InformationText'),
            비고=f.get('DescriptionText'),
            수량=f.get('ChargeableUnitQuantity'),
            단가=f.get('UnitPrice/UnitAmount'),
            공급가액=f.get('InvoiceAmount'),
            세액=f.get('TotalTax/CalculatedAmount'),
        ) for f in finder.sub_finders('TaxInvoiceTradeLineItem')]
    )


def 카드매입(scraper: HometaxScraper, begin: date, end: date):
    scraper.request_permission('tecr')

    for period_begin, period_end in split_date_range(begin, end, relativedelta(months=3)):
        for element in scraper.paginate_action_json(
                'ATECRCCA001R06', 'UTECRCB023',
                json={
                    "busnCrdcDwldFleStatCd": "",
                    "busnCrdcTrsBrkdPrhYr": "",
                    "dwldCnclFg": "",
                    "dwldFleNm": "",
                    "dwldTrsBrkdScnt": "",
                    "fleTp": "",
                    "gdncMsgCntn": "",
                    "ntplBmanAthYn": "",
                    "prhQrt": "",
                    "prhQrtEdInq": "",
                    "prhQrtStInq": "",
                    "prhQrtStrtYm": "",
                    "prhTxamtDdcYn": "all",
                    "reqCd": "",
                    "resultCd": "",
                    "rqsDt": "",
                    "rqstTxprDscmNo": "",
                    "sumTotaTrsAmt": "",
                    "tin": scraper.tin,
                    "trsDtRngEnd": period_end.strftime("%Y%m%d"),
                    "trsDtRngStrt": period_begin.strftime("%Y%m%d"),
                    "txprDclsCd": "250",
                    "upldFleNm": "",
                    "upldPsbYn": "",
                    "yearInq": "",
                },
                subdomain='tecr'):

            yield models.카드매입(
                거래일시=element['aprvDt'],
                카드번호=element['busnCrdCardNoEncCntn'],
                승인번호=element['busnCrdcTrsBrkdSn'],
                카드사=element['crcmClNm'],
                공급가액=element['splCft'],
                부가세=element['vaTxamt'],
                봉사료=element['tip'],
                총금액=element['totaTrsAmt'],
                가맹점=납세자(
                    납세자번호=element['mrntTxprDscmNoEncCntn'],
                    납세자명=element['mrntTxprNm'],
                    업종코드=element['tfbCd'],
                    업태=element['bcNm'],
                    종목=element['tfbNm'],
                ),
                가맹점유형=element['bmanClNm'],
                공제여부=element['ddcYnNm'],
                비고=element['vatDdcClNm'],
            )


def 현금영수증(scraper: HometaxScraper, begin: date, end: date):
    scraper.request_permission('tecr')

    # 현금영수증 매출
    # 매입과 달리 매출의 경우만 body를 암호화하고 있어서 일반 요청 대신 다운로드 요청으로 전환한다.
    # 처음에는 일반 요청을 해서 몇몇 정보를 받은 후 그 정보를 이용해서 다시 다운로드 요청을 한다.
    for period_begin, period_end in split_date_range(begin, end, relativedelta(months=3)):
        first_page = scraper.session.post('https://tecr.hometax.go.kr/wqAction.do', params={
            "actionId": 'ATECRCBA001R03',
            "screenId": 'UTECRCB013',
            "popupYn": "false",
            "realScreenId": ''
        }, json={
            "dprtUserYn": "N",
            "fleTp": "",
            "mrntTxprDscmNoEncCntn": "",
            "pubcUserNo": "all",
            "reqCd": "",
            "spjbTrsYn": "all",
            "spstCnfrId": "all",
            "sumTotaTrsAmt": "",
            "tin": scraper.tin,
            "trsDtRngEnd": period_end.strftime("%Y%m%d"),
            "trsDtRngStrt": period_begin.strftime("%Y%m%d"),
            "txprDscmNo": scraper.selected_trader.납세자번호,
            "totalCount": "0",
            "sumSplCft": "0",
        }).json()

        if first_page['pageInfoVO']['totalCount'] == 0:
            continue

        DOWNLOAD_PAGE_SIZE = 1000
        for page in range(1, first_page['pageInfoVO']['totalCount'] // DOWNLOAD_PAGE_SIZE + 2):
            res = scraper.session.post('https://tecr.hometax.go.kr/wqAction.do', data={
                "downloadParam": json.dumps({
                    "fleTp": "txt",
                    "pblClCd": "all",
                    "reqCd": "00",
                    "sumTotaTrsAmt": first_page['sumTotaTrsAmt'],
                    "tin": scraper.tin,
                    "trsDtRngEnd": period_end.strftime("%Y%m%d"),
                    "trsDtRngStrt": period_begin.strftime("%Y%m%d"),
                    "totalCount": 0,
                    "sumSplCft": first_page['sumSplCft'],
                    "pageInfoVO": {
                        'pageSize': DOWNLOAD_PAGE_SIZE,
                        'pageNum': page,
                        'totalCount': first_page['pageInfoVO']['totalCount']
                    },
                }),
                'actionId': 'ATECRCBA001R03',
                'screenId': 'UTECRCB013',
                'noopen': False,
                'downloadView': 'Y',
            })

            reader = StringIO(res.content.decode('utf8'))
            next(reader)  # 첫 줄에 요약 정보 건너뛰기
            reader = csv.DictReader(reader, delimiter='\t')
            for row in reader:
                yield models.현금영수증(
                    매출매입='매출',
                    거래일시=dateutil.parser.parse(row['매출일시']),
                    거래구분=row['비고'],
                    공급가액=Decimal(row['공급가액'].replace(',', '')),
                    부가세=Decimal(row['부가세'].replace(',', '')),
                    봉사료=Decimal(row['봉사료'].replace(',', '')),
                    총금액=Decimal(row['총금액'].replace(',', '')),
                    승인번호=row['승인번호'],
                    발급수단='',
                    발행구분=row['발행구분'],
                    승인구분=row['거래구분'],
                    매입자명=row['신분확인뒷4자리'],
                    가맹점=scraper.selected_trader,
                )

    # 현금영수증 매입
    for element in scraper.paginate_action_json(
            'ATECRCBA001R02', 'UTECRCB005',
            json={
                "dprtUserYn": "N",
                "fleTp": "",
                "mrntTxprDscmNoEncCntn": "",
                "pubcUserNo": "all",
                "reqCd": "",
                "spjbTrsYn": "all",
                "spstCnfrId": "all",
                "sumTotaTrsAmt": "",
                "tin": scraper.tin,
                "trsDtRngEnd": end.strftime("%Y%m%d"),
                "trsDtRngStrt": begin.strftime("%Y%m%d"),
                "txprDscmNo": scraper.selected_trader.납세자번호,
                "totalCount": "0",
                "sumSplCft": "0",
            }, subdomain='tecr'):
        finder = XMLValueFinder(element)
        yield models.현금영수증(
            매출매입='매입',
            거래일시=element['trsDtTime'],
            거래구분=element['cshptTrsTypeNm'],
            공급가액=element['splCft'],
            부가세=element['vaTxamt'],
            봉사료=element['tip'],
            총금액=element['totaTrsAmt'],
            승인번호=element['aprvNo'],
            발급수단=element['spstCnfrClNm'],
            발행구분=element.get('pblClCd'),
            승인구분=element['trsClNm'],
            매입자명=element['rcprTxprNm'],
            가맹점=납세자(
                납세자번호=element['mrntTxprDscmNoEncCntn'],
                납세자명=element['mrntTxprNm'],
                업종코드=element['tfbCd'],
                업태=element['tfbNm'],
                종목=element['itmNm'],
            ),
            공제여부=element['prhTxamtDdcClNm'] == '공제' or element['prhTxamtDdcYn'] == 'Y',
        )


def 카드매출월간집계(scraper: HometaxScraper, begin: date, end: date):
    """
    자료수집 시점에 대한 홈택스의 안내문구:
        신용카드 자료는 매월 15일경에 직전월 자료까지 포함하여 제공합니다
        현금IC카드 자료는 부가세 신고월에 직전분기 자료까지 포함하여 제공합니다
        1~3월 매출자료 :  4월 10일경 제공      4~6월 매출자료 : 7월 10일경 제공
        7~9월 매출자료 :  10월 10일경 제공   10~12월 매출자료 : 1월 10일경 제공
        판매(결제)대행 매출자료는 부가가치법 제75조에 따라 매 분기 다음 달 15일까지 제출하도록 규정되어 있습니다
        따라서, 자료수집 후 신속하게 제공할 예정입니다
        1~3월 매출자료 :  4월 17일경 제공 예정      4~6월 매출자료 : 7월 17일경 제공 예정
        7~9월 매출자료 :  10월 17일경 제공 예정   10~12월 매출자료 : 1월 17일경 제공 예정
    """
    scraper.request_permission('teht')

    element = scraper.request_xml(
        'https://teht.hometax.go.kr/wqAction.do?' + action_params('ATESFAAA014R02', 'UTESFABG35'),
        payload=f'<map id="ATESFAAA014R02">'
                f'<stlYr>{begin.year}</stlYr>'
                f'<qrtFrom>{get_quarter_by_date(begin)}</qrtFrom>'
                f'<qrtTo>{get_quarter_by_date(end)}</qrtTo>'
                f'<bsno>{scraper.selected_trader.납세자번호}</bsno>'
                f'</map>')

    for child in element.findall('.//list/map'):
        finder = XMLValueFinder(child)
        yield models.카드매출월간집계(
            거래연월=finder.get('stlYm') + '01',  # 연월 값에 01을 붙여서 날짜로 만듦
            거래건수=finder.get('sumStlScnt'),
            합계금액=finder.get('sumTipExclAmt'),
            매입처명=finder.get('txprNm'),
        )

