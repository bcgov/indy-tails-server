import asyncio
import imp
import json
import os
import logging
import socket
import sys
import time
import traceback
from aiohttp import web


try:
    from functools import reduce
except Exception:
    pass


def basic_exception_handler(_, e):
    return False, str(e)


def json_success_handler(results):
    data = {
        'hostname': socket.gethostname(),
        'status': 'success',
        'timestamp': time.time(),
        'results': results,
    }

    return json.dumps(data)


def json_failed_handler(results):
    data = {
        'hostname': socket.gethostname(),
        'status': 'failure',
        'timestamp': time.time(),
        'results': results,
    }

    return json.dumps(data)


def check_reduce(passed, result):
    return passed and result.get('passed')


class Check(object):
    def __init__(self, success_status=200, success_headers=None,
                 success_handler=json_success_handler, success_ttl=None,
                 failed_status=500, failed_headers=None,
                 failed_handler=json_failed_handler, failed_ttl=None,
                 exception_handler=basic_exception_handler, checkers=None,
                 logger=None, **options):
        self.cache = dict()

        self.success_status = success_status
        self.success_headers = success_headers or {'Content-Type': 'application/json'}
        self.success_handler = success_handler
        self.success_ttl = float(success_ttl or 0)

        self.failed_status = failed_status
        self.failed_headers = failed_headers or {'Content-Type': 'application/json'}
        self.failed_handler = failed_handler
        self.failed_ttl = float(failed_ttl or 0)

        self.exception_handler = exception_handler

        self.options = options
        self.checkers = checkers or []

        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger('HealthCheck')

    @asyncio.coroutine
    def __call__(self, request):
        message, status, headers = yield from self.check()
        return web.Response(text=message, status=status, headers=headers)

    def add_check(self, func):
        if not asyncio.iscoroutinefunction(func):
            func = asyncio.coroutine(func)

        self.checkers.append(func)

    @asyncio.coroutine
    def run_check(self, checker):
        try:
            passed, output = yield from checker()
        except Exception:
            traceback.print_exc()
            e = sys.exc_info()[0]
            self.logger.exception(e)
            passed, output = self.exception_handler(checker, e)

        if not passed:
            msg = 'Health check "{}" failed with output "{}"'.format(checker.__name__, output)
            self.logger.error(msg)

        timestamp = time.time()
        if passed:
            expires = timestamp + self.success_ttl
        else:
            expires = timestamp + self.failed_ttl

        result = {'checker': checker.__name__,
                  'output': output,
                  'passed': passed,
                  'timestamp': timestamp,
                  'expires': expires}
        return result

    @asyncio.coroutine
    def check(self):
        results = []
        for checker in self.checkers:
            if checker in self.cache and self.cache[checker].get('expires') >= time.time():
                result = self.cache[checker]
            else:
                result = yield from self.run_check(checker)
                self.cache[checker] = result
            results.append(result)

        passed = reduce(check_reduce, results, True)

        if passed:
            message = "OK"
            if self.success_handler:
                message = self.success_handler(results)

            return message, self.success_status, self.success_headers
        else:
            message = "NOT OK"
            if self.failed_handler:
                message = self.failed_handler(results)

            return message, self.failed_status, self.failed_headers