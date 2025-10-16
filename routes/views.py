from django.shortcuts import render, redirect
from django.urls import reverse
from .models import Airport, Route
from .forms import AirportForm, RouteForm, CombinedAirportRouteForm, NthNodeSearchForm

def home(request):
    airports = Airport.objects.all().order_by('code')
    routes = Route.objects.select_related('source', 'destination').all()
    return render(request, 'home.html', {
        'airports': airports,
        'routes': routes,
    })


def add_airport(request):
    return redirect(reverse('add_airport_and_route'))


def add_route(request):
    return redirect(reverse('add_airport_and_route'))


def add_airport_and_route(request):
    if request.method == 'POST':
        form = CombinedAirportRouteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('home'))
    else:
        form = CombinedAirportRouteForm()
    return render(request, 'add_airport_and_route.html', {'form': form})


def search_nodes(request):
    context = { 'form': None, 'data': None, 'errors': None }
    if request.method == 'POST':
        form = NthNodeSearchForm(request.POST)
        if form.is_valid():
            try:
                data = form.perform()
                context['data'] = data
            except Exception as e:
                form.add_error(None, str(e))
        context['form'] = form
    else:
        context['form'] = NthNodeSearchForm()
    return render(request, 'search_nodes.html', context)
