import unittest

from hometaxbot.models import 전자신고결과조회_납부서


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
