import os
import re
import json
from django.db import connection
from django.http import QueryDict, HttpResponse
from django.http.multipartparser import MultiPartParser


class HarmonicSQLInjectionMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    # flake8: noqa: C901
    def __call__(self, request):
        if request.method in ['POST', 'PUT', 'PATCH']:
            if request.content_type == 'application/json':
                try:
                    data = json.loads(request.body.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    data, _ = self.parse_files(request)
                    data = data.dict()
            elif request.content_type == 'multipart/form-data':
                data = self.parse_multipart_form_data(request)
            elif request.content_type == 'application/x-www-form-urlencoded':
                data = QueryDict(request.body.decode('utf-8')).dict()
            else:
                data = {}
        else:
            data = {}
        data = json.dumps(data).lower()
        query_params = json.dumps(
            dict(zip(request.GET.keys(), request.GET.values()))).lower()
        regex_pattern = ['truncate table', 'create database', 'select database', 'drop database', 'create table', 'select table', 'drop table', 'create schema',
                         'select schema', 'drop schema', 'insert into', 'select * from', 'select .* from.*', 'select.*from.*where.*', 'update.*set.*where.*', 'delete from.*where.*']
        for pattern in regex_pattern:
            if re.search(pattern, data):
                return HttpResponse(status=422)
        for pattern in regex_pattern:
            if re.search(pattern, query_params):
                return HttpResponse(status=422)
        response = self.get_response(request)
        return response

    def parse_multipart_form_data(self, request):
        # Create a copy of the original POST data
        original_post_data = request.POST.copy()

        # Create a QueryDict to store the form data
        form_data = QueryDict('', mutable=True)

        # Parse form data using MultiPartParser
        parser = MultiPartParser(
            request.META, request, request.upload_handlers)
        post_data, files_data = parser.parse()

        # Update the QueryDict with parsed form data
        form_data.update(original_post_data)
        form_data.update(post_data)

        return form_data

    def parse_files(self, request):
        # Create a copy of the original POST data
        original_post_data = request.POST.copy()

        # Create a QueryDict to store the form data
        form_data = QueryDict('', mutable=True)

        # Parse form data using MultiPartParser
        parser = MultiPartParser(
            request.META, request, request.upload_handlers)
        post_data, files_data = parser.parse()

        # Update the QueryDict with parsed form data
        form_data.update(original_post_data)
        form_data.update(post_data)

        # return form_data
        return post_data, files_data


class QueryCountMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        query_count = len(connection.queries)
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'query_count.txt'), 'a+') as f:
            f.write(f"{request.path} {request.method} {query_count} \n")
        return response
