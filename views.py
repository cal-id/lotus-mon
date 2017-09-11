from django.shortcuts import render, get_object_or_404
from monitor.mon import runThroughCrash
from .models import CrashEvent, User, Host, Command, Queue
from django.db.models import Count
import csv  # for parsing lsf data
# Create your views here.


def baseContext():
    'Returns the base content required for all pages (for nav bar)'
    def getUsefulData(event):
        return (event.host, event.date, event.id)
    return {
        "latestCrashes": [getUsefulData(event) for event in
                          CrashEvent.objects.order_by("-date")[0:5]]
    }


def index(request):
    '''Renders the base index page, including calling baseContext for the base
    page which this page extends'''
    context = baseContext()
    context['crashesByDate'] = CrashEvent.objects.order_by('-date')
    # order the rest of the data by counting the associated crashes using
    # the C annotation and then ordering in reverse and removing the 0s
    hostData = [(host.crashevent_set.order_by("-date"), host.address, False)
                for host in Host.objects.annotate(C=Count("crashevent"))
                                        .order_by('-C').filter(C__gt=0)]
    userData = [(user.crashes.order_by("-date"), user.name, False)
                for user in User.objects.annotate(C=Count("crashes"))
                                .order_by('-C').filter(C__gt=0)]
    commandData = [(cmd.crashes.order_by("-date"), cmd.shortText(),
                    cmd.parsedLinesOfText())
                   for cmd in Command.objects.annotate(C=Count("crashes"))
                                     .order_by('-C').filter(C__gt=0)]
    queueData = [(que.crashes.order_by("-date"), que.name, False)
                 for que in Queue.objects.annotate(C=Count("crashes"))
                                 .order_by("-C").filter(C__gt=0)]
    context['listByThis'] = [("User", userData, 4), ("Hostname", hostData, 4),
                             ("Command", commandData, 12),
                             ("Queue", queueData, 4)]
    return render(request, 'monitor/index.html', context)


def registerCrash(request, host=False):
    'Sets up and renders the view after trying to register a crash via http'
    # host should always be passed in, regardless of the url
    assert host is not False
    worked = True
    try:
        runThroughCrash(host)
    except BaseException as e:
        worked = False
    context = baseContext()
    context["worked"] = worked
    context["host"] = host
    return render(request, "monitor/registerCrashTemplate.html", context)


def detailOfCrash(request, i=False):
    '''Gets the information from and renders the page to do with a specific
    crash id which is passed in via the url as the i argument'''
    assert i is not False
    crash = get_object_or_404(CrashEvent, id=i)
    context = baseContext()
    context["crash"] = crash
    context["ganglias"] = crash.gangliagraph_set.all()
    # This try, except is required to force the file not to open in binary mode
    try:
        # change from the default of 'rb'
        crash.lsfData.read()
        crash.lsfData.close()
        crash.lsfData.open(mode="r")
        crash.lsfData.seek(0)
    except ValueError as e:
        # if there is a value error then there is no lsf data for this class
        context["noLsfData"] = True
    else:
        context["noLsfData"] = False
        # get csv to parse the rows
        rows = [[element for element in row]
                for row in csv.reader(crash.lsfData)]
        crash.lsfData.close()
        context["lsfHeaders"] = rows[0]
        context["lsfRows"] = rows[1:]
    return render(request, "monitor/detailOfCrash.html", context)
