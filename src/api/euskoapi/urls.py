""" euskalmoneta API URL Configuration """

from rest_framework import routers

from members.views import MembersAPIView

router = routers.SimpleRouter()
router.register(r'members', MembersAPIView, base_name='members')

urlpatterns = []

urlpatterns += router.urls
