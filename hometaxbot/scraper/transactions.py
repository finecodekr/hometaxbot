from datetime import date
from urllib import parse

from hometaxbot import models
from hometaxbot.crypto import nts_hash_param
from hometaxbot.models import 수입문서, 납세자, 연락처, 세금계산서품목
from hometaxbot.scraper import HometaxScraper, parse_response
from hometaxbot.scraper.requestutil import XMLValueFinder, action_params, get_quarter_by_date

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

            for element in scraper.request_paginated_xml(
                    "https://teet.hometax.go.kr/wqAction.do?actionId=ATEETBDA001R01&screenId=UTEETBDA01&popupYn=false&realScreenId=",
                    payload='<map id="ATEETBDA001R01">'
                            '<icldLsatInfr>N</icldLsatInfr>'
                            '<resnoSecYn>Y</resnoSecYn>'
                            '<srtClCd>1</srtClCd>'
                            '<srtOpt>02</srtOpt>'
                            '{{pageInfoVO}}'
                            '<map id="excelPageInfoVO"/>'
                            '<map id="etxivIsnBrkdTermDVOPrmt">'
                            '<tnmNm/>'
                            f'<prhSlsClCd>{prhSlsClCd}</prhSlsClCd>'
                            f'<dtCl>{조회기준코드["전송일자"]}</dtCl>'
                            f'<bmanCd>{"00" if 매입매출 == "매출" else "01"}</bmanCd>'
                            '<etxivClsfCd>all</etxivClsfCd>'
                            '<isnTypeCd>all</isnTypeCd>'
                            '<pageSize>10</pageSize>'
                            f'<splrTin>{scraper.tin if 매입매출 == "매출" and not 위수탁 else ""}</splrTin>'
                            f'<dmnrTin>{scraper.tin if 매입매출 == "매입" and not 위수탁 else ""}</dmnrTin>'
                            f'<cstnBmanTin>{scraper.tin if 위수탁 else ""}</cstnBmanTin>'
                            '<splrTxprDscmNo></splrTxprDscmNo>'
                            '<dmnrTxprDscmNo></dmnrTxprDscmNo>'
                            '<splrMpbNo></splrMpbNo>'
                            '<dmnrMpbNo></dmnrMpbNo>'
                            '<cstnBmanMpbNo></cstnBmanMpbNo>'
                            f'<etxivClCd>{invoice_type_choices[invoice_type]}</etxivClCd>'
                            '<etxivKndCd>all</etxivKndCd>'
                            f'<inqrDtStrt>{begin.strftime("%Y%m%d")}</inqrDtStrt>'
                            f'<inqrDtEnd>{end.strftime("%Y%m%d")}</inqrDtEnd>'
                            '</map>'
                            '</map>'):
                yield scrape_세금계산서_detail(scraper, element.find('etan').text)

            # for data in self.paginate(self.request_세금계산서_page, begin, end, invoice_type=invoice_type, 매입매출=매입매출):
            #     time.sleep(3)
            #     data['xml'] = ensure_xml_response(self.scrape_세금계산서_detail, data['etan'])
            #     yield data


def scrape_세금계산서_detail(scraper: HometaxScraper, etan):
    scraper.request_permission('teet')
    etan = etan.replace('-', '')
    downloadParam = parse.quote_plus(f'<map id="ATEETBDA001R02">'
                                     f'<fileDwnYn>Y</fileDwnYn>'
                                     f'<etan>{etan}</etan>'
                                     f'<map id="etxivIsnBrkdTermDVOPrmt">'
                                     f'<etan>{etan}</etan>'
                                     f'<screenId>UTEETBDA3</screenId>'
                                     f'<pageNum>1</pageNum>'
                                     f'<slsPrhClCd>02</slsPrhClCd>'
                                     f'<etxivClCd></etxivClCd>'
                                     f'<etxivTin>{scraper.tin}</etxivTin>'
                                     f'<etxivMpbNo>0</etxivMpbNo>'
                                     f'</map>'
                                     f'</map>')

    res = scraper.session.post("https://teet.hometax.go.kr/wqAction.do",
                               data=f"downloadParam={downloadParam}&"
                                    "actionId=ATEETBDA001R02&"
                                    "screenId=UTEETBDA38&"
                                    "downloadView=Y&"
                                    f"d={nts_hash_param(downloadParam)}",
                               headers={'Content-Type': "application/x-www-form-urlencoded"})
    res.encoding = 'UTF-8'
    finder = XMLValueFinder(parse_response(res))

    return models.세금계산서(
        승인번호=finder.get('TaxInvoiceDocument/IssueID'),
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
            납세자번호=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/ID'),
            납세자명=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/NameText'),
            대표자명=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/SpecifiedPerson/NameText'),
            주소=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/SpecifiedAddress/LineOneText'),
            업태=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/TypeCode'),
            종목=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/ClassificationCode'),
            업종코드=finder.get('TaxInvoiceTradeSettlement/InvoicerParty/ClassificationCode')),
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

    for element in scraper.request_paginated_xml(
            "https://tecr.hometax.go.kr/wqAction.do?" + action_params('ATECRCCA001R06', 'UTECRCB023'),
            payload='<map id="ATECRCBA001R03">'
                    '<sumTotaTrsAmt/>'
                    f'<tin>{scraper.tin}</tin>'
                    '<txprDscmNo/>'
                    f'<trsDtRngStrt>{begin.strftime("%Y%m%d")}</trsDtRngStrt>'
                    f'<trsDtRngEnd>{end.strftime("%Y%m%d")}</trsDtRngEnd>'
                    '<pblClCd>all</pblClCd>'
                    '{{pageInfoVO}}</map>'):

        yield models.카드매입(
            거래일시=element.find('aprvDt').text,
            카드번호=element.find('busnCrdCardNoEncCntn').text,
            승인번호=element.find('busnCrdcTrsBrkdSn').text,
            카드사=element.find('crcmClNm').text,
            공급가액=element.find('splCft').text,
            부가세=element.find('vaTxamt').text,
            봉사료=element.find('tip').text,
            총금액=element.find('totaTrsAmt').text,
            가맹점=납세자(
                납세자번호=element.find('mrntTxprDscmNoEncCntn').text,
                납세자명=element.find('mrntTxprNm').text,
                업종코드=element.find('tfbCd').text,
                업태=element.find('bcNm').text,
                종목=element.find('tfbNm').text,
            ),
            가맹점유형=element.find('bmanClNm').text,
            공제여부=element.find('ddcYnNm').text,
            비고=element.find('vatDdcClNm').text,
        )


def 현금영수증(scraper: HometaxScraper, begin: date, end: date):
    scraper.request_permission('tecr')

    # 현금영수증 매출
    for element in scraper.request_paginated_xml(
            "https://tecr.hometax.go.kr/wqAction.do?" + action_params('ATECRCBA001R03', 'UTECRCB013'),
            payload='<map id="ATECRCBA001R03">'
                    '<sumTotaTrsAmt/>'
                    f'<tin>{scraper.tin}</tin>'
                    '<txprDscmNo/>'
                    f'<trsDtRngStrt>{begin.strftime("%Y%m%d")}</trsDtRngStrt>'
                    f'<trsDtRngEnd>{end.strftime("%Y%m%d")}</trsDtRngEnd>'
                    '<pblClCd>all</pblClCd>'
                    '{{pageInfoVO}}</map>'):
        yield models.현금영수증(
            매출매입='매출',
            거래일시=element.find('trsDtm').text,
            거래구분=element.find('cshptTrsTypeNm').text,
            공급가액=element.find('splCft').text,
            부가세=element.find('vaTxamt').text,
            봉사료=element.find('tip').text,
            총금액=element.find('totaTrsAmt').text,
            승인번호=element.find('aprvNo').text,
            발급수단=element.find('spstCnfrClNm').text,
            승인구분=element.find('trsClNm').text,
            매입자명=element.find('rcprTxprNm').text,
            가맹점=scraper.selected_trader,
        )

    # 현금영수증 매입
    for element in scraper.request_paginated_xml(
            "https://tecr.hometax.go.kr/wqAction.do?" + action_params('ATECRCBA001R02', 'UTECRCB005'),
            payload=f'<map id="ATECRCBA001R02">'
                    f'<tin>{scraper.tin}</tin>'
                    f'<spjbTrsYn>all</spjbTrsYn>'
                    f'<pubcUserNo>all</pubcUserNo>'
                    f'<spstCnfrId>all</spstCnfrId>'
                    f'<sumTotaTrsAmt/>'
                    f'<trsDtRngStrt>{begin.strftime("%Y%m%d")}</trsDtRngStrt>'
                    f'<trsDtRngEnd>{end.strftime("%Y%m%d")}</trsDtRngEnd>'
                    f'<txprDscmNo>{scraper.selected_trader.납세자번호}</txprDscmNo>'
                    '{{pageInfoVO}}</map>'):
        finder = XMLValueFinder(element)
        yield models.현금영수증(
            매출매입='매입',
            거래일시=element.find('trsDtTime').text,
            거래구분=finder.get('cshptTrsTypeNm'),
            공급가액=element.find('splCft').text,
            부가세=element.find('vaTxamt').text,
            봉사료=element.find('tip').text,
            총금액=element.find('totaTrsAmt').text,
            승인번호=element.find('aprvNo').text,
            발급수단=element.find('spstCnfrClNm').text,
            승인구분=element.find('trsClNm').text,
            매입자명=element.find('rcprTxprNm').text,
            가맹점=납세자(
                납세자번호=element.find('mrntTxprDscmNoEncCntn').text,
                납세자명=element.find('mrntTxprNm').text,
                업종코드=element.find('tfbCd').text,
                업태=finder.get('tfbNm'),
                종목=finder.get('itmNm'),
            ),
            공제여부=finder.get('prhTxamtDdcClNm') == '공제' or finder.get('prhTxamtDdcYn') == 'Y',
        )


def 카드매출월간집계(scraper: HometaxScraper, begin: date, end: date):
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

