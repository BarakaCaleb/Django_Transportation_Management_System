from django.core.serializers.json import DjangoJSONEncoder
from django import forms
from django.http import JsonResponse
import logging
import traceback
from django.utils import timezone
from django.db.models import Model
from django.core.exceptions import ValidationError


class UnescapedDjangoJSONEncoder(DjangoJSONEncoder):
    """Custom JSON encoder that disables ASCII escaping to properly handle Unicode (e.g., Chinese characters)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ensure_ascii = False


class UnescapedJsonResponse(JsonResponse):
    """JsonResponse subclass that uses UnescapedDjangoJSONEncoder to avoid ASCII escaping."""
    def __init__(self, data, **kwargs):
        json_dumps_params = kwargs.setdefault('json_dumps_params', {})
        json_dumps_params['cls'] = UnescapedDjangoJSONEncoder
        json_dumps_params['ensure_ascii'] = False
        super().__init__(data, **kwargs)


class SortableModelChoiceField(forms.ModelChoiceField):
    """
    Sorting choices for ModelChoiceField is troublesome.
    Although we can use `order_by` on the queryset property to sort,
    we also need to consider database optimization (try to avoid `using filesort` in explain).

    Therefore, we add an extra optional property to ModelChoiceIterator to allow sorting before iterating choices.
    This is application-level sorting, intended to reduce database pressure.
    """
    # Implementation can be added as needed


def multi_lines_log(logger: logging.Logger, string: str, level=logging.INFO):
    """ Log multiple lines """
    for line in string.splitlines():
        logger.log(level, line)


def traceback_log(logger: logging.Logger, level=logging.ERROR):
    """ Log exception stack """
    multi_lines_log(logger=logger, string=traceback.format_exc(), level=level)


def traceback_and_detail_log(request, logger: logging.Logger, level=logging.ERROR):
    """ Log exception stack and some other detailed information """
    logger.log(level, "=" * 100)
    logger.log(level, "Exception:")
    logger.log(level, "Time: %s" % timezone.make_naive(timezone.now()).strftime("%Y-%m-%d %H:%M:%S"))
    logger.log(level, "Url: %s" % request.path)
    logger.log(level, "Method: %s" % request.method)
    logger.log(level, "Cookies: %s" % request.COOKIES)
    logger.log(level, "Session: %s" % dict(request.session.items()))
    if request.method == "POST":
        logger.log(level, "Post data: %s" % request.POST.dict())
    logger.log(level, "")
    traceback_log(logger=logger, level=level)
    logger.log(level, "=" * 100)


def validate_comma_separated_integer_list_and_split(string: str, auto_strip=True) -> list:
    """ 
    Validate if the string is a comma-separated list of integers.
    If valid, return the list of integers. Otherwise, raise ValidationError.
    """
    if auto_strip:
        string = string.strip()

    if not string:
        return []

    items = string.split(',')

    result = []
    for item in items:
        item = item.strip()
        if not item.isdigit():
            raise ValidationError(f"'{item}' is not a valid integer.")
        result.append(int(item))
    return result


def model_to_dict_(instance: Model) -> dict:
    """
    Convert a Django model instance to a dict including all fields,
    even those with editable=False (unlike Django's default model_to_dict).
    """
    opts = instance._meta
    data = {}
    for f in opts.get_fields():
        if f.concrete and (not f.many_to_many) and (not f.one_to_many):
            try:
                value = getattr(instance, f.name)
            except AttributeError:
                value = None
            data[f.name] = value
    return data
