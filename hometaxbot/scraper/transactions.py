import csv
import json
import time
from collections import defaultdict
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from typing import Optional, Tuple

import dateutil.parser
import xlrd
from dateutil.relativedelta import relativedelta

from hometaxbot import models, Throttled
from hometaxbot.models import 수입문서, 납세자, 연락처, 세금계산서품목
from hometaxbot.scraper import HometaxScraper, parse_response
from hometaxbot.scraper.requestutil import XMLValueFinder, action_params, get_quarter_by_date
from hometaxbot.scraper.util import split_date_range
from hometaxbot.types import parse_date

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
                        'pageSize': "10",
                        'pageNum': page,
                        'totalCount': first_page['pageInfoVO']['totalCount']
                    }
                    excelPageInfoVO = {
                        'pageNum': str(page),
                        'pageSize': scraper.DOWNLOAD_PAGE_SIZE,
                        'totalCount': first_page['pageInfoVO']['totalCount']
                    }
                    res = scraper.session.post('https://teet.hometax.go.kr/wqAction.do', data={
                        'downloadParam': json.dumps({
                            "cstnInfoYn": "Y", "fleDwldYn": "Y", "fleTp": "xls", "icldCstnBmanInfr": "",
                            "icldLsatInfr": "Y", "resnoSecYn": "Y", "srtClCd": "1", "srtOpt": "01",
                            "affectedCnt": 0,
                            "pageInfoVO": pageInfoVO,
                            "excelPageInfoVO": excelPageInfoVO,
                            "etxivIsnBrkdTermDVOPrmt": params,
                        }),
                        'actionId': 'ATEETBDA005R04',
                        'screenId': 'UTEETBDA01',
                        'noopen': False,
                        'downloadView': 'Y'
                    })

                    # Excel 파일 파싱
                    excel_file = BytesIO(res.content)
                    wb = xlrd.open_workbook(file_contents=excel_file.read())

                    items_by_approval = defaultdict(list)
                    try:
                        sheet_items = wb.sheet_by_name('품목')
                        headers_items = [cell.value for cell in sheet_items.row(4)]

                        for row_idx in range(5, sheet_items.nrows):
                            row_values = [cell.value for cell in sheet_items.row(row_idx)]
                            row_data = dict(zip(headers_items, row_values))
                            
                            approval_no = str(row_data.get('승인번호', '')).strip()
                            if not approval_no:
                                continue

                            try:
                                item = 세금계산서품목(
                                    일련번호=int(row_data.get('품목순번', 0)),
                                    공급일자=parse_date(str(row_data.get('일자', ''))),
                                    품목명=str(row_data.get('품목명', '')),
                                    규격=str(row_data.get('규격', '')) if row_data.get('규격') else None,
                                    비고=str(row_data.get('비고', '')) if row_data.get('비고') else None,
                                    수량=Decimal(str(row_data['수량']).replace(',', '')) if row_data.get('수량') and str(row_data['수량']).strip() else None,
                                    단가=Decimal(str(row_data['단가']).replace(',', '')) if row_data.get('단가') else Decimal(0),
                                    공급가액=Decimal(str(row_data['공급가액']).replace(',', '')) if row_data.get('공급가액') else Decimal(0),
                                    세액=Decimal(str(row_data.get('세액', 0)).replace(',', '')) if row_data.get('세액') else Decimal(0),
                                )
                                items_by_approval[approval_no].append(item)
                            except (ValueError, KeyError):
                                continue
                    except xlrd.XLRDError:
                        pass

                    try:
                        sheet_invoice = wb.sheet_by_name('세금계산서')
                        headers_invoice = [cell.value for cell in sheet_invoice.row(5)]

                        for row_idx in range(6, sheet_invoice.nrows):
                            row_values = [cell.value for cell in sheet_invoice.row(row_idx)]
                            
                            if not row_values[1]:
                                continue
                            
                            row_data = {}
                            for i, header in enumerate(headers_invoice):
                                if i < len(row_values):
                                    if header in row_data:
                                        row_data[f'{header}_{i}'] = row_values[i]
                                    else:
                                        row_data[header] = row_values[i]
                            
                            row_data_by_index = {i: row_values[i] if i < len(row_values) else None for i in range(len(headers_invoice))}
                            row_data['_by_index'] = row_data_by_index

                            approval_no = str(row_values[1]).strip()
                            items = items_by_approval.get(approval_no, [])

                            업종, 업태 = get_업종업태(scraper, approval_no)

                            invoice = excel_row_to_세금계산서(row_data, items, headers_invoice)
                            
                            if 업종 or 업태:
                                invoice.공급받는자.종목 = 업종
                                invoice.공급받는자.업태 = 업태
                            
                            yield invoice
                    except xlrd.XLRDError:
                        continue


def get_업종업태(scraper: HometaxScraper, approval_no: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        etan = approval_no.replace('-', '')
        
        response = scraper.request_action_json(
            'ATEETBDA001R02',
            'UTEETBDA38',
            json={
                "etxivIsnBrkdTermDVOPrmt": {
                    "etan": etan,
                    "screenId": "UTEETBDA01",
                    "slsPrhClCd": "01",
                    "etxivClCd": "",
                    "etxivClsfCd": "",
                    "etxivMpbNo": "0",
                    "etxivTin": scraper.tin,                                        
                    "layerPopup": "Y",                                        
                    "popupID": "UTEETBDA38"
                }
            },
            popup_yn='true',
            real_screen_id='',
            subdomain='teet'
        )
        
        etxivIsnBrkdTermDVO = response.get('etxivIsnBrkdTermDVO', {})
        업종 = etxivIsnBrkdTermDVO.get('dmnrItmNm')
        업태 = etxivIsnBrkdTermDVO.get('dmnrBcNm')
        
        업종 = 업종 if 업종 else None
        업태 = 업태 if 업태 else None
        
        return (업종, 업태)
    except Exception:
        return (None, None)


def excel_row_to_세금계산서(row_data: dict, items: list, headers: list = None) -> models.세금계산서:
    row_by_index = row_data.get('_by_index', {})
    
    def safe_get(key, default=''):
        value = row_data.get(key, default)
        return str(value).strip() if value else default
    
    def safe_get_by_index(index, default=''):
        value = row_by_index.get(index, default)
        return str(value).strip() if value else default

    def safe_decimal(key, default=Decimal(0)):
        value = row_data.get(key, default)
        if not value:
            return default
        return Decimal(str(value).replace(',', ''))

    def safe_decimal_by_index(index, default=Decimal(0)):
        value = row_by_index.get(index, default)
        if not value:
            return default
        return Decimal(str(value).replace(',', ''))

    def safe_date(key):
        value = row_data.get(key)
        if not value:
            return None
        return parse_date(str(value))

    분류_텍스트 = safe_get('전자세금계산서 분류', '')
    종류_텍스트 = safe_get('전자세금계산서종류', '')
    
    분류 = models.세금계산서분류.세금계산서
    if '수정세금계산서' in 분류_텍스트:
        분류 = models.세금계산서분류.수정세금계산서
    elif '계산서' in 분류_텍스트 and '수정' not in 분류_텍스트:
        분류 = models.세금계산서분류.계산서
    elif '수정계산서' in 분류_텍스트:
        분류 = models.세금계산서분류.수정계산서
    
    종류 = models.세금계산서종류.일반
    if '영세율' in 종류_텍스트 and '위수탁' not in 종류_텍스트:
        종류 = models.세금계산서종류.영세율
    elif '위수탁' in 종류_텍스트 and '영세율' not in 종류_텍스트:
        종류 = models.세금계산서종류.위수탁
    elif '수입' in 종류_텍스트 and '납부유예' not in 종류_텍스트:
        종류 = models.세금계산서종류.수입
    elif '영세율위수탁' in 종류_텍스트 or ('영세율' in 종류_텍스트 and '위수탁' in 종류_텍스트):
        종류 = models.세금계산서종류.영세율위수탁
    elif '수입납부유예' in 종류_텍스트:
        종류 = models.세금계산서종류.수입납부유예
    
    영수청구_텍스트 = safe_get('영수/청구 구분', '')
    영수청구코드 = '01'
    if '청구' in 영수청구_텍스트:
        영수청구코드 = '02'

    위수탁자 = None
    위수탁자연락처 = None
    수탁사업자등록번호 = safe_get('수탁사업자등록번호')
    if 수탁사업자등록번호:
        위수탁자_상호 = safe_get_by_index(26, '')
        위수탁자 = 납세자(
            납세자번호=수탁사업자등록번호,
            납세자명=위수탁자_상호,
            대표자명=None,
            주소=None,
            업태=None,
            종목=None,
            업종코드=None,
        )

    return models.세금계산서(
        승인번호=safe_get('승인번호'),
        전송일자=safe_date('전송일자'),
        작성일자=safe_date('작성일자'),
        세금계산서분류=분류,
        세금계산서종류=종류,
        영수청구코드=영수청구코드,
        수정코드=None,
        당초승인번호=None,
        비고=safe_get('비고'),
        수입문서참조=None,
        공급자=납세자(
            납세자번호=safe_get('공급자사업자등록번호'),
            납세자명=safe_get_by_index(6),
            대표자명=safe_get_by_index(7),
            주소=safe_get_by_index(8),
            업태=None,
            종목=None,
            업종코드=None,
        ),
        공급자연락처=연락처(
            부서명='',
            이름='',
            전화번호='',
            이메일=safe_get('공급자 이메일'),
        ),
        공급받는자=납세자(
            납세자번호=safe_get('공급받는자사업자등록번호') or safe_get('공급자사업자등록번호'),
            납세자명=safe_get_by_index(11) or safe_get_by_index(6),
            대표자명=safe_get_by_index(12) or safe_get_by_index(7),
            주소=safe_get_by_index(13) or safe_get_by_index(8),
            업태=None,
            종목=None,
            업종코드=None,
        ),
        공급받는자연락처=연락처(
            부서명='',
            이름='',
            전화번호='',
            이메일=safe_get('공급받는자 이메일1') or safe_get('공급자 이메일'),
        ),
        공급받는자연락처2=연락처(
            부서명='',
            이름='',
            전화번호='',
            이메일=safe_get('공급받는자 이메일2'),
        ) if safe_get('공급받는자 이메일2') else None,
        위수탁자=위수탁자,
        위수탁자연락처=위수탁자연락처,
        결제방법코드=None,
        결제금액=Decimal(0),
        공급가액=safe_decimal('공급가액'),
        세액=safe_decimal('세액'),
        총금액=safe_decimal('합계금액'),
        품목=items,
    )


def scrape_세금계산서_detail(scraper: HometaxScraper, etan, 전송일자):
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

