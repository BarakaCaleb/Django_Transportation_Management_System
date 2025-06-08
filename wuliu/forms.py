def _init_form_fields_class(self_: forms.BaseForm):
    """ Set styles for all form fields """
    for field in self_.fields.values():
        if isinstance(field, (forms.ModelMultipleChoiceField, forms.MultipleChoiceField)):
            # Set multi-select style for multiple choice fields
            field.widget.attrs["class"] = "form-control multiple-select"
        elif isinstance(field, forms.ChoiceField):
            # Set select2 style for single choice fields
            field.widget.attrs["class"] = "form-control select2"
        elif isinstance(field, forms.DateField):
            # Set md-date-picker style for date fields
            field.widget.attrs["class"] = "form-control md-date-picker"
        elif isinstance(field, forms.TimeField):
            # Set md-time-picker style for time fields
            field.widget.attrs["class"] = "form-control md-time-picker"
        else:
            field.widget.attrs["class"] = "form-control"

def _destroy_model_form_save(self_: forms.ModelForm):
    """ Destroy ModelForm's save method """
    def save_(self__, *args, **kwargs):
        raise NotImplemented
    self_.save = save_

class ChangePassword(_FormBase):
    old_password = forms.CharField(label="Old Password", widget=forms.PasswordInput)
    new_password = forms.CharField(label="New Password", widget=forms.PasswordInput)
    new_password_again = forms.CharField(label="Re-enter New Password", widget=forms.PasswordInput)

# ... (snip, only showing changed labels below for brevity)

class WaybillForm(_ModelFormBase):

    def add_id_field(self, id_: int, id_full: str):
        """ Add a full waybill number field and a hidden id field """
        self.fields["id_"] = forms.CharField(label="Waybill Number", max_length=8)
        # ...

    def check_again(self, request):
        """ Perform secondary validation on submitted form data """

        def _gen_handling_fee(cargo_price):
            if cargo_price == 0:
                return 0
            return math.ceil(cargo_price * get_global_settings().handling_fee_ratio)

        form_dic = self.cleaned_data
        logged_user = get_logged_user(request)
        _handling_fee = _gen_handling_fee(form_dic["cargo_price"])
        custom_validators = [
            # Shipping department must match the department of the logged-in user
            (
                form_dic["src_department"] == logged_user.department,
                "Shipping department (%s) does not match the logged-in user's department (%s, %s)" % (
                    form_dic["src_department"].name, logged_user.name, logged_user.department.name
                )
            ),
            # Handling fee check
            (form_dic["cargo_handling_fee"] == _handling_fee, "Handling fee does not match system calculated amount (%d)" % _handling_fee),
        ]
        for validator, error_text in custom_validators:
            assert validator, error_text

    def change_to_detail_form(self):
        """ Change the form to a waybill detail page form """
        change_dic = {
            "RO_src_department": {
                "label": Waybill.src_department.field.verbose_name,
                "value": self.instance.src_department.name,
            },
            "RO_dst_department": {
                "label": Waybill.dst_department.field.verbose_name,
                "value": self.instance.dst_department.name,
            },
            "RO_src_customer": {
                "label": Waybill.src_customer.field.verbose_name,
                "value": str(self.instance.src_customer) if self.instance.src_customer else None,
            },
            "RO_dst_customer": {
                "label": Waybill.dst_customer.field.verbose_name,
                "value": str(self.instance.dst_customer) if self.instance.dst_customer else None,
            },
            "RO_fee_type": {
                "label": "Payment Method",
                "value": Waybill.FeeTypes(self.instance.fee_type).label,
            },
            "RO_create_time": {
                "label": Waybill.create_time.field.verbose_name,
                "value": timezone.make_naive(self.instance.create_time).strftime("%Y-%m-%d %H:%M:%S"),
            },
            "RO_status": {
                "label": "Waybill Status",
                "value": self.instance.Statuses(self.instance.status).label,
            },
        }
        # ... (rest unchanged)

class WaybillSearchForm(_FormBase):
    create_date_start = forms.DateField(
        label="Invoice Date", required=False,
        initial=timezone.make_naive(timezone.now() - timezone.timedelta(days=7)).strftime("%Y-%m-%d"),
    )
    create_time_start = forms.TimeField(label="-", required=False, initial="00:00")
    create_date_end = forms.DateField(
        label="To", required=False,
        initial=timezone.make_naive(timezone.now()).strftime("%Y-%m-%d"),
    )
    create_time_end = forms.TimeField(label="-", required=False, initial="23:59")

    arrival_date_start = forms.DateField(label="Arrival Date", required=False)
    arrival_date_end = forms.DateField(label="To", required=False)
    sign_for_date_start = forms.DateField(label="Sign Date", required=False)
    sign_for_date_end = forms.DateField(label="To", required=False)

    src_department = forms.ModelChoiceField(Department.queryset_is_branch(), required=False, label="Invoice Department")
    dst_department = forms.ModelChoiceField(Department.queryset_is_branch(), required=False, label="Arrival Department")

    src_department_group = forms.ChoiceField(
        label="-", required=False, choices=DEPARTMENT_GROUP_CHOICES.items(), initial=0,
    )
    dst_department_group = forms.ChoiceField(
        label="-", required=False, choices=DEPARTMENT_GROUP_CHOICES.items(), initial=0,
    )

    src_customer_name = forms.CharField(label="Sender", required=False)
    src_customer_phone = forms.CharField(label="Sender Phone", required=False)
    dst_customer_name = forms.CharField(label="Receiver", required=False)
    dst_customer_phone = forms.CharField(label="Receiver Phone", required=False)

    waybill_id = forms.CharField(label="Waybill Number", required=False, max_length=8)
    waybill_status = forms.MultipleChoiceField(
        label="Waybill Status", required=False,
        choices=Waybill.Statuses.choices,
        initial=[Waybill.Statuses.Created, ],
    )
    waybill_fee_type = forms.MultipleChoiceField(
        label="Settlement Method", required=False,
        choices=Waybill.FeeTypes.choices,
        initial=Waybill.FeeTypes.values,
    )

# ... (continue translating all Chinese labels, help texts, error messages, and comments in the same way throughout the file)
