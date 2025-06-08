import json

from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .export_excel import gen_workbook


@require_POST
@csrf_exempt
def export_excel(request):
    """ Export excel table
    The frontend must submit the form "explicitly" (can use a hidden form), cannot use ajax, otherwise the download will not be triggered
    """
    table_title = request.POST.get("table_title")
    table_header = request.POST.get("table_header")
    table_rows = request.POST.get("table_rows")
    table_rows_value_type = request.POST.get("table_rows_value_type", '[]')
    if not (table_title and table_header and table_rows):
        return HttpResponseBadRequest()
    try:
        table_header = json.loads(table_header)
        table_rows = json.loads(table_rows)
        table_rows_value_type = json.loads(table_rows_value_type)
    except json.decoder.JSONDecodeError:
        if settings.DEBUG:
            raise
        return HttpResponseBadRequest()
    # Cannot use FileResponse or StreamingHttpResponse, which is strange
    response = HttpResponse(gen_workbook(table_title, table_header, table_rows, table_rows_value_type))
    response["Content-Type"] = "application/octet-stream"
    # Must be encoded as ansi here, otherwise the filename will be garbled if it contains Chinese characters
    response["Content-Disposition"] = ('attachment; filename="%s.xlsx"' % table_title).encode("ansi")
    return response
