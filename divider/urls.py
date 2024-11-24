
from django.urls import path
from .views import DividerPDFView

# Create your views here.
urlpatterns = [
    path('divide-pdf/', DividerPDFView.as_view(), name='divide_pdf'),
]