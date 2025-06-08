import datetime as datetime_
import math
from collections import defaultdict

from django.db import models, transaction
from django.db.models import Count, Sum, Q, F
from django.db.models.query import QuerySet
from django.utils import timezone
from django.core.validators import MinValueValidator, validate_slug
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.functional import cached_property
from django.utils.html import strip_tags

from utils.common.expire_lru_cache import ExpireLruCache

from django.core.serializers.json import DjangoJSONEncoder



def _validate_handling_fee_ratio(value):
    if value <= 0 or value > 1:
        raise ValidationError("Handling fee ratio must be greater than 0 and less than or equal to 1!")

def _validate_customer_score_ratio(value):
    if value <= 0 or value > 1:
        raise ValidationError("Customer score ratio must be greater than 0 and less than or equal to 1!")

# Global Settings
class Settings(models.Model):
    company_name = models.CharField("Company Name", max_length=32)
    handling_fee_ratio = models.FloatField("Handling Fee Ratio (Ceil)", validators=[_validate_handling_fee_ratio, ])
    customer_score_ratio = models.FloatField("Customer Score Ratio (Ceil)", validators=[_validate_customer_score_ratio, ])

    class Meta:
        verbose_name = "Global Configuration"
        verbose_name_plural = verbose_name
        constraints = [
            models.CheckConstraint(
                check=Q(handling_fee_ratio__gt=0, handling_fee_ratio__lte=1), name="check_handling_fee_ratio"
            ),
            models.CheckConstraint(
                check=Q(customer_score_ratio__gt=0, customer_score_ratio__lte=1), name="check_customer_score_ratio"
            ),
        ]

    def save(self, *args, **kwargs):
        cls = self.__class__
        if cls.objects.exists():
            if cls.objects.count() != 1 or self.id != cls.objects.get().id:
                raise Exception("Only one configuration is allowed!")
        self.full_clean()
        super().save(*args, **kwargs)

def _get_global_settings() -> Settings:
    """ Return the global Settings object, create one if not exists """
    try:
        return Settings.objects.first()
    except Settings.DoesNotExist:
        settings_ = Settings(
            company_name="PP Logistics",
            handling_fee_ratio=0.002,  # 0.2%
            customer_score_ratio=1,    # 1 point per 1 yuan freight
        )
        settings_.save()
        return settings_

# Permission Group
class PermissionGroup(models.Model):
    name = models.CharField("Permission Group Name", max_length=64, unique=True, validators=[validate_slug, ])
    print_name = models.CharField("Print Permission Group Name", max_length=64)
    father = models.ForeignKey(
        "self", verbose_name="Parent Permission Group", on_delete=models.PROTECT, null=True, blank=True,
    )  # If Null, this is the top-level permission group

    class Meta:
        verbose_name = "Permission Group"
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        cls = self.__class__
        if (self.father is None
                and cls.objects.filter(father__isnull=True).exists()
                and self.id != cls.objects.get(father__isnull=True).id):
            raise Exception("Only one root permission group is allowed!")
        self.full_clean()
        super().save(*args, **kwargs)

    @cached_property
    def tree_str(self) -> str:
        return "%s %s" % (
            self.father.tree_str + " -" if self.father is not None else "",
            self.print_name,
        )

    tree_str.short_description = "Hierarchy"

    def __str__(self):
        return "%s (%s)" % (self.print_name, self.name)

# Permission
class Permission(models.Model):
    name = models.CharField("Permission Name", max_length=64, unique=True, validators=[validate_slug, ])
    print_name = models.CharField("Print Permission Name", max_length=64)
    father = models.ForeignKey(PermissionGroup, verbose_name="Parent Permission Group", on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Permission"
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @cached_property
    def tree_str(self) -> str:
        return "%s - %s" % (self.father.tree_str, self.print_name)

    tree_str.short_description = "Hierarchy"

    def __str__(self):
        return "%s (%s)" % (self.print_name, self.name)

# Department
class Department(models.Model):
    name = models.CharField("Department Name", max_length=32, unique=True)
    father_department = models.ForeignKey(
        "self", verbose_name="Parent Department", on_delete=models.SET_NULL, null=True, blank=True,
    )  # If Null, this is the top-level department
    unit_price = models.FloatField("Unit Price (Yuan/kg/m³)", validators=[MinValueValidator(0), ], db_index=True)
    enable_src = models.BooleanField("Allow Shipping", default=False)
    enable_dst = models.BooleanField("Allow Receiving", default=False)
    enable_cargo_price = models.BooleanField("Allow Collection", default=False)
    is_branch_group = models.BooleanField("Branch Group", default=False)

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = verbose_name

    def clean(self):
        if self.father_department is not None:
            if self.father_department.is_branch_group and self.is_branch_group:
                raise ValidationError("Departments under a branch group cannot be branch groups themselves")
            if not self.father_department.is_branch_group and self.unit_price != 0:
                raise ValidationError("Departments not under a branch group must have unit price 0")
            if self.father_department.is_branch_group and self.unit_price == 0:
                raise ValidationError("Departments under a branch group must have a unit price")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @cached_property
    def is_goods_yard(self) -> bool:
        """ Is this a goods yard """
        return self.name == "Goods Yard"

    @cached_property
    def is_branch(self) -> bool:
        """ Is this a branch """
        return self.father_department.is_branch_group if self.father_department else False

    is_branch.admin_order_field = "father_department"
    is_branch.boolean = True
    is_branch.short_description = "Branch"

    @classmethod
    def queryset_is_branch(cls):
        return cls.objects.filter(father_department__is_branch_group=True)

    @classmethod
    def queryset_is_goods_yard(cls):
        return cls.objects.filter(name="Goods Yard")

    @staticmethod
    @ExpireLruCache(expire_time=timezone.timedelta(minutes=5))
    def get_name_by_id(dept_id):
        """ Get department name by id """
        # Since User's __str__ method frequently needs department name, use a cached class method to reduce overhead
        return Department.objects.get(id=dept_id).name

    @cached_property
    def tree_str(self) -> str:
        return "%s %s" % (
            self.father_department.tree_str+" -" if self.father_department is not None else "",
            self.name,
        )

    tree_str.short_description = "Organization Structure"

    def __str__(self):
        return str(self.name)

# User
class User(models.Model):
    name = models.CharField("Username", max_length=32, unique=True)
    password = models.CharField("Password", max_length=128)
    enabled = models.BooleanField("Enabled", default=True, db_index=True)
    administrator = models.BooleanField("Administrator", default=False)
    department = models.ForeignKey(Department, verbose_name="Department", on_delete=models.PROTECT)
    create_time = models.DateTimeField("Created Time", auto_now_add=True)
    permission = models.ManyToManyField(Permission, verbose_name="Permissions")

    class Meta:
        verbose_name = "User"
        verbose_name_plural = verbose_name

    class Types(models.TextChoices):
        Administrator = "Administrator"
        Company = "Company"
        Branch = "Branch"
        GoodsYard = "Goods Yard"

    def save(self, *args, **kwargs):
        cls = self.__class__
        if not self.administrator:
            if not cls.objects.exists() or not cls.objects.filter(administrator=True).exclude(pk=self.pk).exists():
                raise ValueError("At least one administrator user is required!")
        self.full_clean()
        super().save(*args, **kwargs)

    def has_perm(self, perm_name: str) -> bool:
        """ Check if user has perm_name permission """
        return self.permission.filter(name=perm_name).exists()

    @cached_property
    def get_type(self) -> Types:
        """ Get user type """
        if self.administrator:
            return self.Types.Administrator
        is_goods_yard = self.department.is_goods_yard
        is_branch = self.department.is_branch
        assert not (is_goods_yard and is_branch), "Goods yard department should not have unit price"
        if is_goods_yard:
            return self.Types.GoodsYard
        if is_branch:
            return self.Types.Branch
        return self.Types.Company

    def __str__(self):
        return "%s (%s)%s" % (
            self.name, Department.get_name_by_id(self.department_id), " (Administrator)" if self.administrator else ""
        )

# Customer
class Customer(models.Model):
    name = models.CharField("Name", max_length=32, db_index=True)
    phone = models.CharField("Phone Number", max_length=16, unique=True)
    enabled = models.BooleanField("Enabled", default=True, db_index=True)
    bank_name = models.CharField("Bank Name", max_length=32)
    bank_number = models.CharField("Bank Card Number", max_length=32)
    credential_num = models.CharField("ID Number", max_length=32)
    address = models.CharField("Address", max_length=64, blank=True)
    is_vip = models.BooleanField("VIP", default=False, db_index=True)
    score = models.PositiveIntegerField("Score", default=0)
    create_time = models.DateTimeField("Created Time", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = verbose_name

    def __str__(self):
        return "%s (%s)%s" % (self.name, self.phone, " (VIP Customer)" if self.is_vip else "")

# Cargo Price Payment
class CargoPricePayment(models.Model):
    """
    Note: When updating the status field to "Paid" via update method, you must manually update the redundant field cargo_price_status in waybill_set.
    """

    class Statuses(models.IntegerChoices):
        Created = 0, "Created"
        Submitted = 1, "Submitted"
        Reviewed = 2, "Reviewed"
        Paid = 3, "Paid"
        Rejected = 4, "Rejected"

    create_time = models.DateTimeField("Created Time", auto_now_add=True, db_index=True)
    settle_accounts_time = models.DateTimeField("Settlement Time", null=True)
    create_user = models.ForeignKey(User, verbose_name="Creator", on_delete=models.PROTECT)
    payee_name = models.CharField("Payee Name", max_length=32)
    payee_phone = models.CharField("Payee Phone Number", max_length=16)
    payee_bank_name = models.CharField("Payee Bank Name", max_length=32)
    payee_bank_number = models.CharField("Payee Bank Card Number", max_length=32)
    payee_credential_num = models.CharField("Payee ID Number", max_length=32)
    remark = models.CharField("Remark", max_length=256, blank=True)
    reject_reason = models.CharField("Rejection Reason", max_length=256, blank=True)
    status = models.SmallIntegerField(
        "Status", choices=Statuses.choices, default=Statuses.Created.value, db_index=True
    )

    class Meta:
        verbose_name = "Cargo Price Payment"
        verbose_name_plural = verbose_name

    def gen_total_fee(self) -> dict:
        """ Calculate payable amounts """
        total_cargo_price = self.waybill_set.only("cargo_price").aggregate(_=models.Sum("cargo_price"))["_"]
        total_deduction_fee = self.waybill_set.only("fee").filter(
                fee_type=Waybill.FeeTypes.Deduction
            ).aggregate(_=models.Sum("fee"))["_"]
        total_cargo_handling_fee = self.waybill_set.only(
                "cargo_handling_fee"
            ).aggregate(_=models.Sum("cargo_handling_fee"))["_"]
        return {
            "cargo_price": total_cargo_price or 0,
            "deduction_fee": total_deduction_fee or 0,
            "cargo_handling_fee": total_cargo_handling_fee or 0,
        }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # When saving, if payment is paid, update redundant field cargo_price_status for related waybills
        if self.status == self.Statuses.Paid:
            with transaction.atomic():
                self.waybill_set.update(cargo_price_status=Waybill.CargoPriceStatuses.Paid)

    @cached_property
    def get_full_id(self) -> str:
        return "".join([
            self.create_time.strftime("%Y%m%d"),
            str(self.create_user_id).zfill(3),
            str(self.id).zfill(3)[-3:],
        ])

# Waybill
class Waybill(models.Model):
    """
    Note: When updating cargo_price or cargo_price_payment fields via update method, you must manually update the redundant field cargo_price_status as needed.
    """

    class Statuses(models.IntegerChoices):
        Created = 0, "Created"
        Loaded = 1, "Loaded"
        Departed = 2, "Departed"
        GoodsYardArrived = 3, "Arrived at Goods Yard"
        GoodsYardLoaded = 4, "Loaded at Goods Yard"
        GoodsYardDeparted = 5, "Departed from Goods Yard"
        Arrived = 6, "Arrived at Station"
        SignedFor = 7, "Signed by Customer"
        Returned = 8, "Returned"
        Dropped = 9, "Voided"

    class FeeTypes(models.IntegerChoices):
        SignFor = 0, "Pay on Delivery"
        Now = 1, "Pay Now"
        Deduction = 2, "Deducted"

    class CargoPriceStatuses(models.IntegerChoices):
        No = 0, "No Collection"
        NotPaid = 1, "Not Paid"
        Paid = 2, "Paid"

    create_time = models.DateTimeField("Created Date", auto_now_add=True, db_index=True)
    # arrival_time and sign_for_time are essentially redundant fields, as these times can be queried from WaybillRouting
    arrival_time = models.DateTimeField("Arrival Date", null=True, blank=True, db_index=True)
    sign_for_time = models.DateTimeField("Pickup Date", null=True, blank=True, db_index=True)
    src_department = models.ForeignKey(
        Department, verbose_name="Shipping Department", on_delete=models.PROTECT, related_name="wb_src_department"
    )
    dst_department = models.ForeignKey(
        Department, verbose_name="Receiving Department", on_delete=models.PROTECT, related_name="wb_dst_department"
    )

    src_customer = models.ForeignKey(
        Customer, verbose_name="Sender", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="src_customer"
    )
    src_customer_name = models.CharField("Sender Name", max_length=32)
    src_customer_phone = models.CharField("Sender Phone", max_length=16)
    src_customer_credential_num = models.CharField("Sender ID Number", max_length=32, blank=True)
    src_customer_address = models.CharField("Sender Address", max_length=64, blank=True)
    dst_customer = models.ForeignKey(
        Customer, verbose_name="Receiver", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="dst_customer"
    )
    dst_customer_name = models.CharField("Receiver Name", max_length=32)
    dst_customer_phone = models.CharField("Receiver Phone", max_length=16)
    dst_customer_credential_num = models.CharField("Receiver ID Number", max_length=32, blank=True)
    dst_customer_address = models.CharField("Receiver Address", max_length=64, blank=True)

    cargo_name = models.CharField("Cargo Name", max_length=16)
    cargo_num = models.PositiveIntegerField("Quantity", validators=[MinValueValidator(1), ])
    cargo_volume = models.FloatField("Volume", validators=[MinValueValidator(0.01), ])
    cargo_weight = models.FloatField("Weight", validators=[MinValueValidator(0.1), ])
    cargo_price = models.PositiveIntegerField("Cargo Price", default=0)
    cargo_handling_fee = models.PositiveIntegerField("Handling Fee", default=0)

    fee = models.PositiveIntegerField("Freight", validators=[MinValueValidator(1), ])
    fee_type = models.SmallIntegerField("Freight Type", choices=FeeTypes.choices, db_index=True)

    customer_remark = models.CharField("Customer Remark", max_length=64, blank=True)
    company_remark = models.CharField("Company Remark", max_length=64, blank=True)

    sign_for_customer_name = models.CharField("Recipient Name", max_length=32, blank=True)
    sign_for_customer_credential_num = models.CharField("Recipient ID Number", max_length=32, blank=True)

    status = models.SmallIntegerField(
        "Status", default=Statuses.Created.value, choices=Statuses.choices, db_index=True
    )
    drop_reason = models.CharField("Void Reason", max_length=64, blank=True)
    # return_waybill is not NULL means this waybill is a return waybill for another waybill (return_waybill)
    return_waybill = models.OneToOneField(
        "self", verbose_name="Original Return Waybill", on_delete=models.SET_NULL, null=True, blank=True
    )
    # One waybill can only correspond to one cargo price payment, one payment can include multiple waybills
    cargo_price_payment = models.ForeignKey(
        CargoPricePayment, verbose_name="Cargo Price Payment", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Denormalized field: redundant
    cargo_price_status = models.SmallIntegerField("Cargo Price Status", choices=CargoPriceStatuses.choices, db_index=True)

    class Meta:
        verbose_name = "Waybill"
        verbose_name_plural = verbose_name

    def clean(self):
        custom_validators = [
            # Shipping/Receiving departments must have shipping/receiving permissions
            (self.src_department.enable_src, "Shipping department does not have shipping permission"),
            (self.dst_department.enable_dst, "Receiving department does not have receiving permission"),
            # Shipping and receiving departments cannot be the same
            (self.src_department != self.dst_department, "Shipping and receiving departments cannot be the same"),
            # If sender/receiver is filled, the customer must be enabled
            (self.src_customer.enabled if self.src_customer else True, "Sender is not enabled"),
            (self.dst_customer.enabled if self.dst_customer else True, "Receiver is not enabled"),
            # If using deduction, receiving department must allow collection, and freight cannot exceed cargo price
            (
                (
                    self.dst_department.enable_cargo_price
                    if self.fee_type == self.FeeTypes.Deduction else True
                ),
                "Receiving department does not allow collection"
            ),
            (
                (
                    self.fee <= self.cargo_price
                    if self.fee_type == self.FeeTypes.Deduction else True
                ),
                "Deducted freight cannot exceed cargo price"
            ),
            (self.return_waybill != self, "A waybill cannot be its own return waybill"),
        ]
        for validator, error_text in custom_validators:
            if not validator:
                raise ValidationError(error_text)

    def save(self, *args, **kwargs):
        # Update redundant field cargo_price_status when saving
        if self.cargo_price:
            if self.cargo_price_payment and (self.cargo_price_payment.status == CargoPricePayment.Statuses.Paid):
                self.cargo_price_status = self.CargoPriceStatuses.Paid
            else:
                self.cargo_price_status = self.CargoPriceStatuses.NotPaid
        else:
            self.cargo_price_status = self.CargoPriceStatuses.No
        self.full_clean()
        super().save(*args, **kwargs)

    @cached_property
    def get_full_id(self) -> str:
        if self.return_waybill:
            return "YF" + str(self.return_waybill_id).zfill(8)
        return str(self.id).zfill(8)

    get_full_id.admin_order_field = "pk"
    get_full_id.short_description = "Waybill Number"

    def __str__(self):
        return self.get_full_id

# Truck
class Truck(models.Model):
    number_plate = models.CharField("License Plate", max_length=8, unique=True)
    driver_name = models.CharField("Driver Name", max_length=32)
    driver_phone = models.CharField("Driver Phone Number", max_length=16)
    enabled = models.BooleanField("Enabled", default=True, db_index=True)
    create_time = models.DateTimeField("Created Time", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Truck"
        verbose_name_plural = verbose_name

    def __str__(self):
        return str(self.number_plate)

# Transport Out (Trip)
class TransportOut(models.Model):

    class Statuses(models.IntegerChoices):
        Ready = 0, "Cargo Loaded"
        OnTheWay = 1, "On the Way"
        Arrived = 2, "Arrived"

    truck = models.ForeignKey(Truck, verbose_name="Truck", on_delete=models.PROTECT)
    driver_name = models.CharField("Driver Name", max_length=32)
    driver_phone = models.CharField("Driver Phone Number", max_length=16)
    create_time = models.DateTimeField("Created Time", auto_now_add=True, db_index=True)
    start_time = models.DateTimeField("Departure Time", null=True, db_index=True)
    end_time = models.DateTimeField("Arrival Time", null=True)
    src_department = models.ForeignKey(
        Department, verbose_name="Departure Department", on_delete=models.PROTECT, related_name="tn_src_department"
    )
    dst_department = models.ForeignKey(
        Department, verbose_name="Arrival Department", on_delete=models.PROTECT, related_name="tn_dst_department"
    )
    waybills = models.ManyToManyField(Waybill, verbose_name="Loaded Waybills")
    status = models.SmallIntegerField(
        "Status", choices=Statuses.choices, default=Statuses.Ready.value, db_index=True
    )

    class Meta:
        verbose_name = "Trip"
        verbose_name_plural = verbose_name

    def __str__(self):
        return "%s (%s)" % (self.get_full_id, self.get_status_display())

    @cached_property
    def get_full_id(self) -> str:
        return "SN" + str(self.id).zfill(8)

    get_full_id.admin_order_field = "pk"
    get_full_id.short_description = "Trip Number"

    def gen_waybills_info(self):
        """ Statistics for loaded waybills (count, quantity, total volume, total weight) """
        return self.waybills.only(*"pk cargo_num cargo_volume cargo_weight".split()).aggregate(
            total_num=Count("pk"),
            total_cargo_num=Sum("cargo_num"),
            total_cargo_volume=Sum("cargo_volume"),
            total_cargo_weight=Sum("cargo_weight"),
        )

# Waybill Routing
class WaybillRouting(models.Model):
    waybill = models.ForeignKey(Waybill, verbose_name="Waybill", on_delete=models.PROTECT)
    time = models.DateTimeField("Operation Time")
    operation_type = models.SmallIntegerField("Operation Type", choices=Waybill.Statuses.choices)
    operation_dept = models.ForeignKey(Department, verbose_name="Operation Department", on_delete=models.PROTECT)
    operation_user = models.ForeignKey(User, verbose_name="Operation User", on_delete=models.PROTECT)
    operation_info = models.JSONField("Details", encoder=DjangoJSONEncoder, default=dict)

    class Meta:
        verbose_name = "Waybill Routing"
        verbose_name_plural = verbose_name

    def __str__(self):
        return "%s (%s)" % (
            self.waybill.get_full_id, self.get_operation_type_display()
        )

    def _template_context(self) -> dict:
        wr_transport_out = None
        wr_return_waybill = None
        if self.operation_type in (Waybill.Statuses.GoodsYardDeparted, Waybill.Statuses.Departed):
            wr_transport_out_id = self.operation_info.get("transport_out_id")
            if wr_transport_out_id:
                wr_transport_out = TransportOut.objects.get(id=wr_transport_out_id)
        elif self.operation_type == Waybill.Statuses.Returned:
            wr_return_waybill_id = self.operation_info.get("return_waybill_id")
            if wr_return_waybill_id:
                wr_return_waybill = Waybill.objects.get(id=wr_return_waybill_id)
        return {
            "wr": self,
            "WB_STATUSES": Waybill.Statuses,
            "transport_out": wr_transport_out,
            "return_waybill": wr_return_waybill,
        }

    def gen_print_operation_info(self) -> str:
        """ Generate detailed text for waybill routing """
        operation_info_string = render_to_string(
            "wuliu/_inclusions/_waybill_routing_operation_info.html",
            self._template_context(),
        )
        return operation_info_string.strip()

    def gen_print_operation_info_text(self) -> str:
        """ Generate detailed text for waybill routing (remove html tags) """
        return strip_tags(self.gen_print_operation_info())

# Department Payment
class DepartmentPayment(models.Model):

    class Statuses(models.IntegerChoices):
        Created = 0, "Created"
        Reviewed = 1, "Reviewed"
        Paid = 2, "Paid"
        Settled = 3, "Settled"

    create_time = models.DateTimeField("Created Time", auto_now_add=True)
    payment_date = models.DateField("Payment Due Date")
    settle_accounts_time = models.DateTimeField("Settlement Time", null=True)
    waybills = models.ManyToManyField(Waybill, verbose_name="Waybills")
    src_department = models.ForeignKey(
        Department, verbose_name="Payment Department",
        on_delete=models.PROTECT, related_name="pm_src_department",
    )
    dst_department = models.ForeignKey(
        Department, verbose_name="Receiving Department",
        on_delete=models.PROTECT, related_name="pm_dst_department",
    )
    status = models.SmallIntegerField(
        "Status", choices=Statuses.choices, default=Statuses.Created.value, db_index=True
    )
    src_remark = models.CharField("Payment Department Remark", max_length=256, blank=True)
    dst_remark = models.CharField("Receiving Department Remark", max_length=256, blank=True)

    class Meta:
        verbose_name = "Department Payment"
        verbose_name_plural = verbose_name

    @staticmethod
    def static_gen_waybills(src_department: Department, payment_date: datetime_.date) -> set:
        """ Generate set of waybill ids by payment department and payment date """

        def _date_to_datetime_start(_date):
            return timezone.make_aware(timezone.datetime.combine(_date, datetime_.time()))

        def _date_to_datetime_end(_date):
            return timezone.make_aware(timezone.datetime.combine(_date, datetime_.time(23, 59, 59)))

        transport_out_src = TransportOut.objects.filter(
            src_department=src_department,
            status__gte=TransportOut.Statuses.OnTheWay,
            start_time__gte=_date_to_datetime_start(payment_date),
            start_time__lte=_date_to_datetime_end(payment_date),
        )
        # Waybills shipped on the day (pay now)
        waybills_src = [
            wb_id
            for to_obj in transport_out_src
            for wb_id in to_obj.waybills.filter(fee_type=Waybill.FeeTypes.Now).values_list("id", flat=True)
        ]
        # Waybills signed for on the day
        waybills_dst = list(
            Waybill.objects.filter(
                dst_department=src_department,
                status=Waybill.Statuses.SignedFor,
                sign_for_time__gte=_date_to_datetime_start(payment_date),
                sign_for_time__lte=_date_to_datetime_end(payment_date),
            ).values_list("id", flat=True)
        )
        return set(waybills_src + waybills_dst)

    def set_waybills_auto(self):
        """ Set related waybills """
        with transaction.atomic():
            self.waybills.set(self.static_gen_waybills(self.src_department, self.payment_date))

    @staticmethod
    def static_gen_total_fee(waybills, src_department: Department) -> dict:
        """ Calculate payable amounts """
        if not isinstance(waybills, QuerySet):
            waybills = Waybill.objects.filter(id__in=waybills)
        # Shipping waybills: pay now
        fee_now = waybills.only("fee").filter(
                src_department=src_department, fee_type=Waybill.FeeTypes.Now,
            ).aggregate(_=models.Sum("fee"))["_"]
        # Signed waybills: pay on delivery
        fee_sign_for = waybills.only("fee").filter(
                dst_department=src_department, fee_type=Waybill.FeeTypes.SignFor,
            ).aggregate(_=models.Sum("fee"))["_"]
        # Signed waybills: cargo price
        cargo_price = waybills.only("cargo_price").filter(
                dst_department=src_department
            ).aggregate(_=models.Sum("cargo_price"))["_"]
        return {
            "fee_now": fee_now or 0,
            "fee_sign_for": fee_sign_for or 0,
            "cargo_price": cargo_price or 0,
        }

    def gen_total_fee(self) -> dict:
        """ Calculate payable amounts """
        return self.static_gen_total_fee(self.waybills.all(), self.src_department)

    def gen_customer_score_change(self) -> list:
        """ Calculate customer score changes """
        customer_score_ratio = _get_global_settings().customer_score_ratio
        customer_score_change = []
        filtered_waybills_info = self.waybills.filter(src_customer__is_vip=True).values(
            "src_department_id", "dst_department_id", "src_customer_id", "id", "fee", "fee_type",
        )
        for waybill_info in filtered_waybills_info:
            fee_type = waybill_info["fee_type"]
            # Pay now: payment department should match shipping department
            # Pay on delivery or deduction: payment department should match receiving department
            if any([
                fee_type == Waybill.FeeTypes.Now and self.src_department_id == waybill_info["src_department_id"],
                fee_type in (Waybill.FeeTypes.Deduction, Waybill.FeeTypes.SignFor) and (
                    self.src_department_id == waybill_info["dst_department_id"]
                ),
            ]):
                customer_score_change.append({
                    "customer_id": waybill_info["src_customer_id"],
                    "waybill_id": waybill_info["id"],
                    "add_score": math.ceil(waybill_info["fee"] * customer_score_ratio),
                })
        return customer_score_change

    def update_customer_score_change(self):
        """ Update customer score changes """
        customer_score_changes = self.gen_customer_score_change()
        # Calculate total score increase per customer
        customer_add_score_total = defaultdict(int)
        for change in customer_score_changes:
            customer_add_score_total[change["customer_id"]] += change["add_score"]
        with transaction.atomic():
            CustomerScoreLog.objects.bulk_create([
                CustomerScoreLog(
                    customer_id=change["customer_id"],
                    inc_or_dec=True,
                    score=change["add_score"],
                    remark="Waybill Settlement",
                    waybill=Waybill.objects.get(id=change["waybill_id"])
                )
                for change in customer_score_changes
            ])
            for customer_id, add_score_total in customer_add_score_total.items():
                customer = Customer.objects.get(id=customer_id)
                customer.score = F("score") + add_score_total
                customer.save(update_fields=["score", ])

    @cached_property
    def get_full_id(self) -> str:
        return "".join([
            self.payment_date.strftime("%Y%m%d"),
            str(self.src_department_id).zfill(3),
            str(self.dst_department_id).zfill(3),
        ])

    def save(self, *args, **kwargs):
        # self.full_clean()
        super().save(*args, **kwargs)
        if self.status == DepartmentPayment.Statuses.Settled:
            self.update_customer_score_change()

    def __str__(self):
        return "%s (%s -> %s)" % (
            self.get_full_id, self.src_department.name, self.dst_department.name
        )

# Customer Score Log
class CustomerScoreLog(models.Model):
    create_time = models.DateTimeField("Change Time", auto_now_add=True, db_index=True)
    customer = models.ForeignKey(Customer, verbose_name="Customer", on_delete=models.PROTECT)
    inc_or_dec = models.BooleanField("Increase or Decrease")
    score = models.PositiveIntegerField("Score Change", validators=[MinValueValidator(1), ])
    remark = models.CharField("Change Reason", max_length=256)
    # Each waybill should only correspond to one customer score increase record
    waybill = models.OneToOneField(Waybill, verbose_name="Related Waybill", on_delete=models.PROTECT, null=True)
    user = models.ForeignKey(User, verbose_name="Operator", on_delete=models.PROTECT, null=True)

    class Meta:
        verbose_name = "Customer Score Log"
        verbose_name_plural = verbose_name
        constraints = [
            models.CheckConstraint(check=Q(score__gte=1), name="check_change_score"),
        ]
