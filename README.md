# hometaxbot
홈택스에서 여러가지 정보를 스크래핑해오는 도구.

## 설치
```bash
pip install hometaxbot
```

**주의**: 패키지 호환성 문제로 pyOpenSSL의 버전을 23.2.0으로 고정해놓고 있습니다. 추후 관련 패키지들이 업데이트되면 최신 패키지로 업데이트할 예정입니다.

## 사용법
```python
from hometaxbot.scraper import HometaxScraper, reports

scraper = HometaxScraper()
scraper.login_with_cert(['signKey.der', 'signPri.key'], '1234')
for report in reports.전자신고결과조회(scraper, date(2024, 1, 1), date(2024, 6, 1)):
    print(report.신고서종류)
    
```

자세한 내용은 [테스트 케이스](tests)를 참고하세요. 

**주의**: 테스트 케이스는 실제로 홈택스에 접속해서 데이터를 가져오는 테스트를 포함하고 있기 때문에 실제 접속가능한 공동인증서에 대한 정보를 넣어야 실행이 가능합니다. 
[tests/testdata/__init__.py.sample](tests/testdata/__init__.py.sample) 파일을 `__init__.py`로 복사해서 보유한 인증서 정보를 입력하고 테스트 케이스를 실행하세요.
