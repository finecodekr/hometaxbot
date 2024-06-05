import typing
from contextlib import contextmanager, ExitStack
from datetime import date
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
