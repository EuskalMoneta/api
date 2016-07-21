from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def home(request):
    # homepage for bureauchange app
    return render(request, 'home.html')
