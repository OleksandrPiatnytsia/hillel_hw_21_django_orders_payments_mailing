from django.contrib.auth.management import create_permissions
from django.db import migrations

# What the "Managers" group gets in the admin, by app label.
# Kept here, not imported from app code: a migration must keep working
# the same way even if the app code changes later.
MANAGER_PERMISSIONS = {
    "orders": [
        "view_order",
        # Status, delivery data and the "Cancel selected orders" action
        # (OrderAdmin.cancel_selected has permissions=["change"])
        "change_order",
        # Items are shown on the order page (OrderItemInline, view only)
        "view_orderitem",
    ],
    "payments": [
        # Payments list and the payments of an order (view only)
        "view_payment",
        # "Add a manual payment" rows on the order page (ManualPaymentInline)
        "add_payment",
    ],
}
# Not given: add_order / delete_order (orders come only from checkout and
# are cancelled, not deleted; OrderAdmin forbids both anyway),
# change_payment / delete_payment (payments are changed only by
# payments.services). Customers get nothing: they see their own orders on
# the site, not in the admin.

GROUP = "Managers"


def _permissions(apps):
    Permission = apps.get_model("auth", "Permission")
    for app_label, codenames in MANAGER_PERMISSIONS.items():
        permissions = Permission.objects.filter(
            content_type__app_label=app_label, codename__in=codenames
        )
        # Fail loudly on a typo instead of giving fewer rights
        missing = set(codenames) - set(permissions.values_list("codename", flat=True))
        if missing:
            raise RuntimeError(f"Unknown permissions in {app_label}: {sorted(missing)}")
        yield from permissions


def add_permissions(apps, schema_editor):
    # Permissions are normally created by the post_migrate signal — AFTER
    # all migrations. On a fresh database they don't exist yet, so create
    # them now (the same trick as in users/0003_create_groups.py).
    for app_label in MANAGER_PERMISSIONS:
        app_config = apps.get_app_config(app_label)
        app_config.models_module = True  # create_permissions() skips apps without it
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    # get_or_create: the group comes from users/0003, but don't depend on it
    group, _ = Group.objects.get_or_create(name=GROUP)
    # add(), not set(): keep the catalog permissions the group already has
    group.permissions.add(*_permissions(apps))


def remove_permissions(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    group = Group.objects.filter(name=GROUP).first()
    if group is not None:
        group.permissions.remove(*_permissions(apps))


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
        ("payments", "0001_initial"),
        ("users", "0003_create_groups"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(add_permissions, remove_permissions),
    ]
