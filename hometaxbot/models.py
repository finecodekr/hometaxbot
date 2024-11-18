from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List

from hometaxbot.types import HometaxModel


class 홈택스사용자구분코드(Enum):
    개인 = '01'
    개인사업자 = '02'
    법인사업자 = '03'


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
class 전자신고결과조회(HometaxModel):
    세무서코드: str
    과세연월: str
    접수일: date
    업종코드: str
    신고구분: str  # 예시: 정기(확정)
    금액: Decimal
    접수번호: str
    신고서종류코드: str  # 예시: F01
    신고유형: str  # 예시: 정기신고
    접수일시: datetime  # 예시: 20191203145924
    홈택스ID: str
    신고서종류: str # 예시: 원천징수이행상황신고서
    공급가액: Decimal  # 예시: 10500000
    접수여부_첨부서류: str  # 예시: 정상(1종)
    과세기간시작일: date  # 예시: 20191101
    신고구분코드: str  # 예시: 01
    과세기간종료일: date  # 예시: 20191130
    신고구분상세코드: str  # 예시: 01
    납세자명: str
    납세자번호: str


@dataclass(kw_only=True)
class 납부내역(HometaxModel):
    세무서코드: str
    세무서명: str
    납부일: date
    금액: Decimal
    전자납부발행번호: str
    세목: str
    세목코드: str
    전자납부번호: str


@dataclass(kw_only=True)
class 환급금조회(HometaxModel):
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
    수량: int = None # `-` 허용. 단위는 attribute로 들어간다.
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

