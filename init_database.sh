#!/usr/bin/sh

# Test data account passwords are as follows:

# Username      Password    User Type
# csshd         666666      Receiving Point
# csfgs         666666      Branch Company (Arrival Point)
# kj_1          666666      Accountant (Finance Department)
# zxg_1         666666      Cargo Handler 1 (Platform)
# zxg_2         666666      Cargo Handler 2 (Platform)
# pzqqt         88888888    Administrator

set -e

# Temporarily modify some code in the project
# This is a necessary step before database migration
# Otherwise, you will be prompted that some tables do not exist
cat <<EOF | git apply
diff --git a/wuliu/common.py b/wuliu/common.py
index f29db03..56fa551 100644
--- a/wuliu/common.py
+++ b/wuliu/common.py
@@ -46,7 +46,7 @@ def is_logged_user_is_goods_yard(request) -> bool:
     """ Determine whether the logged-in user belongs to the goods yard """
     return get_logged_user_type(request) == User.Types.GoodsYard
 
-def _gen_permission_tree_list(root_pg_=PermissionGroup.objects.get(father__isnull=True)) -> list:
+def _gen_permission_tree_list(root_pg_) -> list:
     """ Generate a list based on the hierarchical structure of all permission groups and permissions, for front-end rendering """
     tree_list = []
     for pg in PermissionGroup.objects.filter(father=root_pg_):
@@ -59,7 +59,7 @@ def _gen_permission_tree_list(root_pg_=PermissionGroup.objects.get(father__isnul
         })
     return tree_list
 
-PERMISSION_TREE_LIST = _gen_permission_tree_list()
+PERMISSION_TREE_LIST = []
 
 def login_required(raise_404=False):
     """ Custom decorator for decorating route methods
diff --git a/wuliu/urls.py b/wuliu/urls.py
index 92406c3..8c5aa12 100644
--- a/wuliu/urls.py
+++ b/wuliu/urls.py
@@ -1,6 +1,5 @@
 from django.urls import path, include
 
-from . import views, apis
 
 # Unused
 def easy_path(view_func):
@@ -8,6 +7,8 @@ def easy_path(view_func):
     return path(view_func.__name__, view_func, name=view_func.__name__)
 
 app_name = "wuliu"
+urlpatterns = []
+'''
 urlpatterns = [
     # Login
     path("login", views.login, name="login"),
@@ -136,3 +137,4 @@ urlpatterns = [
         ])),
     ])),
 ]
+'''
EOF

# Perform database migration
python3 ./manage.py migrate
# Start importing test data
python3 ./manage.py loaddata init_data.json

# Restore files in the wuliu directory to their original state
git checkout -- ./wuliu

echo "Done!"

