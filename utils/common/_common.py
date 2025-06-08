class UnescapedDjangoJSONEncoder(DjangoJSONEncoder):

    """ Custom JSON encoder, forcibly sets ensure_ascii to False to avoid Chinese characters being encoded as garbled text """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forcibly set ensure_ascii to False
        self.ensure_ascii = False

class SortableModelChoiceField(forms.ModelChoiceField):

    """
    Sorting choices for ModelChoiceField is troublesome.
    Although we can use `order_by` on the queryset property to sort,
    we also need to consider database optimization (try to avoid `using filesort` in explain).

    Therefore, we add an extra optional property to ModelChoiceIterator to allow sorting before iterating choices.
    This is application-level sorting, intended to reduce database pressure.
    """

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
    """ Determine whether the string is a comma-separated list of numbers.
    If so, automatically split and return the list; if not, raise a ValidationError.
    :param string: The string to parse
    :param auto_strip: If True, strip the string first (default)
    :return: list
    """

def model_to_dict_(instance: Model) -> dict:
    """ Django has a built-in django.forms.models.model_to_dict method (hereinafter referred to as the original model_to_dict method)
    which conveniently converts a model to a dictionary, but there is a pitfall: fields marked as not editable (editable=False) will not be included in the output dictionary.
    The original model_to_dict method is only used when initializing ModelForm, which is understandable for safety reasons.
    But what we want is a "model to dictionary" method that should include all fields of the model.
    So we wrote a new model_to_dict_ method based on the original model_to_dict method.
    Compared to the original model_to_dict method, it lacks the fields and exclude parameters, because we don't need them for now.
    """
