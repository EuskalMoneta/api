from django.shortcuts import render

from members.forms import MemberForm


def index(request):
    return render(request, 'members/list.html')


def add(request):
    return render(request, 'members/add.html', {'form': MemberForm()})
