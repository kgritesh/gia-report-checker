# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from collections import OrderedDict

import aiohttp
import re
import xmltodict
from bs4 import BeautifulSoup

ANGLE_RE = re.compile('\d+.?\d]*')


def get_angle(val):
    match = ANGLE_RE.search(val or '')
    if match:
        return match.group()
    return val


class ReportCheckerException(Exception):
    MESSAGE = '{}: Failed to extract report'

    def __init__(self, report_no, message=None):
        message = message or self.MESSAGE.format(report_no)
        super().__init__(message)


class ReportBlocked(ReportCheckerException):
    MESSAGE = '{}: Report Blocked'


class ReportFetchFailed(ReportCheckerException):
    MESSAGE = '{}: Unable to fetch report. Http Status: {}'

    def __init__(self, report_no, status):
        super().__init__(self.MESSAGE.format(report_no, status))


class ReportParseFailed(ReportCheckerException):
    MESSAGE = '{}: Failed to parse report'


class GIAReportChecker(object):

    GIA_WEBSITE_URL = 'https://www.gia.edu/report-check?reportno={}'

    GIA_REPORT_URL = 'https://www.gia.edu/otmm_wcs_int/loadXML.jsp?ReportNumber={}'

    REPORT_KEY_MAP = OrderedDict([
        ('REPORT_NO', 'Report No'),
        ('LENGTH', 'Measurements'),
        ('WEIGHT', 'Carat Weight'),
        ('COLOR', 'Color Grade'),
        ('CLARITY', 'Clarity Grade'),
        ('FINAL_CUT', 'Cut Grade'),
        ('DEPTH_PCT', 'Depth'),
        ('TABLE_PCT', 'Table'),
        ('CRN_AG', 'Crown Angle'),
        ('CRN_HT', 'Crown Height'),
        ('PAV_AG', 'Pavilion Angle'),
        ('PAV_DP', 'Pavillion Depth'),
        ('STR_LN', 'Star Length'),
        ('LR_HALF', 'Lower Half'),
        ('GIRDLE', 'Girdle Type'),
        ('GIRDLE_CONDITION', 'Girdle Condition'),
        ('GIRDLE_PCT', 'Girdle'),
        ('CULET_SIZE', 'Cutlet'),
        ('POLISH', 'Polish'),
        ('SYMMETRY', 'Symmetry'),
        ('FLUORESCENCE_INTENSITY', 'Fluorescence'),
        ('KEY_TO_SYMBOLS', 'Clarity Characteristics'),
        ('REPORT_TYPE', 'Report Type'),
        ('REPORT_DT', 'Date of Issue'),
        ('INSCRIPTION', 'Inscription(s)'),
        ('SHAPE', 'Shape'),
        ('REPORT_COMMENTS', 'Comments')
    ])

    REPORT_VALUE_FORMAT = {
        'Crown Angle': get_angle,
        'Pavilion Angle': get_angle,
    }

    def __init__(self, report_no):
        self.report_no = report_no

    async def check(self):
        encr_report_no = await self._get_encrypted_report_no()
        report = await self._get_report(encr_report_no)
        if not report:
            raise Exception('Failed to get report: {}'.format(self.report_no))
        report_fmt = OrderedDict()
        for key, fmt_key in self.REPORT_KEY_MAP.items():
            fmt = self.REPORT_VALUE_FORMAT.get(fmt_key, lambda x: x)
            report_fmt[fmt_key] = fmt(report[key])

        return report_fmt

    async def _get_report(self, encr_report_no):
        async with aiohttp.ClientSession() as session:
            url = self.GIA_REPORT_URL.format(encr_report_no)
            async with session.get(url) as resp:
                content = await resp.text()
                try:
                    report_dict = xmltodict.parse(content)
                    return report_dict['REPORT_CHECK_RESPONSE']['REPORT_DTLS']['REPORT_DTL']
                except Exception:
                    raise ReportParseFailed(self.report_no)

    async def _get_encrypted_report_no(self):
        async with aiohttp.ClientSession() as session:
            url = self.GIA_WEBSITE_URL.format(self.report_no)
            async with session.get(url) as resp:
                if resp.status == 403:
                    raise ReportBlocked(self.report_no)
                elif resp.status != 200:
                    raise ReportCheckerException(self.report_no, resp.status)

                content = await resp.text()
                soup = BeautifulSoup(content, 'html.parser')
                encr_input = soup.find(id='encryptedString')
                if not encr_input:
                    raise ReportParseFailed(self.report_no)

                return encr_input.attrs['value']
