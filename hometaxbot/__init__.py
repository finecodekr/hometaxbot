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
