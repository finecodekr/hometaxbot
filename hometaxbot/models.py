from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

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
    사업자구분: 홈택스사용자구분코드

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
