def api_json_response(message_text="unknown", code=400, **kwargs):
    """ Return a standard ajax json response format """
    return UnescapedJsonResponse({
        "code": code,
        "data": {"message": message_text} | kwargs,
    })

class ActionApi(View):

    """ A generic class-based view to simplify the following steps:
    Read parameters from request.POST -> authentication & data cleaning -> query from database -> update database
    If you need to pass variables between different methods, you can use the self._private_dic dictionary
    Note: Only supports POST requests
    """

    # ... rest unchanged

    def actions(self):
        """ Perform authentication, data cleaning, queries, etc. here
        To interrupt, you should raise ActionApi.AbortException with a prompt text
        """
        raise NotImplementedError

    def write_database(self):
        """ Perform database update operations here """
        pass

    def actions_after_success(self):
        """ Perform follow-up operations after successful database update here """
        pass

    # ... rest unchanged

@csrf_exempt
@require_POST
def check_old_password(request):
    """ Check the current password (old password) of the logged-in user """
    # ... unchanged

@_api_login_required
@require_GET
def get_customer_info(request):
    """ Get customer details """
    # ... unchanged

@_api_login_required
@require_GET
def get_department_info(request):
    """ Get department details """
    # ... unchanged

@_api_login_required
@require_GET
def get_waybills_info(request):
    """ Get waybill details """
    # ... unchanged

@_api_login_required
@require_GET
def get_truck_info(request):
    """ Get truck details """
    # ... unchanged

@_api_login_required
@require_GET
def get_user_info(request):
    """ Get user details """
    # ... unchanged

@_api_login_required
@require_GET
def get_user_permission(request):
    """ Get permissions owned by the user """
    # ... unchanged

@_api_login_required
@require_GET
def gen_standard_fee(request):
    """ Given shipping department id, arrival department id, total cargo volume and weight, calculate standard freight """
    # ... unchanged

@_api_login_required
@_api_check_permission("manage_transport_out__add_edit_delete_start")
@require_POST
@csrf_exempt
def remove_waybill_when_add_transport_out(request):
    """ Remove waybill when adding a new transport out """
    # ... unchanged

@_api_login_required
@_api_check_permission("manage_transport_out__add_edit_delete_start")
@require_POST
@csrf_exempt
def remove_waybill_when_edit_transport_out(request):
    """ Remove waybill when editing transport out information """
    # ... unchanged

@_api_login_required
@_api_check_permission("manage_sign_for")
@require_POST
@csrf_exempt
def add_waybill_when_confirm_sign_for(request):
    """ Add waybill when confirming sign for """
    # ... unchanged

@_api_login_required
@_api_check_permission("manage_cargo_price_payment__add_edit_delete_submit")
@require_POST
@csrf_exempt
def add_waybill_when_edit_cargo_price_payment(request):
    """ Add waybill when editing cargo price payment """
    # ... unchanged

class DropWaybill(ActionApi):
    """ Void waybill """

    need_permissions = ("manage_waybill__edit_delete_print", )

    def actions(self):
        drop_id = self.request.POST.get("drop_waybill_id")
        drop_reason = self.request.POST.get("drop_waybill_reason")
        if not (drop_id and drop_reason):
            raise ActionApi.AbortException("Invalid request format!")
        try:
            waybill = Waybill.objects.get(id=drop_id)
        except Waybill.DoesNotExist as exc:
            raise ActionApi.AbortException("The waybill does not exist!") from exc
        # Prohibit cross-department voiding of waybills
        if waybill.src_department_id != self.request.session["user"]["department_id"]:
            raise ActionApi.AbortException("Cross-department voiding of waybills is prohibited!")
        # Only waybills that are not loaded/dispatched can be voided
        if waybill.status != Waybill.Statuses.Created:
            raise ActionApi.AbortException('Only waybills in "Created" status can be voided!')
        if waybill.return_waybill:
            raise ActionApi.AbortException("Return waybills cannot be voided")
        self._private_dic = {
            "waybill": waybill, "drop_reason": drop_reason,
        }

    def write_database(self):
        # ... unchanged

    def actions_after_success(self):
        self.response_dic["data"]["waybill_status_now"] = Waybill.Statuses.Dropped.value

class DropTransportOut(ActionApi):
    """ Delete transport out """

    need_permissions = ("manage_transport_out__add_edit_delete_start", )

    def actions(self):
        drop_id = self.request.POST.get("drop_transport_out_id")
        if not drop_id:
            raise ActionApi.AbortException("Invalid request format!")
        try:
            to_obj = TransportOut.objects.get(id=drop_id)
        except TransportOut.DoesNotExist as exc:
            raise ActionApi.AbortException("The transport out does not exist!") from exc
        # Prohibit cross-department deletion of transport out
        if to_obj.src_department_id != self.request.session["user"]["department_id"]:
            raise ActionApi.AbortException("Cross-department deletion of transport out is prohibited!")
        # Prohibit deletion of dispatched transport out
        if to_obj.status != TransportOut.Statuses.Ready:
            raise ActionApi.AbortException('Only transport out in "Cargo Loaded" status can be deleted!')
        # If the transport out has no waybills loaded
        to_obj_waybills = to_obj.waybills.all()
        if not to_obj_waybills.exists():
            self._private_dic = {"to_obj": to_obj, "waybills_status": 0}
            return
        # Ensure all waybills in the transport out have the same status and are in "Loaded" or "Goods Yard Loaded" status
        try:
            waybills_status = to_obj_waybills.order_by("status").values("status").distinct()
            assert len(waybills_status) == 1
            waybills_status = waybills_status[0]["status"]
            if is_logged_user_is_goods_yard(self.request):
                assert waybills_status == Waybill.Statuses.GoodsYardLoaded.value
            else:
                assert waybills_status == Waybill.Statuses.Loaded.value
        except AssertionError as exc:
            raise ActionApi.AbortException("There are waybills with abnormal status in this transport out!") from exc
        self._private_dic = {
            "to_obj": to_obj, "waybills_status": waybills_status,
        }

    def write_database(self):
        # ... unchanged

class StartTransportOut(ActionApi):
    """ Dispatch transport out """

    need_permissions = ("manage_transport_out__add_edit_delete_start", )

    def actions(self):
        start_id = self.request.POST.get("start_transport_out_id")
        if not start_id:
            raise ActionApi.AbortException("Invalid request format!")
        try:
            to_obj = TransportOut.objects.get(id=start_id)
        except TransportOut.DoesNotExist as exc:
            raise ActionApi.AbortException("The transport out does not exist!") from exc
        # Prohibit cross-department dispatch
        if to_obj.src_department_id != self.request.session["user"]["department_id"]:
            raise ActionApi.AbortException("Cross-department operation on transport out is prohibited!")
        # Prohibit dispatching already dispatched transport out
        if to_obj.status != TransportOut.Statuses.Ready:
            raise ActionApi.AbortException('Only transport out in "Cargo Loaded" status can be dispatched!')
        # If the transport out has no waybills loaded
        to_obj_waybills = to_obj.waybills.all()
        if not to_obj_waybills.exists():
            raise ActionApi.AbortException("There are no waybills loaded in this transport out!")
        # Ensure all waybills in the transport out have the same status and are in "Loaded" or "Goods Yard Loaded" status
        try:
            waybills_status = to_obj_waybills.order_by("status").values("status").distinct()
            assert len(waybills_status) == 1
            waybills_status = waybills_status[0]["status"]
            if is_logged_user_is_goods_yard(self.request):
                assert waybills_status == Waybill.Statuses.GoodsYardLoaded.value
            else:
                assert waybills_status == Waybill.Statuses.Loaded.value
        except AssertionError as exc:
            raise ActionApi.AbortException("There are waybills with abnormal status in this transport out!") from exc
        timezone_now = timezone.now()
        self._private_dic = {
            "to_obj": to_obj, "waybills_status": waybills_status, "timezone_now": timezone_now,
        }

    def write_database(self):
        # ... unchanged

    def actions_after_success(self):
        timezone_now = self._private_dic["timezone_now"]
        timezone_now_str = timezone.make_naive(timezone_now).strftime("%Y-%m-%d %H:%M:%S")
        self.response_dic["data"]["start_time"] = timezone_now_str
        self.response_dic["data"]["start_time_timestamp"] = timezone_now.timestamp()

class ConfirmArrival(ActionApi):
    """ Confirm arrival """

    need_permissions = ("manage_arrival", )

    def actions(self):
        to_id = self.request.POST.get("transport_out_id")
        if not to_id:
            raise ActionApi.AbortException("Invalid request format!")
        try:
            to_obj = TransportOut.objects.get(id=to_id)
        except TransportOut.DoesNotExist as exc:
            raise ActionApi.AbortException("The transport out does not exist!") from exc
        if to_obj.dst_department_id != self.request.session["user"]["department_id"]:
            raise ActionApi.AbortException("Cross-department operation on transport out is prohibited!")
        # Only transport out in "On The Way" status can be confirmed as arrived
        if to_obj.status != TransportOut.Statuses.OnTheWay:
            raise ActionApi.AbortException('Only transport out in "On The Way" status can be confirmed as arrived!')
        # Ensure all waybills in the transport out have the same status and are in "Departed" or "Goods Yard Departed" status
        try:
            waybills_status = to_obj.waybills.order_by("status").values("status").distinct()
            assert len(waybills_status) == 1
            waybills_status = waybills_status[0]["status"]
            if is_logged_user_is_goods_yard(self.request):
                assert waybills_status == Waybill.Statuses.Departed.value
            else:
                assert waybills_status == Waybill.Statuses.GoodsYardDeparted.value
        except AssertionError as exc:
            raise ActionApi.AbortException("There are waybills with abnormal status in this transport out!") from exc
        self._private_dic = {
            "to_obj": to_obj, "waybills_status": waybills_status,
        }

    def write_database(self):
        # ... unchanged

    def actions_after_success(self):
        messages.success(self.request, "Operation successful")

class ConfirmSignFor(ActionApi):
    """ Confirm sign for """

    need_permissions = ("manage_sign_for", )

    def actions(self):
        sign_for_waybill_ids = self.request.POST.get("sign_for_waybill_ids", "").strip()
        sign_for_name = self.request.POST.get("sign_for_name", "").strip()
        sign_for_credential_num = self.request.POST.get("sign_for_credential_num", "").strip()
        if not (sign_for_waybill_ids and sign_for_name and sign_for_credential_num):
            raise ActionApi.AbortException("Invalid request format!")
        try:
            sign_for_waybill_ids = validate_comma_separated_integer_list_and_split(sign_for_waybill_ids)
        except ValidationError as exc:
            raise ActionApi.AbortException("Invalid request format!") from exc
        if Waybill.objects.filter(id__in=sign_for_waybill_ids).count() != len(sign_for_waybill_ids):
            raise ActionApi.AbortException("There are non-existent waybills in the request!")
        # Prohibit signing for waybills whose arrival department does not match the current department, and waybills not in "Arrived" status
        if Waybill.objects.filter(id__in=sign_for_waybill_ids).filter(
                ~Q(dst_department__id=self.request.session["user"]["department_id"]) |
                ~Q(status=Waybill.Statuses.Arrived)).exists():
            raise ActionApi.AbortException("There are waybills with abnormal status in the request!")
        timezone_now = timezone.now()
        self._private_dic = {
            "sign_for_waybill_ids": sign_for_waybill_ids,
            "sign_for_name": sign_for_name,
            "sign_for_credential_num": sign_for_credential_num,
            "timezone_now": timezone_now,
        }

    def write_database(self):
        # ... unchanged

    def actions_after_success(self):
        messages.success(self.request, "Operation successful")

class ModifyRemarkDepartmentPayment(ActionApi):
    """ Modify department payment remark """

    need_permissions = ("manage_department_payment__search", )

    def actions(self):
        dp_id = self.request.POST.get("dp_id")
        remark_dept_type = self.request.POST.get("remark_dept_type")
        remark_text = self.request.POST.get("remark_text").strip()
        if not (dp_id and remark_dept_type and remark_text):
            raise ActionApi.AbortException("Invalid request format!")
        try:
            dp_obj = DepartmentPayment.objects.get(id=dp_id)
        except (ValueError, DepartmentPayment.DoesNotExist) as exc:
            raise ActionApi.AbortException("The payment does not exist!") from exc
        if dp_obj.status == DepartmentPayment.Statuses.Settled:
            raise ActionApi.AbortException("Settled payments cannot be modified.")
        if remark_dept_type == "src":
            if self.request.session["user"]["department_id"] != dp_obj.src_department_id:
                raise ActionApi.AbortException("You do not have permission to modify the remark.")
            dp_obj.src_remark = remark_text
        elif remark_dept_type == "dst":
            if self.request.session["user"]["department_id"] != dp_obj.dst_department_id:
                raise ActionApi.AbortException("You do not have permission to modify the remark.")
            dp_obj.dst_remark = remark_text
        else:
            raise ActionApi.AbortException("Invalid request format!")
        self._private_dic = {"dp_obj": dp_obj}

    def write_database(self):
        self._private_dic["dp_obj"].save(update_fields=["src_remark", "dst_remark"])

class DropDepartmentPayment(ActionApi):
    """ Delete payment """

    need_permissions = ("manage_department_payment__add_delete", )

    def actions(self):
        dp_ids = self.request.POST.get("dp_ids", "")
        try:
            dp_ids = validate_comma_separated_integer_list_and_split(dp_ids)
        except ValidationError as exc:
            raise ActionApi.AbortException("Invalid request format!") from exc
        dp_qs = DepartmentPayment.objects.filter(id__in=dp_ids)
        if dp_qs.exclude(status=DepartmentPayment.Statuses.Created).exists():
            raise ActionApi.AbortException("Only payments that have not been reviewed can be deleted!")
        self._private_dic = {"dp_queryset": dp_qs}

    def write_database(self):
        self._private_dic["dp_queryset"].delete()

class ConfirmReviewDepartmentPayment(ActionApi):
    """ Review payment """

    need_permissions = ("manage_department_payment__review", )

    def actions(self):
        dp_ids = self.request.POST.get("dp_ids", "")
        try:
            dp_ids = validate_comma_separated_integer_list_and_split(dp_ids)
        except ValidationError as exc:
            raise ActionApi.AbortException("Invalid request format!") from exc
        dp_qs = DepartmentPayment.objects.filter(id__in=dp_ids)
        if dp_qs.exclude(status=DepartmentPayment.Statuses.Created).exists():
            raise ActionApi.AbortException("Only payments that have not been reviewed can be reviewed!")
        self._private_dic = {"dp_queryset": dp_qs}

    def write_database(self):
        self._private_dic["dp_queryset"].update(status=DepartmentPayment.Statuses.Reviewed)

class ConfirmPayDepartmentPayment(ActionApi):
    """ Confirm payment of payment """

    need_permissions = ("manage_department_payment__pay", )

    def actions(self):
        dp_ids = self.request.POST.get("dp_ids", "")
        try:
            dp_ids = validate_comma_separated_integer_list_and_split(dp_ids)
        except ValidationError as exc:
            raise ActionApi.AbortException("Invalid request format!") from exc
        dp_qs = DepartmentPayment.objects.filter(id__in=dp_ids)
        if dp_qs.exclude(status=DepartmentPayment.Statuses.Reviewed).exists():
            raise ActionApi.AbortException('Only payments in "Reviewed" status can be confirmed for payment!')
        if dp_qs.exclude(src_department_id=self.request.session["user"]["department_id"]).exists():
            raise ActionApi.AbortException("You can only confirm payment for payments of the current department.")
        self._private_dic = {"dp_queryset": dp_qs}

    def write_database(self):
        self._private_dic["dp_queryset"].update(status=DepartmentPayment.Statuses.Paid)

class ConfirmSettleAccountsDepartmentPayment(ActionApi):
    """ Confirm settlement of payment """

    need_permissions = ("manage_department_payment__settle", )

    def actions(self):
        dp_ids = self.request.POST.get("dp_ids", "")
        try:
            dp_ids = validate_comma_separated_integer_list_and_split(dp_ids)
        except ValidationError as exc:
            raise ActionApi.AbortException("Invalid request format!") from exc
        dp_qs = DepartmentPayment.objects.filter(id__in=dp_ids)
        if dp_qs.exclude(status=DepartmentPayment.Statuses.Paid).exists():
            raise ActionApi.AbortException('Only payments in "Paid" status can be settled.')
        self._private_dic = {"dp_queryset": dp_qs, "timezone_now": timezone.now()}

    def write_database(self):
        # Update payment status
        self._private_dic["dp_queryset"].update(
            status=DepartmentPayment.Statuses.Settled,
            settle_accounts_time=self._private_dic["timezone_now"],
        )
        for dp in self._private_dic["dp_queryset"]:
            dp.update_customer_score_change()

    def actions_after_success(self):
        timezone_now = self._private_dic["timezone_now"]
        timezone_now_str = timezone.make_naive(timezone_now).strftime("%Y-%m-%d %H:%M:%S")
        self.response_dic["data"]["dp_settle_accounts_time"] = timezone_now_str
        self.response_dic["data"]["dp_settle_accounts_time_timestamp"] = timezone_now.timestamp()

class DropCargoPricePayment(ActionApi):
    """ Delete transfer order """

    need_permissions = ("manage_cargo_price_payment__add_edit_delete_submit", )

    def actions(self):
        try:
            cpp_id = self.request.POST.get("cpp_id", "").strip()
            cpp_obj = CargoPricePayment.objects.get(id=cpp_id)
        except (ValueError, CargoPricePayment.DoesNotExist) as exc:
            raise ActionApi.AbortException("The transfer order does not exist!") from exc
        if cpp_obj.status not in (CargoPricePayment.Statuses.Created, CargoPricePayment.Statuses.Rejected):
            raise ActionApi.AbortException("Submitted transfer orders cannot be deleted!")
        if cpp_obj.create_user != get_logged_user(self.request):
            raise ActionApi.AbortException("You can only delete transfer orders you created!")
        self._private_dic["cpp_obj"] = cpp_obj

    def write_database(self):
        self._private_dic["cpp_obj"].delete()

class ConfirmSubmitCargoPricePayment(ActionApi):
    """ Confirm submission of transfer order """

    need_permissions = ("manage_cargo_price_payment__add_edit_delete_submit", )

    def actions(self):
        try:
            cpp_id = self.request.POST.get("cpp_id", "").strip()
            cpp_obj = CargoPricePayment.objects.get(id=cpp_id)
        except (ValueError, CargoPricePayment.DoesNotExist) as exc:
            raise ActionApi.AbortException("The transfer order does not exist!") from exc
        if cpp_obj.status not in (CargoPricePayment.Statuses.Created, CargoPricePayment.Statuses.Rejected):
            raise ActionApi.AbortException('Only transfer orders in "Created" status can be submitted!')
        if cpp_obj.create_user != get_logged_user(self.request):
            raise ActionApi.AbortException("You can only submit transfer orders you created!")
        self._private_dic["cpp_obj"] = cpp_obj

    def write_database(self):
        self._private_dic["cpp_obj"].status = CargoPricePayment.Statuses.Submitted
        self._private_dic["cpp_obj"].save()

class ConfirmReviewCargoPricePayment(ActionApi):
    """ Review transfer order """

    need_permissions = ("manage_cargo_price_payment__review_reject", )

    def actions(self):
        try:
            cpp_id = self.request.POST.get("cpp_id", "").strip()
            cpp_obj = CargoPricePayment.objects.get(id=cpp_id)
        except (ValueError, CargoPricePayment.DoesNotExist) as exc:
            raise ActionApi.AbortException("The transfer order does not exist!") from exc
        if cpp_obj.status != CargoPricePayment.Statuses.Submitted:
            raise ActionApi.AbortException('Only transfer orders in "Submitted" status can be reviewed!')
        self._private_dic["cpp_obj"] = cpp_obj

    def write_database(self):
        self._private_dic["cpp_obj"].status = CargoPricePayment.Statuses.Reviewed
        self._private_dic["cpp_obj"].reject_reason = ""
        self._private_dic["cpp_obj"].save()

class ConfirmRejectCargoPricePayment(ActionApi):
    """ Reject transfer order """

    need_permissions = ("manage_cargo_price_payment__review_reject", )

    def actions(self):
        try:
            cpp_id = self.request.POST.get("cpp_id", "").strip()
            reject_reason = self.request.POST.get("reject_reason", "").strip()
            cpp_obj = CargoPricePayment.objects.get(id=cpp_id)
        except (ValueError, CargoPricePayment.DoesNotExist) as exc:
            raise ActionApi.AbortException("The transfer order does not exist!") from exc
        if not reject_reason:
            raise ActionApi.AbortException("Rejection reason cannot be empty!")
        if cpp_obj.status != CargoPricePayment.Statuses.Submitted:
            raise ActionApi.AbortException('Only transfer orders in "Submitted" status can be rejected!')
        self._private_dic["cpp_obj"] = cpp_obj
        self._private_dic["reject_reason"] = reject_reason

    def write_database(self):
        self._private_dic["cpp_obj"].status = CargoPricePayment.Statuses.Rejected
        self._private_dic["cpp_obj"].reject_reason = self._private_dic["reject_reason"]
        self._private_dic["cpp_obj"].save()

class ConfirmPayCargoPricePayment(ActionApi):
    """ Confirm payment of transfer order """

    need_permissions = ("manage_cargo_price_payment__pay", )

    def actions(self):
        try:
            cpp_id = self.request.POST.get("cpp_id", "").strip()
            cpp_obj = CargoPricePayment.objects.get(id=cpp_id)
        except (ValueError, CargoPricePayment.DoesNotExist) as exc:
            raise ActionApi.AbortException("The transfer order does not exist!") from exc
        if cpp_obj.status != CargoPricePayment.Statuses.Reviewed:
            raise ActionApi.AbortException('Only transfer orders in "Reviewed" status can be confirmed for payment!')
        self._private_dic = {"cpp_obj": cpp_obj, "timezone_now": timezone.now()}

    def write_database(self):
        cpp_obj = self._private_dic["cpp_obj"]
        cpp_obj.status = CargoPricePayment.Statuses.Paid
        cpp_obj.settle_accounts_time = self._private_dic["timezone_now"]
        cpp_obj.save()

    def actions_after_success(self):
        timezone_now = self._private_dic["timezone_now"]
        timezone_now_str = timezone.make_naive(timezone_now).strftime("%Y-%m-%d %H:%M:%S")
        self.response_dic["data"]["cpp_settle_accounts_time"] = timezone_now_str
        self.response_dic["data"]["cpp_settle_accounts_time_timestamp"] = timezone_now.timestamp()
