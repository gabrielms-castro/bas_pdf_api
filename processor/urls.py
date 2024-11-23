from django.urls import path
from .views import ProcessarPDFView

urlpatterns = [
    path('pdf-processor/', ProcessarPDFView.as_view(), name='pdf-processor'),
]