import base64
import hashlib
import hmac
import re
import typing
from contextlib import contextmanager, ExitStack
from datetime import date, datetime
from typing import List

from OpenSSL import crypto
from pypinksign import pypinksign

from hometaxbot import InvalidCertificate, HometaxException


@contextmanager
def open_files(files: List[str], mode: str = 'rb') -> List[typing.BinaryIO]:
    with ExitStack() as stack:
        yield [stack.enter_context(open(f, mode)) for f in files]


def load_cert(files: List[typing.BinaryIO], password: str) -> pypinksign.PinkSign:
    for f in files:
        f.seek(0)

    ders = [f for f in reversed(files) if f.name.endswith('.der')]
    keys = [f for f in reversed(files) if f.name.endswith('.key')]
    if len(files) == 1 and (files[0].name.endswith('.pfx') or files[0].name.endswith('.p12')):
        try:
            sign = pypinksign.PinkSign(p12_data=files[0].read(),
                                       prikey_password=password.encode('utf8'))
            return sign
        except (ValueError, crypto.Error) as e:
            raise InvalidCertificate('공인인증서 비밀번호를 확인해주세요.') from e
    elif ders and keys:
        found = False
        for der in ders:
            sign = pypinksign.PinkSign(pubkey_data=der.read())
            for key in keys:
                key.seek(0)
                try:
                    sign.load_prikey(prikey_data=key.read(), prikey_password=password.encode('utf-8'))
                except ValueError:
                    continue
                if not getattr(sign, '_rand_num', None):
                    continue
                signed = sign.sign(password.encode('utf-8'))
                if sign.verify(signed, password.encode('utf-8')):
                    found = True
                    return sign
        if not found:
            raise InvalidCertificate('유효한 공인인증서를 찾을 수 없습니다. 비밀번호를 확인해주세요.')
    else:
        raise InvalidCertificate('올바른 공인인증서 형식이 아닙니다. *.p12이나 *.pfx, 또는 *.der과 *.key의 묶음 중에 하나여야 합니다.')


def validate_cert_expiry(sign):
    if sign.valid_date()[1].date() < date.today():
        raise HometaxException('공인인증서 유효기간이 지났습니다.')


def nts_hash_param(payload):
    # payload를 정확히 encode하지 않아도 API가 동작함. 그래서 형식만 맞추도록 일부만 구현함
    # 필요 시 Hometax script를 보고 정확히 해싱하여 보내도록 수정
    second = datetime.now().second
    encodedParam = base64.b64encode(hashlib.sha256((payload + str(second)).encode('utf-8')).hexdigest().upper().encode('utf-8')).decode('utf-8')
    return str(second + 12) + encodedParam + str(second)


# 홈택스 js소스에 구현된 k1~k8암호화소스


def k1(second):
    # TODO testVal 매번 바뀌는지 확인필요
    testVal = ["bakfuRUXvh9c3POvkdfUDHF91jijBhV2BvsuWE966SY", "rns6HuMkhT3FN8cIELHqYW51xHpk4oGOTetFjZ3Wog",
               "ZobgiyO5GpHBj4XfBxpIsdtuxOVGOuxfvJ3cl7hg", "tQpnppnLO4DhApYt4Wpi2fP3ikontfDj5e4gL8fatL0",
               "qyDYuOUwZO2GCykWTJJZrgRIGTg6z3FPBrIAyHxxI", "RF899ggdKY31TR3beawC7r7QbLAW1of4OrRaSWypA",
               "ASNbDSqkpdq6ckOpIoGUyO5E6xeVulnMBIQJwOAvEI"]
    return testVal[int(second) % 7]


def k2(payload, testVal):
    signature = hmac.new(testVal.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).digest()
    return re.sub(r'[^0-9a-zA-Z]', r'', base64.b64encode(signature).decode('utf-8'))


def k4(payload, second, userId=''):
    return k2(payload+userId, k1(second))


def k7():
    return f'{datetime.now().second:02}'


def k8(action_id, second):
    return k4(action_id, second)
