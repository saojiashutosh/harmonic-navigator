from rest_framework import pagination
from rest_framework.response import Response
from collections import OrderedDict
import math


class HarmonicPagination(pagination.LimitOffsetPagination):
    default_limit = 10

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.count),
            ('currentPage', 1 if self.offset ==
             0 else self.offset // self.limit + 1),
            ('totalPages', math.ceil(self.count / self.limit)),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))
