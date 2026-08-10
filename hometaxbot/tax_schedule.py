from datetime import date
from functools import lru_cache

import requests
from bs4 import BeautifulSoup

from hometaxbot.models import 세목코드


@lru_cache(maxsize=3)
def fetch_세무일정(기준연도=None):
    if not 기준연도:
        기준연도 = date.today().year

    schedules = []
    for month in range(1, 13):
        try:
            response = requests.get(
                'https://www.nts.go.kr/nts/ad/taxSchdul/selectList.do',
                params={'taxYear': 기준연도, 'taxMonth': f'{month:02}'}, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(response.text, 'html.parser')
        active_year = soup.select_one('#taxSchdulList .tab_list li.on a')
        if not active_year or active_year.get_text(strip=True) != f'{기준연도}년':
            continue

        for row in soup.select('#taxSchdulList table tbody tr'):
            cells = [cell.get_text(' ', strip=True) for cell in row.find_all('td')]
            if len(cells) < 4:
                continue
            try:
                begin = date(기준연도, int(cells[0]), int(cells[1]))
            except ValueError:
                continue
            schedules.append({'begin': begin, 'content': cells[2], 'display': f'{cells[2]} {cells[3]}'.strip()})
    return tuple(schedules)


def 세무일정(report, year):
    result = []
    report_type = f'{report.신고서종류 or ""} {report.신고구분 or ""}'
    for schedule in fetch_세무일정(year):
        content = schedule['content'].replace('_', ' ')
        if not all(keyword in content for keyword in ('신고', '납부')):
            continue

        if report.세목코드 == 세목코드.원천세 and '원천세' in content:
            result.append(schedule)
        elif report.세목코드 == 세목코드.부가세:
            filing_type = '예정' if '예정' in report_type else '확정'
            if '부가가치세' in content and filing_type in content:
                result.append(schedule)
        elif report.세목코드 == 세목코드.종합소득세:
            if '종합소득세' in content and '확정' in content:
                result.append(schedule)
        elif report.세목코드 == 세목코드.법인세 and report.과세기간종료일:
            if '법인세' in content and f'{report.과세기간종료일.month}월말' in content:
                result.append(schedule)
    return result
