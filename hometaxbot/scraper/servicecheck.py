import hashlib
import re
import json
import base64
import urllib
from urllib.parse import unquote

def extract_vars(js: str) -> dict:
    vars = {}
    for found in re.findall(r'(?ms)^var[\s\S]*?;\r?\n', js, re.MULTILINE):
        if 'function' in found: continue

        eq_pos = found.index('=')
        value = found[eq_pos + 1:-2]
        try:
            if "'" in found and '"' not in found:
                value = value.replace("'", '"')
            vars[found[4:eq_pos].strip()] = json.loads(value)

        except json.decoder.JSONDecodeError:
            print('error', found[4:eq_pos])
            vars[found[4:eq_pos].strip()] = found[eq_pos + 1:-1]

    decoder_pattern = re.compile(r'function\s+(\w+)[^{]*{\s*return\s+decodeURIComponent', re.MULTILINE | re.DOTALL)
    if match := decoder_pattern.search(js):
        vars['decoder_function'] = match.group(1)
        print(f"Found decoder function: {match.group(1)}")
    else:
        print("Decoder function not found!")

    return vars

def deobfuscate_js(js: str, consts_key: str, consts: list[str], decoder_function: str) -> str:
    """
    난독화된 JavaScript 코드를 해독합니다.
    
    Args:
        js: 난독화된 JavaScript 코드
        consts: base64로 인코딩된 상수 문자열 리스트
    
    Returns:
        해독된 JavaScript 코드
    """
    # Step 1: Convert hex numbers to decimal first
    hex_pattern = re.compile(r'0x[0-9A-Fa-f]+')
    def convert_hex(match):
        try:
            hex_str = match.group(0)
            return str(int(hex_str, 16))
        except Exception as e:
            print(f"Error converting hex '{match.group(0)}': {e}")
            return match.group(0)  # 에러 발생 시 원문 반환
    
    # Convert all hex numbers to decimal first
    js = hex_pattern.sub(convert_hex, js)

    # Step 2: Calculate all numeric expressions
    numeric_pattern = re.compile(
        r"(?<![\w$])"  # 앞 경계
        r"(?:\d+(?:\.\d+)?|\([^()]*\))"  # 첫 항
        r"(?:\s*(?:<<|>>>|>>|[+\-*/%&|^])\s*"  # 연산자
        r"(?:\d+(?:\.\d+)?|\([^()]*\)))*"
        r"(?![\w$])",  # 뒤 경계
        re.MULTILINE,
    )
    
    def calculate_expression(match):
        expr = match.group(0)
        try:
            # Skip if it's just a single number
            if expr.strip().isdigit():
                return expr
            # Let Python's eval handle the expression directly
            result = eval(expr)
            # Convert result to integer
            return str(int(result))
        except Exception as e:
            # print(f"Error calculating expression '{expr}': {e}")
            return match.group(0)

    # First pass: replace all numeric expressions with their calculated values
    intermediate_js = numeric_pattern.sub(calculate_expression, js)

    # Step 3: Replace string references with actual values
    string_pattern = f'{decoder_function}\\({consts_key}\\[(\\d+)\\]\\)'
    
    def replace_string(match):
        try:
            index = int(match.group(1))
            value = consts[index]
            # Escape any quotes in the string
            value = value.replace('"', '\\"')
            return f'"{value}"'
        except Exception as e:
            print(f"Error replacing string at index {match.group(1)}: {e}")
            return match.group(0)

    # Replace all string references with actual values
    deobfuscated_js = re.sub(string_pattern, replace_string, intermediate_js)

    # Step 4: Handle string concatenation (moved to the end)
    string_concat_pattern = re.compile(
        r'"[A-Za-z0-9_]+"\s*\+\s*"[A-Za-z0-9_]+"'  # 아주 단순한 큰따옴표 문자열 + 문자열
    )

    def concat_strings(match):
        try:
            expr = match.group(0)
            print(f"\nFound string concatenation: {expr}")
            print(f"Context: ...{deobfuscated_js[max(0, match.start()-50):match.end()+50]}...")
            # 문자열 연결 연산 수행
            result = eval(expr)
            print(f"Result: {result}")
            return f'"{result}"'  # 결과를 다시 문자열로 감싸서 반환
        except Exception as e:
            # print(f"Error concatenating strings '{match.group(0)}': {e}")
            return match.group(0)

    # Final pass: handle string concatenation
    print("\nSearching for string concatenations in file...")
    final_js = string_concat_pattern.sub(concat_strings, deobfuscated_js)

    return final_js


def encrypt_post_body(service_check_js: str, body: str) -> str:
    m = re.search(r'"([A-Za-z0-9]+)" \+ "\&" \+ "([A-Za-z0-9]+)"', service_check_js)
    signature_key = m.group(1)
    payload_key = m.group(2)
    print(signature_key, payload_key)


def hometax_sign_post(payload: str, salt_prefix, salt_suffix):
    """
    JavaScript EvCrypto SHA-256 해시 계산 로직을
    Python hashlib으로 재현한 함수.
    1) payload를 percent-encoding
    2) Base64 인코딩
    3) PREFIX + payload + body_b64 + SUFFIX 결합
    4) SHA-256 해시 → hex 문자열 반환
    """
    # 1) Percent-encode (JS의 encodeURIComponent과 동일)
    encoded = urllib.parse.quote(payload, safe='')

    # 2) Base64 인코딩 (JS의 btoa)
    body_b64 = base64.b64encode(encoded.encode('utf-8')).decode('utf-8')

    # 3) 솔트 앞뒤 + 원본 페이로드 + Base64 페이로드 결합
    input_str = salt_prefix + payload + body_b64 + salt_suffix

    # 4) SHA-256 해시 계산 → 16진수 문자열
    h = hashlib.sha256()
    h.update(input_str.encode('utf-8'))
    return h.hexdigest()
