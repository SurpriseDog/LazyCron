#!/usr/bin/python3

import csv

def write_csv(filename, data):
    "write a 2d array to csv"
    with open(filename, 'w') as csvfile:
        writer = csv.writer(csvfile)
        for row in data:
            writer.writerow(row)


def _clean_csv(row):
    "Strip all the junk off of csv file"
    out = []
    for item in row:
        # Cleanup any quote wraps
        item = item.strip()
        if item.startswith("'") and item.endswith("'"):
            item.strip("'")
        if item.startswith('"') and item.endswith('"'):
            item.strip('"')

        # Check if its a number
        if item.lstrip('-').replace('.', '', 1).isdigit():
            if '.' in item:
                item = float(item)
            else:
                item = int(item)
        out.append(item)
    return out


def _get_headers(row, headers, unused = '__UNUSED'):
    "Match headers with row"
    out = {}
    count = 0
    for count, header in enumerate(headers):
        out[header] = row[count] if count < len(row) else None
    if len(row) > count + 1:
        if unused in out:
            raise ValueError("Unexpected header:", unused)
        out[unused] = row[count + 1:]

    return out


def read_row(line, merge=True, delimiter=',', **kargs):
    "Read csv line with support for multiple delimiters"
    if len(delimiter) == 1:
        row = next(csv.reader([line], delimiter=delimiter[0], **kargs))
    else:
        row = line.split(delimiter)

    # Eliminate empty columns
    if merge:
        row = [item for item in row if item]
    return row


def read_csv(filename, ignore_comments=True, cleanup=True, headers=None, merge=True, delimiter=',', **kargs):
    '''Read a csv while stripping comments and turning numbers into numbers
    ignore_comments = ignore a leading #
    cleanup = remove quotes and fix numbers
    headers = instead of a list return a dict with headers as keys for columns
    delimiter = seperator between columns.
    If you provide a list it will try each one in turn, but the first option must be a single character
    merge = merge repeated delimiter'''


    with open(filename) as f:
        for line in f.readlines():
            line = line.strip()
            if not line or (ignore_comments and line.startswith('#')):
                # yield _get_headers(_clean_csv([]), headers)
                continue


            # Try various delimiters looking for one that will handle the line properly
            for d in delimiter:
                row = read_row(line, delimiter=d, merge=merge, **kargs)
                if len(row) >= len(headers):
                    break
            else:
                raise ValueError("Could not hande line:", line)
            yield _get_headers(_clean_csv(row), headers)




def __tester():
    headers = "time frequency date reqs path".split()
    for line in read_csv(sys.argv[1], headers=headers, delimiter=("\t", " " * 4), merge=True, ignore_comments=True):
        print(line)
        print('\n')


if __name__ == "__main__":
    import sys
    __tester()
