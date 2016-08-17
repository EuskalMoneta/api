from django.shortcuts import render


def index(request):
    return render(request, 'members/list.html')


def add(request):
    return render(request, 'members/add.html')


def search(request):
    return render(request, 'members/search.html')


def add_subscription(request, member_id):
    return render(request, 'members/add_subscription.html', {'member_id': member_id})
