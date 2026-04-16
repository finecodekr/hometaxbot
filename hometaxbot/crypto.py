import base64
import hashlib
import hmac
import math
import re
import typing
from contextlib import contextmanager, ExitStack
from datetime import date, datetime
from typing import List

from Crypto.Cipher import ARC2
from OpenSSL import crypto
from asn1crypto import pkcs12 as asn1_pkcs12, algos as asn1_algos
from pypinksign import pypinksign

from hometaxbot import InvalidCertificate, HometaxException


ID_KISA_NPKI_RAND_NUM = '1.2.410.200004.10.1.1.3'


def _pkcs12_kdf(password_bytes, salt, iterations, key_length, id_byte=1):
    """PKCS#12 key derivation function (RFC 7292, Appendix B)"""
    v = 64  # SHA-1 block size
    D = bytes([id_byte]) * v
    S = (salt * (v // len(salt) + 1))[:v * math.ceil(len(salt) / v)] if salt else b''
    P = (password_bytes * (v // len(password_bytes) + 1))[:v * math.ceil(len(password_bytes) / v)] if password_bytes else b''
    I = S + P
    result = b''
    while len(result) < key_length:
        A = D + I
        for _ in range(iterations):
            A = hashlib.sha1(A).digest()
        result += A
        if len(result) >= key_length:
            break
        B = (A * (v // len(A) + 1))[:v]
        new_I = b''
        for j in range(len(I) // v):
            block = I[j * v:(j + 1) * v]
            carry = 1
            new_block = bytearray(v)
            for k in range(v - 1, -1, -1):
                temp = block[k] + B[k] + carry
                new_block[k] = temp & 0xff
                carry = temp >> 8
            new_I += bytes(new_block)
        I = new_I
    return result[:key_length]


def _decrypt_pbe(algo_oid, pwd_bytes, salt, iterations, encrypted_bytes):
    """PBE 알고리즘으로 암호화된 데이터를 복호화한다."""
    if algo_oid == '1.2.840.113549.1.12.1.6':
        # pbeWithSHAAnd40BitRC2-CBC
        key = _pkcs12_kdf(pwd_bytes, salt, iterations, 5, id_byte=1)
        iv = _pkcs12_kdf(pwd_bytes, salt, iterations, 8, id_byte=2)
        cipher = ARC2.new(key, ARC2.MODE_CBC, iv, effective_keylen=40)
    elif algo_oid == '1.2.840.113549.1.12.1.3':
        # pbeWithSHAAnd3-KeyTripleDES-CBC
        from Crypto.Cipher import DES3
        key = _pkcs12_kdf(pwd_bytes, salt, iterations, 24, id_byte=1)
        iv = _pkcs12_kdf(pwd_bytes, salt, iterations, 8, id_byte=2)
        cipher = DES3.new(key, DES3.MODE_CBC, iv)
    else:
        return None
    decrypted = cipher.decrypt(encrypted_bytes)
    return decrypted[:-decrypted[-1]]


def extract_rand_num_from_pfx(pfx_data: bytes, password: str) -> bytes:
    """PFX 파일에서 KISA NPKI rand_num (OID 1.2.410.200004.10.1.1.3)을 추출한다."""
    from pyasn1.codec.der import encoder
    from pyasn1.type.univ import ObjectIdentifier

    oid_der = encoder.encode(ObjectIdentifier(tuple(int(x) for x in ID_KISA_NPKI_RAND_NUM.split('.'))))

    pfx = asn1_pkcs12.Pfx.load(pfx_data)
    content_bytes = pfx['auth_safe']['content'].native
    auth_safe = asn1_pkcs12.AuthenticatedSafe.load(content_bytes)

    pwd_bytes = password.encode('utf-16-be') + b'\x00\x00'

    for ci in auth_safe:
        ct = ci['content_type'].native

        if ct == 'data':
            safe_contents = asn1_pkcs12.SafeContents.load(ci['content'].native)
            for bag in safe_contents:
                bag_id = bag['bag_id'].native

                if bag_id == 'key_bag':
                    result = _find_kisa_rand_num_in_bytes(bag['bag_value'].dump(), oid_der)
                    if result is not None:
                        return result

                elif bag_id == 'pkcs8_shrouded_key_bag':
                    val = bag['bag_value']
                    algo = val['encryption_algorithm']
                    algo_oid = algo['algorithm'].dotted
                    salt = algo['parameters']['salt'].native
                    iterations = algo['parameters']['iterations'].native
                    encrypted_bytes = val['encrypted_data'].native
                    decrypted = _decrypt_pbe(algo_oid, pwd_bytes, salt, iterations, encrypted_bytes)
                    if decrypted is not None:
                        result = _find_kisa_rand_num_in_bytes(decrypted, oid_der)
                        if result is not None:
                            return result

        elif ct == 'encrypted_data':
            enc_data = ci['content']
            eci = enc_data['encrypted_content_info']
            algo = eci['content_encryption_algorithm']
            algo_oid = algo['algorithm'].dotted
            pbe_params = asn1_algos.Pbes1Params.load(algo['parameters'].dump())
            salt = pbe_params['salt'].native
            iterations = pbe_params['iterations'].native
            encrypted_bytes = eci['encrypted_content'].native
            decrypted = _decrypt_pbe(algo_oid, pwd_bytes, salt, iterations, encrypted_bytes)
            if decrypted is not None:
                result = _find_kisa_rand_num(decrypted, oid_der)
                if result is not None:
                    return result

    raise HometaxException('PFX 파일에서 KISA rand_num을 찾을 수 없습니다.')


def _find_kisa_rand_num_in_bytes(data: bytes, oid_der: bytes) -> bytes:
    """바이트 데이터에서 KISA rand_num OID의 값을 찾는다."""
    idx = data.find(oid_der)
    if idx < 0:
        return None
    # OID 뒤: SET { OCTET STRING { value } }
    remaining = data[idx + len(oid_der):]
    set_length = remaining[1]
    set_content = remaining[2:2 + set_length]
    # OCTET STRING 내부
    os_length = set_content[1]
    rand_num = set_content[2:2 + os_length]
    # ASN.1 INTEGER 부호 패딩 (0x00) 제거
    if rand_num[0] == 0:
        rand_num = rand_num[1:]
    return rand_num


def _find_kisa_rand_num(decrypted_safe_contents: bytes, oid_der: bytes) -> bytes:
    """복호화된 SafeContents에서 KISA rand_num OID의 값을 찾는다."""
    safe_contents = asn1_pkcs12.SafeContents.load(decrypted_safe_contents)
    for bag in safe_contents:
        result = _find_kisa_rand_num_in_bytes(bag['bag_value'].dump(), oid_der)
        if result is not None:
            return result
    return None


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


def snake_oil_encrypt(pswd: str) -> str:
    temp_string = ""
    for ch in pswd:
        encoded_char = chr(128 - ord(ch))
        temp_string += encoded_char
    encoded_bytes = temp_string.encode("latin1")  # 0~255 범위 안전하게 인코딩
    base64_encoded = base64.b64encode(encoded_bytes).decode("ascii")
    return base64_encoded
