import asyncio
import csv
import json

import click
from click import MissingParameter

from gia_report_checker.report_checker import GIAReportChecker


def validate_input_options(ctx, param, value):
    report_no = ctx.params.get('report_no')
    input_file = value
    if report_no is None and input_file is None:
        raise MissingParameter("Either one of report_no or input_file must be specified")

    if None not in (report_no, input_file):
        raise click.BadArgumentUsage('Only one of report_no or input_file must be specified')

    return input_file


def validate_output_options(ctx, param, value):
    if not value and ctx.params['input_file']:
        raise click.MissingParameter()
    return value


async def check_report(report_no, semaphore):
    async with semaphore:
        checker = GIAReportChecker(report_no)
        print('Checking Report for ', report_no)
        try:
            report = await checker.check()
            print('Successfully fetched report for: {}'.format(report_no))
            return report_no, report
        except Exception as ex:
            print('Failed to fetch report for: {}. Error: {}'.format(report_no, ex))
            return report_no, ex

async def check_reports(report_no_list, parallel):
    tasks = []
    # create instance of Semaphore
    sem = asyncio.Semaphore(parallel)
    for report_no in report_no_list:
        tasks.append(asyncio.ensure_future(check_report(report_no, sem)))
    return await asyncio.gather(*tasks)


def write_output(output_file, reports):
    headers = GIAReportChecker.REPORT_KEY_MAP.values()
    with open(output_file, 'w', encoding='utf-8') as fl:
        writer = csv.DictWriter(fl, fieldnames=headers)
        writer.writeheader()
        for row in reports:
            if isinstance(row, dict):
                writer.writerow(row)


@click.command()
@click.option('-n', '--report-no',
              help="GIA Report Number",
              type=click.STRING)
@click.option('-f', '--input-file',
              type=click.Path(exists=True),
              help="CSV file with list of GIA Report Numbers",
              callback=validate_input_options)
@click.option('-o', '--output-file',
              type=click.Path(dir_okay=False),
              callback=validate_output_options,
              help="Output file to store the report")
@click.option('-p', '--parallel', default=2,
              type=click.INT,
              help='No of requests in parallel')
def cli(report_no, input_file, output_file, parallel):
    report_no_list = []
    if report_no:
        report_no_list.extend(report_no.split(', '))
    else:
        with open(input_file, 'r') as fl:
            for row in csv.reader(fl):
                report_no_list.append(row[0])

    print('Total no of reports to be read: {}'.format(len(report_no_list)))

    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(check_reports(report_no_list, parallel))
    results = loop.run_until_complete(future)
    reports = []
    failed = []
    for res in results:
        if isinstance(res[1], Exception):
            failed.append(res[0])
        else:
            reports.append(res[1])

    print('Total no of reports extracted successfully: {}'.format(len(reports)))
    print('Failed to extract reports: {}'.format(', '.join(failed)))
    if output_file:
        write_output(output_file, reports)

    else:
        print(json.dumps(reports))


if __name__ == '__main__':
    cli(default_map={
        'launch': {
            'auto_envvar_prefix': 'ETHCLOUD'
        }
    })
