from functools import wraps

from django.shortcuts import redirect
from django.http import Http404, HttpResponseForbidden
from django.utils import timezone

from .models import (
    User, Waybill, TransportOut, DepartmentPayment, CargoPricePayment, Permission, PermissionGroup,
    _get_global_settings,
)
from utils.common import ExpireLruCache, model_to_dict_


_EXPIRE_LRU_CACHE_1MIN = ExpireLruCache(expire_time=timezone.timedelta(minutes=1))

get_global_settings = ExpireLruCache(expire_time=timezone.timedelta(hours=3))(_get_global_settings)

@_EXPIRE_LRU_CACHE_1MIN
def _get_logged_user_by_id(user_id: int) -> User:
    """ Return user model object by user id """
    return User.objects.get(id=user_id)

def get_logged_user(request) -> User:
    """ Get the logged-in user object """
    return _get_logged_user_by_id(request.session["user"]["id"])

def get_logged_user_type(request) -> User.Types:
    """ Get the user type of the logged-in user """
    return get_logged_user(request).get_type

@_EXPIRE_LRU_CACHE_1MIN
def _get_user_permissions(user: User) -> set:
    """ Get the permissions owned by the user, note this method returns a set not a QuerySet """
    return set(user.permission.all().values_list("name", flat=True))

def is_logged_user_has_perm(request, perm_name: str) -> bool:
    """ Check if the logged-in user has the perm_name permission
    :return: True or False
    """
    if not perm_name:
        return True
    return perm_name in _get_user_permissions(get_logged_user(request))

def is_logged_user_is_goods_yard(request) -> bool:
    """ Determine whether the logged-in user belongs to the goods yard """
    return get_logged_user_type(request) == User.Types.GoodsYard

def _gen_permission_tree_list(root_pg_=PermissionGroup.objects.get(father__isnull=True)) -> list:
    """ Generate a list based on the hierarchical structure of all permission groups and permissions, for frontend rendering """
    tree_list = []
    for pg in PermissionGroup.objects.filter(father=root_pg_):
        tree_list.append({
            "id": pg.id, "name": pg.name, "print_name": pg.print_name, "children": _gen_permission_tree_list(pg)
        })
    for p in Permission.objects.filter(father=root_pg_):
        tree_list.append({
            "id": p.id, "name": p.name, "print_name": p.print_name,
        })
    return tree_list

PERMISSION_TREE_LIST = _gen_permission_tree_list()

def login_required(raise_404=False):
    """ Custom decorator for decorating route methods
    If the user is not logged in, redirect to the login page
    If raise_404 is True, redirect to the 404 page
    """
    def _login_required(func):
        @wraps(func)
        def login_check(request, *args, **kwargs):
            if not request.session.get("user"):
                if raise_404:
                    raise Http404
                return redirect("wuliu:login")
            return func(request, *args, **kwargs)
        return login_check
    return _login_required

def check_permission(perm_name: str):
    """ Custom decorator to check if the user has the perm_name permission before the request
    If the user does not have perm_name permission, redirect to the 403 page
    """
    def _check_permission(func):
        @wraps(func)
        def perm_check(request, *args, **kwargs):
            if perm_name and not is_logged_user_has_perm(request, perm_name):
                return HttpResponseForbidden()
            return func(request, *args, **kwargs)
        return perm_check
    return _check_permission

def check_administrator(func):
    """ Custom decorator to check if the user is an administrator before the request
    If not an administrator, redirect to the 403 page
    """
    @wraps(func)
    def admin_check(request, *args, **kwargs):
        if not get_logged_user(request).administrator:
            return HttpResponseForbidden()
        return func(request, *args, **kwargs)
    return admin_check

def waybill_to_dict(waybill_obj: Waybill) -> dict:
    """ Convert Waybill object to dictionary """
    waybill_dic = model_to_dict_(waybill_obj)
    waybill_dic["id_"] = waybill_obj.get_full_id
    waybill_dic["fee_type_id"] = waybill_dic["fee_type"]
    waybill_dic["fee_type"] = waybill_obj.get_fee_type_display()
    waybill_dic["status_id"] = waybill_dic["status"]
    waybill_dic["status"] = waybill_obj.get_status_display()
    if waybill_obj.return_waybill is not None:
        waybill_dic["return_waybill"] = waybill_to_dict(waybill_obj.return_waybill)
    else:
        waybill_dic["return_waybill"] = None
    return waybill_dic

def transport_out_to_dict(transport_out_obj: TransportOut) -> dict:
    """ Convert TransportOut object to dictionary """
    to_dic = model_to_dict_(transport_out_obj)
    to_dic["id_"] = transport_out_obj.get_full_id
    to_dic["status_id"] = to_dic["status"]
    to_dic["status"] = transport_out_obj.get_status_display()
    to_dic.update(transport_out_obj.gen_waybills_info())
    return to_dic

def department_payment_to_dict(department_payment_obj: DepartmentPayment) -> dict:
    """ Convert DepartmentPayment object to dictionary """
    dp_dic = model_to_dict_(department_payment_obj)
    dp_dic["id_"] = department_payment_obj.get_full_id
    dp_dic["status_id"] = dp_dic["status"]
    dp_dic["status"] = department_payment_obj.get_status_display()
    total_fee_dic = department_payment_obj.gen_total_fee()
    dp_dic["total_fee_now"] = total_fee_dic["fee_now"]
    dp_dic["total_fee_sign_for"] = total_fee_dic["fee_sign_for"]
    dp_dic["total_cargo_price"] = total_fee_dic["cargo_price"]
    dp_dic["final_total_fee"] = sum(total_fee_dic.values())
    return dp_dic

def cargo_price_payment_to_dict(cargo_price_payment_obj: CargoPricePayment) -> dict:
    """ 将CargoPricePayment对象转为字典 """
    cpp_dic = model_to_dict_(cargo_price_payment_obj)
    cpp_dic["id_"] = cargo_price_payment_obj.get_full_id
    cpp_dic["status_id"] = cpp_dic["status"]
    cpp_dic["status"] = cargo_price_payment_obj.get_status_display()
    total_fee_dic = cargo_price_payment_obj.gen_total_fee()
    cpp_dic["total_cargo_price"] = total_fee_dic["cargo_price"]
    cpp_dic["total_deduction_fee"] = total_fee_dic["deduction_fee"]
    cpp_dic["total_cargo_handling_fee"] = total_fee_dic["cargo_handling_fee"]
    cpp_dic["final_fee"] = (
        total_fee_dic["cargo_price"] - total_fee_dic["deduction_fee"] - total_fee_dic["cargo_handling_fee"]
    )
    return cpp_dic
