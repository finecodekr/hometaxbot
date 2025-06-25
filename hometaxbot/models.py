from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from io import BytesIO
from typing import List

from hometaxbot.types import HometaxModel


class 홈택스사용자구분코드(Enum):
    개인 = '01'
    개인사업자 = '02'
    법인사업자 = '03'


class 세목코드(Enum):
    종합소득세 = '10'
    원천세 = '14'
    양도소득세 = '22'
    법인세 = '31'
    부가세 = '41'


@dataclass(kw_only=True)
class 홈택스사용자(HometaxModel):
    납세자번호: str
    납세자명: str
    홈택스ID: str
    홈택스사용자번호: str
    사용자구분: 홈택스사용자구분코드
    휴대전화번호: str
    전자메일주소: str


@dataclass(kw_only=True)
class 납세자(HometaxModel):
    납세자번호: str
    납세자명: str
    휴대전화번호: str = None
    전자메일주소: str = None
    주소: str = None
    사업자구분: 홈택스사용자구분코드 = None

    대표자주민등록번호: str = None
    법인등록번호: str = None
    대표자명: str = None
    업종코드: str = None
    업태: str = None
    종목: str = None
    개업일: date = None
    폐업일: date = None
    사업장소재지: str = None
    사업장전화번호: str = None
    간이과세여부: bool = False


@dataclass(kw_only=True)
class 세무대리인:
    상호: str
    사업자번호: str
    관리번호: str
    사업장소재지: str = None
    대표자성명: str = None
    대표자주민등록번호: str = None
    전화번호: str = None


@dataclass(kw_only=True)
class 세무대리수임정보:
    납세자: 납세자
    세무대리인: 세무대리인 = None
    수임일: date
    동의일: date = None
    정보제공범위: str


@dataclass(kw_only=True)
class 전자신고결과조회(HometaxModel):
    접수번호: str
    세무서코드: str = None
    세목코드: 세목코드
    신고서종류: str # 예시: 원천징수이행상황신고서
    신고서종류코드: str = None  # 예시: F01
    신고구분코드: str = None  # 예시: 01
    신고구분상세코드: str = None  # 예시: 01
    신고구분: str  # 예시: 정기(확정)
    신고유형: str  # 예시: 정기신고
    과세연월: str
    과세기간시작일: date = None  # 예시: 20191101
    과세기간종료일: date = None  # 예시: 20191130
    지급연월: str = None
    접수일: date
    접수일시: datetime = None  # 예시: 20191203145924
    접수여부_첨부서류: str = None  # 예시: 정상(1종)
    홈택스ID: str = None
    납세자명: str = None
    납세자번호: str = None
    업종코드: str = None
    공급가액: Decimal  # 예시: 10500000
    금액: Decimal
    납부금액: Decimal


@dataclass(kw_only=True)
class 납부내역(HometaxModel):
    세무서코드: str
    세무서명: str
    납부일: date
    금액: Decimal
    전자납부발행번호: str
    세목: str
    세목코드: str
    결정구분: str = None
    신고연월: str = None
    전자납부번호: str = None

    def __post_init__(self):
        if not self.전자납부번호:
            self.전자납부번호 = '0126' + self.신고연월[2:] + self.결정구분 + self.세목코드 + self.전자납부발행번호


@dataclass(kw_only=True)
class 환급금조회(HometaxModel):
    환급번호: str
    세무서코드: str
    세무서명: str
    세목: str
    세목코드: str
    환급결정일: date
    최종변경일시: datetime
    귀속연월: date
    금액: Decimal


class 세금계산서분류(Enum):
    세금계산서 = '01'
    수정세금계산서 = '02'
    계산서 = '03'
    수정계산서 = '04'


class 세금계산서종류(Enum):
    일반 = '01'
    영세율 = '02'
    위수탁 = '03'
    수입 = '04'
    영세율위수탁 = '05'
    수입납부유예 = '06'


@dataclass(kw_only=True)
class 세금계산서(HometaxModel):
    승인번호: str
    전송일자: date  # 세금계산서 XML에는 포함되어 있지 않는 필드로 홈택스 시스템에서만 제공한다.
    작성일자: date
    세금계산서분류: 세금계산서분류
    세금계산서종류: 세금계산서종류
    영수청구코드: str
    수정코드: str = None
    당초승인번호: str = None
    비고: str = None
    수입문서참조: '수입문서' = None

    공급자: 납세자
    공급자연락처: '연락처'
    공급받는자: 납세자
    공급받는자연락처: '연락처'
    공급받는자연락처2: '연락처' = None
    위수탁자: 납세자 = None
    위수탁자연락처: '연락처' = None

    결제방법코드: str
    결제금액: Decimal
    공급가액: Decimal
    세액: Decimal
    총금액: Decimal

    품목: List['세금계산서품목']


@dataclass(kw_only=True)
class 수입문서(HometaxModel):
    신고번호: str
    일괄발급시작일: date
    일괄발급종료일: date
    총건: int


@dataclass(kw_only=True)
class 연락처(HometaxModel):
    부서명: str
    이름: str
    전화번호: str
    이메일: str


@dataclass(kw_only=True)
class 세금계산서품목(HometaxModel):
    일련번호: int
    공급일자: date
    품목명: str
    규격: str = None
    비고: str = None
    수량: Decimal = None # `-` 허용. 단위는 attribute로 들어간다.
    단가: Decimal  # 소수점 2자리까지 표현. `-` 허용
    공급가액: Decimal  # 원단위까지. `-` 허용
    세액: Decimal


@dataclass(kw_only=True)
class 카드매입(HometaxModel):
    거래일시: datetime
    카드번호: str
    승인번호: str
    카드사: str
    공급가액: Decimal
    부가세: Decimal
    봉사료: Decimal
    총금액: Decimal
    가맹점: 납세자
    가맹점유형: str
    공제여부: str
    비고: str


@dataclass(kw_only=True)
class 현금영수증(HometaxModel):
    거래일시: datetime
    매출매입: str
    승인번호: str
    승인구분: str
    발행구분: str = None
    발급수단: str
    거래구분: str = None
    공급가액: Decimal
    부가세: Decimal
    봉사료: Decimal
    총금액: Decimal
    매입자명: str = None
    가맹점: 납세자
    공제여부: bool = None


@dataclass(kw_only=True)
class 카드매출월간집계(HometaxModel):
    거래연월: date
    거래건수: int
    합계금액: Decimal
    매입처명: str


@dataclass(kw_only=True)
class 체납내역:
    잔여납부세액: Decimal  # 3470280
    납세자번호: str  # 129-86-67290
    과세기간_세목: str  # 2018년2기분 부가가치세
    감액세액: Decimal  # 0
    납세자명: str  # 주식회사 이콜레모
    고지세액: Decimal   # 3119410
    일부납부세액: Decimal  # 0
    전자납부번호: str   # 0126-1903-5-41-11168940
    납부URL: str = None
    상태: str  # 미납
    세목명: str  # 부가가치세
    세목코드: str  # 41


@dataclass(kw_only=True)
class 고지내역:
    세목코드: str  # 41
    전자납부번호: str  # 0126-2003-5-41-22057360
    고지번호: str   # 100000000047718675
    납세자번호: str  # 129-86-67290
    납부URL: str = None
    고지세액: Decimal  # 710540
    납세자명: str  # 주식회사 이콜레모
    납부기한: date  # 2020-03-31
    납부의무종결사유: str = None  # 해당없음
    고지송달일: date
    납부여부: str  # 미납
    고지서유형: str  # 일반고지
    분납_연부연납세액: Decimal  # 0
    납부할세액: Decimal  # 710540
    과세기간_세목: str  # 2019년2기분 부가가치세
    감액세액: Decimal  # 0
    세목: str  # 부가가치세


@dataclass(kw_only=True)
class 전자신고_신고서_납부서(HometaxModel):
    납세자: 납세자
    # 신고내역: 전자신고결과조회
    신고서_data: dict
    납부내역: 납부내역
    납부서_pdf: BytesIO
