from dateutil.relativedelta import relativedelta


def split_date_range(begin, end, step: relativedelta):
    while True:
        next_begin = begin + step
        if next_begin > end:
            yield begin, end
            break

        yield begin, next_begin - relativedelta(days=1)
        begin = next_begin
