from django.urls import path
from market import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/prices/", views.MarketTickListView.as_view(), name="api_prices_list"),
    path("api/prices/<str:symbol>/", views.MarketTickDetailView.as_view(), name="api_prices_detail"),
    path("api/status/", views.EngineStatusView.as_view(), name="api_status"),
]
