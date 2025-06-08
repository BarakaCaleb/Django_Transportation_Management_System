# ... (imports and unchanged code above)
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth.hashers import check_password
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
import datetime
from . import forms
import sys
import os
from wuliu.common import get_logged_user_type, is_logged_user_has_perm  # Ensure 'wuliu/utils.py' exists and contains these functions
from .models import Waybill, TransportOut, User  # Add this import for Waybill, TransportOut, and User models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import get_logged_user_type, is_logged_user_has_perm  # Adjusted import for utils outside the app directory



class WaybillSearchView(View):

    form_class = forms.WaybillSearchForm
    template_name = ""
    need_login = True
    need_permissions = ()

    def __init__(self, *args, **kwargs):
        assert getattr(self, "template_name"), (
            "Subclasses inherited must specify the 'template_name' property when defining!"
        )
        assert isinstance(self.form_class(), forms.WaybillSearchForm)
        super().__init__(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {
                "form": self.form_class.init_from_request(request),
                "waybill_list": [],
                "logged_user_type": get_logged_user_type(request),
            }
        )

    def post(self, request, *args, **kwargs):
        form = self.form_class.init_from_request(request, data=request.POST)
        waybill_list = []
        if form.is_valid():
            try:
                waybill_list = form.gen_waybill_list_to_queryset()
            except:
                if settings.DEBUG:
                    raise
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "waybill_list": waybill_list,
                "logged_user_type": get_logged_user_type(request),
            }
        )

    def dispatch(self, request, *args, **kwargs):
        if self.need_login and not request.session.get("user"):
            return redirect("wuliu:login")
        for perm in self.need_permissions:
            if not is_logged_user_has_perm(request, perm):
                return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

def _transport_out_detail_view(request, render_path):
    transport_out_id = request.GET.get("transport_out_id")
    if not transport_out_id:
        return HttpResponseBadRequest()
    transport_out = get_object_or_404(TransportOut, pk=transport_out_id)
    form = forms.TransportOutForm.init_from_request(request, instance=transport_out)
    form.add_id_field(id_=transport_out.id, id_full=transport_out.get_full_id)
    form.change_to_detail_form()
    return render(
        request,
        render_path,
        {
            "form": form,
            "detail_view": True,
            "waybills_info_list": transport_out.waybills.all().select_related("src_department", "dst_department"),
        }
    )

def _transport_out_search_view(request, render_path, search_mode):
    assert search_mode in ("src", "dst"), 'search_mode parameter can only be "src" or "dst"'
    if request.method == "GET":
        form = forms.TransportOutSearchForm.init_from_request(request, search_mode=search_mode)
        return render(
            request,
            render_path,
            {
                "form": form,
                "transport_out_list": [],
            }
        )
    if request.method == "POST":
        form = forms.TransportOutSearchForm.init_from_request(request, data=request.POST, search_mode=search_mode)
        transport_out_list = []
        if form.is_valid():
            try:
                transport_out_list = form.gen_transport_out_list_to_queryset()
            except ValueError:
                pass
        return render(
            request,
            render_path,
            {
                "form": form,
                "transport_out_list": transport_out_list,
            }
        )

def login(request):

    def _login_abort(message_text):
        messages.error(request, message_text)
        return redirect("wuliu:login")

    if request.method == "GET":
        if request.session.get('user'):
            return redirect("wuliu:welcome")
        return render(request, 'wuliu/login.html')
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            user = User.objects.get(name=username)
        except User.DoesNotExist:
            return _login_abort('Incorrect username or password, please try again!')
        if not user.enabled:
            return _login_abort('This user is not enabled, please contact the administrator!')
        if not check_password(password, user.password):
            return _login_abort('Incorrect username or password, please try again!')
        request.session['user'] = {
            "logged_in_time": timezone.make_naive(timezone.now()).strftime("%Y-%m-%d %H:%M:%S"),
            "id": user.id,
            "name": user.name,
            "department_id": user.department_id,
            "department_name": user.department.name,
        }
        return redirect("wuliu:welcome")

def logout(request):
    request.session.flush()
    request.COOKIES.clear()
    return redirect("wuliu:login")

@login_required()
def welcome(request):
    # messages.debug(request, "Test debug message...")
    # messages.info(request, "Test info message...")
    # messages.success(request, "Test success message...")
    # messages.warning(request, "Test warning message...")
    # messages.error(request, "Test error message...")
    logged_user_type = get_logged_user_type(request)
    dic = {
        "today": {"waybill": 0, "transport_out": 0, "arrival": 0, "sign_for": 0},
        "wait": {"waybill": 0, "transport_out": 0, "arrival": 0, "sign_for": 0},
    }
    today_start_datetime = timezone.make_aware(
        datetime.datetime.combine(datetime.date.today(), datetime.time(0, 0))
    )
    today_end_datetime = timezone.make_aware(
        datetime.datetime.combine(datetime.date.today(), datetime.time(23, 59, 59))
    )
    today_weekday = timezone.now().isoweekday()
    weekdays = [
        {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}.get(
            today_weekday-i if today_weekday-i > 0 else today_weekday+7-i
        )
        for i in range(7)[::-1]
    ]
    # Number of new waybills and freight income for each day in the past 14 days
    # Branches and goods yards only count new waybills for their own department (although goods yards do not have billing rights...)
    if logged_user_type == User.Types.GoodsYard:
        waybill_num_in_past_two_weeks = [0] * 14
        waybill_fee_in_past_two_weeks = [0] * 14
    else:
        waybill_num_in_past_two_weeks = []
        waybill_fee_in_past_two_weeks = []
        for i in range(14)[::-1]:
            queryset = Waybill.objects.only("pk", "fee").filter(
                    create_time__gte=today_start_datetime - timezone.timedelta(days=i),
                    create_time__lte=today_end_datetime - timezone.timedelta(days=i),
                ).exclude(status=Waybill.Statuses.Dropped)
            if logged_user_type == User.Types.Branch:
                queryset = queryset.filter(src_department__id=request.session["user"]["department_id"])
            day_info = queryset.aggregate(fee_total=Sum("fee"), count=Count("pk"))
            waybill_num_in_past_two_weeks.append(day_info["count"])
            waybill_fee_in_past_two_weeks.append(day_info["fee_total"] or 0)
    # Today's new waybills
    dic["today"]["waybill"] = waybill_num_in_past_two_weeks[-1]
    # Today's departures
    today_start_datetime = timezone.make_aware(
        datetime.datetime.combine(datetime.date.today(), datetime.time(0, 0))
    )
    today_end_datetime = timezone.make_aware(
        datetime.datetime.combine(datetime.date.today(), datetime.time(23, 59, 59))
    )
    today_transport_out = TransportOut.objects.filter(
        start_time__gte=today_start_datetime,
        start_time__lte=today_end_datetime,
        status__in=(TransportOut.Statuses.OnTheWay, TransportOut.Statuses.Arrived),
    )
    if logged_user_type not in (User.Types.Administrator, User.Types.Company):
        today_transport_out = today_transport_out.filter(src_department__id=request.session["user"]["department_id"])
    dic["today"]["transport_out"] = today_transport_out.aggregate(_=Count("waybills"))["_"] or 0
    # Today's arrivals
    today_arrival = Waybill.objects.filter(
        arrival_time__gte=today_start_datetime, arrival_time__lte=today_end_datetime,
    )
    if logged_user_type not in (User.Types.Administrator, User.Types.Company):
        today_arrival = today_arrival.filter(dst_department__id=request.session["user"]["department_id"])
    dic["today"]["arrival"] = today_arrival.count() or 0
    # Today's sign-for
    today_sign_for = Waybill.objects.filter(
        sign_for_time__gte=today_start_datetime, sign_for_time__lte=today_end_datetime,
    )
    if logged_user_type not in (User.Types.Administrator, User.Types.Company):
        today_sign_for = today_sign_for.filter(dst_department__id=request.session["user"]["department_id"])
    dic["today"]["sign_for"] = today_sign_for.count()
    # Pending orders
    dic["wait"]["waybill"] = 0
    # Pending departures
    if logged_user_type == User.Types.GoodsYard:
        dic["wait"]["transport_out"] = Waybill.objects.filter(
                status__in=(Waybill.Statuses.GoodsYardArrived, Waybill.Statuses.GoodsYardLoaded)
            ).count()
    elif logged_user_type == User.Types.Branch:
        dic["wait"]["transport_out"] = Waybill.objects.filter(
                src_department__id=request.session["user"]["department_id"],
                status__in=(Waybill.Statuses.Created, Waybill.Statuses.Loaded),
            ).count()
    else:
        dic["wait"]["transport_out"] = Waybill.objects.filter(
                status__in=(Waybill.Statuses.Created, Waybill.Statuses.Loaded)
            ).count()
    # Pending arrivals
    wait_arrival = TransportOut.objects.filter(status=TransportOut.Statuses.OnTheWay)
    if logged_user_type not in (User.Types.Administrator, User.Types.Company):
        wait_arrival = wait_arrival.filter(dst_department__id=request.session["user"]["department_id"])
    dic["wait"]["arrival"] = wait_arrival.count()
    # Pending sign-for
    wait_sign_for = Waybill.objects.filter(status=Waybill.Statuses.Arrived)
    if logged_user_type not in (User.Types.Administrator, User.Types.Company):
        wait_sign_for = wait_sign_for.filter(dst_department__id=request.session["user"]["department_id"])
    dic["wait"]["sign_for"] = wait_sign_for.count()

    return render(
        request,
        "wuliu/welcome.html",
        {
            "data_dic": dic,
            "weekdays": weekdays,
            "waybill_num_last_week": waybill_num_in_past_two_weeks[:7],
            "waybill_num_this_week": waybill_num_in_past_two_weeks[7:],
            "waybill_num_this_week_total": sum(waybill_num_in_past_two_weeks[7:]),
            "waybill_num_change_rate_percentage": (
                (sum(waybill_num_in_past_two_weeks[7:]) / sum(waybill_num_in_past_two_weeks[:7]) - 1) * 100
                if sum(waybill_num_in_past_two_weeks[:7]) else (
                    100 if sum(waybill_num_in_past_two_weeks[7:]) else 0
                )
            ),
            "waybill_fee_last_week": waybill_fee_in_past_two_weeks[:7],
            "waybill_fee_this_week": waybill_fee_in_past_two_weeks[7:],
            "waybill_fee_this_week_total": sum(waybill_fee_in_past_two_weeks[7:]),
            "waybill_fee_change_rate_percentage": (
                (sum(waybill_fee_in_past_two_weeks[7:]) / sum(waybill_fee_in_past_two_weeks[:7]) - 1) * 100
                if sum(waybill_fee_in_past_two_weeks[:7]) else (
                    100 if sum(waybill_fee_in_past_two_weeks[7:]) else 0
                )
            ),
        }
    )

# ... (rest of the code unchanged except for Chinese comments/messages, which should be translated similarly)
