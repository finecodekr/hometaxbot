import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from hometaxbot.models import (세목코드, 전자신고결과조회, 전자신고결과조회_납부서)


class TestModels(unittest.TestCase):
    def test_전자신고결과조회_납부서_전자납부번호(self):
        payment = 전자신고결과조회_납부서(
            접수번호='receipt',
            신고연월='202606',
            결정구분='4',
            세목코드='14',
            세목='근로소득세(갑)',
            전자납부발행번호='12345678',
        )

        self.assertEqual('0126260641412345678', payment.전자납부번호)

    @patch('hometaxbot.tax_schedule.세무일정')
    def test_전자신고결과조회_납부기한(self, schedules):
        cases = [
            (세목코드.원천세, '202607', None, '원천징수이행상황신고서', date(2026, 8, 10)),
            (세목코드.부가세, '202507', date(2025, 12, 31), '부가가치세 확정 신고서', date(2026, 1, 26)),
            (세목코드.법인세, '202512', date(2025, 12, 31), '법인세 정기확정 신고서', date(2026, 3, 31)),
            (세목코드.종합소득세, '202512', date(2025, 12, 31), '종합소득세 신고서', date(2026, 6, 1)),
        ]
        schedules.side_effect = [[{'begin': case[-1]}] for case in cases]
        for tax_code, tax_month, period_end, form_name, expected in cases:
            with self.subTest(tax_code=tax_code):
                report = 전자신고결과조회(
                    접수번호='receipt', 세목코드=tax_code, 신고서종류=form_name,
                    신고구분='정기(확정)', 신고유형='정기신고', 과세연월=tax_month,
                    과세기간종료일=period_end, 접수일=date(2026, 1, 1),
                    공급가액=Decimal(0), 금액=Decimal(0), 납부금액=Decimal(0),
                )
                self.assertEqual(expected, report.납부기한)
