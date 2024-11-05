"""
홈택스에 로그인해서 여러 가지 정보를 requests로 수집해오는 봇입니다.
"""
import random


class HometaxException(Exception):
    pass


class InvalidCertificate(HometaxException):
    pass


class AuthenticationFailed(HometaxException):
    pass


class Throttled(HometaxException):
    wait = 3  # 재시도 대기시간 초


def random_second():
    return random.randrange(30, 60)


__version__ = '0.2.0'