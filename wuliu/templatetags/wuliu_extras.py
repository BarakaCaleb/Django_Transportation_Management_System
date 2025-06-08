class _MenuItem:

    __slots__ = ["name", "url", "icon", "opened", "children", "need_perm", "admin_only"]

    def __init__(self, name="Unnamed Item", url="", *,
                 icon="far fa-circle", opened=False, children=tuple(), need_perm="", admin_only=False):
        """
        :param name: Name displayed on the page
        :param url: url
        :param icon: Class style of the icon before the text
        :param opened: Whether it is in the opened state
        :param children: Sub-items, Note: currently can only nest once
        :param need_perm: Required permission
        :param admin_only: Requires admin permission if True
        """
        self.name = name
        self.url = url
        self.icon = icon
        self.opened = opened
        self.children = children
        self.need_perm = need_perm
        self.admin_only = admin_only

@register.filter(name="is_logged_user_has_perm")
def _is_logged_user_has_perm(perm_name, request):
    """ Check if the logged-in user has the perm_name permission
    Example:
    {% if "report_table_sign_for_waybill"|is_logged_user_has_perm:request %}
      true
    {% endif %}
    """
    return is_logged_user_has_perm(request, perm_name)

@register.filter()
def is_logged_user_is_admin(request):
    """ Check if the logged-in user is an administrator
    Example:
    {% if request|is_logged_user_is_admin %}
      true
    {% endif %}
    """
    return get_logged_user(request).administrator

@register.simple_tag()
def get_company_name():
    """ Get company name """
    return get_global_settings().company_name

@register.inclusion_tag('wuliu/_inclusions/_message.html')
def show_message(message):
    """ Message on the page
    :param message: Message object
    """
    return {
        "message": message,
        "icon": _message_icons.get(message.level, _message_icons[constants.INFO]),
    }

@register.inclusion_tag('wuliu/_inclusions/_sidebar_menu_items.html', takes_context=True)
def show_sidebar_menu_items(context):
    """ Sidebar tree menu """
    current_url = context.request.path
    items = get_sidebar_menu_items()
    for item in items:
        for child in item.children:
            if child is None:
                continue
            # Expand the list according to the url
            if child.url == current_url:
                item.opened = True
                child.opened = True
                break
    return {"items": items, "request": context.request}

@register.inclusion_tag('wuliu/_inclusions/_form_input_field.html')
def show_form_input_field(field, label="", div_class="col-md"):
    """ Form field input box
    :param field: Form field object
    :param label: Custom label, defaults to the label attribute of the form field
    :param div_class: Custom class
    """
    if not label:
        label = field.label
    return {"field": field, "label": label, "div_class": div_class}

@register.inclusion_tag('wuliu/_inclusions/_form_input_field_with_append_select.html')
def show_form_input_field_with_append_select(field, field_append, label="", div_class="col-md"):
    """ Form field input box with a Dropdown button group on the right
    :param field: Form field object
    :param field_append: Form field for the Dropdown button group, must be ChoiceField
    :param label: Custom label, defaults to the label attribute of the form field
    :param div_class: Custom class
    """
    assert isinstance(field_append.field, ChoiceField)
    field_append_choices = [(str(k), v) for k, v in field_append.field.choices]
    field_append_initial_value = str(field_append.value() or field_append.initial)
    field_append_initial_string = dict(field_append_choices).get(field_append_initial_value, "")
    return {
        "field": field,
        "field_append": field_append,
        "field_append_choices": field_append_choices,
        "field_append_initial_value": field_append_initial_value,
        "field_append_initial_string": field_append_initial_string,
        "label": label,
        "div_class": div_class
    }

@register.inclusion_tag('wuliu/_inclusions/_waybill_routing_operation_info.html')
def show_waybill_routing_operation_info(wr: WaybillRouting):
    """ Generate detailed text content for waybill routing
    :param wr: WaybillRouting object
    """
    return wr._template_context()

@register.inclusion_tag('wuliu/_inclusions/_tables/_waybill_table.html')
def show_waybill_table(waybills_info_list, table_id, have_check_box=True, high_light_fee=False, high_light_dept_id=-1):
    """ Waybill table
    :param waybills_info_list: Table containing all waybill info dictionaries
    :param table_id: DataTables object id
    :param have_check_box: If False, do not show checkbox
    :param high_light_fee: Highlight the receivable fee cell (used only in department payment list)
    :param high_light_dept_id: Highlight department cell id (used only in department payment list)
    """
    return {
        "waybills_info_list": waybills_info_list,
        "table_id": table_id,
        "have_check_box": have_check_box,
        "high_light_fee": high_light_fee,
        "high_light_dept_id": high_light_dept_id,
    }

@register.inclusion_tag('wuliu/_inclusions/_tables/_waybill_table_row.html')
def show_waybill_table_row(waybill_dic, table_id, have_check_box=True):
    return {
        "waybill": waybill_dic,
        "table_id": table_id,
        "have_check_box": have_check_box,
    }

@register.inclusion_tag('wuliu/_inclusions/_tables/_stock_waybill_table.html')
def show_stock_waybill_table(waybills_info_list, table_id):
    return {
        "waybills_info_list": waybills_info_list,
        "table_id": table_id,
    }

@register.inclusion_tag('wuliu/_inclusions/_tables/_dst_stock_waybill_table.html')
def show_dst_stock_waybill_table(waybills_info_list, table_id):
    return {
        "waybills_info_list": waybills_info_list,
        "table_id": table_id,
    }

@register.inclusion_tag('wuliu/_inclusions/_tables/_transport_out_table.html')
def show_transport_out_table(transport_out_list, table_id):
    return {
        "transport_out_list": transport_out_list,
        "table_id": table_id,
    }

@register.inclusion_tag('wuliu/_inclusions/_tables/_department_payment_table.html')
def show_department_payment_table(department_payment_list, table_id):
    return {
        "department_payment_list": department_payment_list,
        "table_id": table_id,
    }

@register.inclusion_tag('wuliu/_inclusions/_tables/_cargo_price_payment_table.html')
def show_cargo_price_payment_table(cargo_price_payment_list, table_id):
    return {
        "cargo_price_payment_list": cargo_price_payment_list,
        "table_id": table_id,
    }

@register.inclusion_tag('wuliu/_inclusions/_tables/_customer_score_log_table.html')
def show_customer_score_log_table(customer_score_logs, table_id):
    return {
        "customer_score_logs": customer_score_logs,
        "table_id": table_id,
    }

@register.inclusion_tag('wuliu/_inclusions/_sign_for_waybill_info.html')
def show_sign_for_waybill_info(waybill_info_dic):
    return {"waybill": waybill_info_dic}

@register.inclusion_tag('wuliu/_inclusions/_permission_tree.html')
def _show_permission_tree(list_):
    """ Permission tree (used recursively) """
    return {"list": list_}

@register.inclusion_tag('wuliu/_inclusions/_full_permission_tree.html')
def show_full_permission_tree(div_id):
    """ Complete permission tree (with js) """
    return {"div_id": div_id, "list": PERMISSION_TREE_LIST}

@register.inclusion_tag('wuliu/_inclusions/_js/_export_table_to_excel.js.html')
def js_export_table_to_excel(table_id, button_css_selector, skip_td_num=1,
                             table_title="", table_title_is_js=False, min_time_interval=60):
    """ JS implementation code for export (excel table) function, already wrapped by <script> tag, do not add again
    :param table_id: DataTables object id
    :param button_css_selector: CSS selector for the export button (must escape single quotes)
    :param skip_td_num: Number of columns to skip when exporting, default is to skip the first column (serial number), note: should skip two columns if the table has checkboxes
    :param table_title: Custom title and file name for the exported table, defaults to the h1 tag text in the page content,
                        when table_title_is_js is False, it's best not to have special symbols (single/double quotes will be automatically removed)
    :param table_title_is_js: Whether the table_title parameter is a js expression, default is False
    :param min_time_interval: Minimum export time interval, default is 60 seconds
    """
    if table_title and not table_title_is_js:
        table_title = '"%s"' % table_title.replace('\"', "").replace("\'", "")
    return {
        "table_id": table_id,
        "button_css_selector": button_css_selector,
        "skip_td_num": skip_td_num,
        "table_title": table_title,
        "min_time_interval": min_time_interval,
    }

@register.inclusion_tag('wuliu/_inclusions/_js/_init_datatable.js.html')
def js_init_datatable(table_id, have_check_box=True, custom_fixed_columns_left=None):
    """ JS implementation code for initializing DataTable (init, select all, add serial number), already wrapped by <script> tag, do not add again
    :param table_id: id attribute of DataTables object
    :param have_check_box: Whether the second column of the table has a checkbox, default is True
    :param custom_fixed_columns_left: Custom number of columns fixed on the left side of the table,
                                      if None, freeze two columns (if have_check_box is True, also fix the second column's checkbox)
    """
    return {
        "table_id": table_id,
        "have_check_box": have_check_box,
        "custom_fixed_columns_left": custom_fixed_columns_left
    }
