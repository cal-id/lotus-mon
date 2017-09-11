# -------------------------------- DOC STRING ---------------------------------

'''A monitoring script for lotus crashes. Gets called when a host
crashes to record data about the lsf usage and ganglia plots.

DEPENDS on the wrapper script 'bjobsLSF.sh' which sources the lsf profile.
'''

# ------------------------------- DEPENDENCIES -------------------------------
# STANDARD IMPORTS (should come included with python3)
from sys import argv  # for parsing command line inputs
from subprocess import check_output  # for calling bjobs
from re import finditer, escape  # for parsing the lsf results
from io import BytesIO
import os

# PIP IMPORTS (need to be installed with pip3)
# django, requests
import requests  # for downloading ganglia plots
from django.utils import timezone  # for recording django times
from django.core.files.base import File  # for saving files to database

# LOCAL IMPORTS (other files)
from monitor.models import CrashEvent, Host  # models for db
# app level configuration
from monitor.conf import (GANGLIA_ROOT, LSF_FIELDS, GANGLIA_TIMES,
                          GANGLIA_REPORTS, GANGLIA_BASIC)


# ---------------------------- FUNCTIONS --------------------------------------


def runThroughCrash(hostAddress):
    'The base function that handles a crash by calling other functions'
    print("Starting up")
    hostDB, isNew = Host.objects.get_or_create(address=hostAddress)
    if isNew:
        hostDB.save()
    hostName = hostDB.getHostName()  # split off the 'hostXYZ' from the address
    print("Looking at host: {} <=> {}".format(hostName, hostAddress))
    # create a django db instance
    crashEvent = CrashEvent(date=timezone.now(), host=hostDB)
    print("Created crash event")
    # the save here is required (so it gets an id and later we can add ganglia)
    try:
        crashEvent.save()
    except BaseException as e:
        print("ERROR on save:", e)
        raise
    try:
        # get and save the lsf results
        print("before query lsf")
        queryLsf(hostAddress, crashEvent)
        # get and save the ganglia results
        queryGanglia(hostAddress, crashEvent)
        crashEvent.save()  # save the database changes
        print("Database instance saved")
    except BaseException as e:
        # if there is an error then delete the crash event so that a broken
        # half copy isn't hanging around...
        crashEvent.delete()
        print("failed, deleting crash event")
        print("Error type:", type(e))
        print("Message (if any):", e)
        raise


def queryLsf(host, crashEvent):
    '''Queries lsf and saves the information to csv.
        - host as string 'hostABC.jc.rl.ac.uk'
        - crashEvent is a django database 'CrashEvent' model'''
    # according to
    # https://www.ibm.com/support/knowledgecenter/en/SSETD4_9.1.2/lsf_command_ref/bjobs.1.html
    # specify the output format of bjobs with
    # bjobs -o "field_name[:[-][output_width]] ... [delimiter='character']"

    # The ideal would be to specify a delimiter (eg '/') and then split each
    # line of output around this character. However, bjobs doesn't escape
    # the delimiter if it appears elsewhere. Attributes like 'command' seem
    # to contain any character so this would lead to errors.

    # A different approach is to use a fixed width for each column and a known
    # delimiter. By finding the positions of the delimiter in the header (and
    # choosing a delimiter that isn't in any of the headers), the position
    # is the same for each of the rows so can be determined accurately.
    #    However, this means that an arbitrary column width for each column
    # has to be chosen so data would be lost to bjobs truncating any cell that
    # is longer than this column. Although there are 'suggested values', in
    # testing it seems that our lsf usage seems to regularly exceed those
    # values (eg hostname is suggested 11 characters - allowing only
    # jc.rl.ac.uk).
    #    To try to minimise truncating, the site above seems to indicate that
    # 4096 is the maximum size of each element in the table so that value can
    # be reasonably safely used as a width.
    #    Although it is over the top to request a table with 4096 characters
    # in each cell, it seems to run roughly 70 times faster (testBjobsSpeed.py)
    # than the alternative: requesting each field with an individual 'bjobs'
    # command. So it is assumed that it is the method that causes the least
    # strain on lsf.

    delimiter = "|"  # can be anything that wont be in the table header
    maxWidthFormatter = ":4096 "
    formatArg = (maxWidthFormatter.join(LSF_FIELDS) + maxWidthFormatter +
                 "delimiter='{}'".format(delimiter))
    # Get the path to the bjobs script (in the same directory as this file)
    bjobsScript = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                               "bjobsLSF.sh")
    try:
        # removing trailing spaces / new lines with strip
        # call bjobsLSF.sh which is a wrapper script for bjobs by sourcing the
        # LSF profile before running bjobs
        lines = check_output([bjobsScript, "-o", formatArg, "-u", "all",
                              "-m", host]).decode("utf-8").strip().split("\n")
        # Content of bjobsLSF.sh - for info
        # #! /bin/bash
        # source /apps/lsf/conf/profile.lsf
        # bjobs "$@"
        print("Queried lsf, returned {} lines of output".format(len(lines)))
    except FileNotFoundError:
        print("ERROR couldn't find the bjobs wrapper script")
        raise
    if len(lines) <= 1:
        # if there is no actual output then don't save any lsf data
        print("No lsf data for this crash, not saving any")
        raise
    header = lines[0]
    # check that the correct number of fields were returned
    assert header.count(delimiter) == len(LSF_FIELDS) - 1
    # use escape function to avoid problems with special characters in python
    # strings when using regex
    delimiterIndicies = [m.start()
                         for m in finditer(escape(delimiter), header)]
    data = []  # a list that will contain the data by each row
    for row in lines[1:]:
        # step through each line of data (index 0 is table header)
        cells = []
        lastIndex = -1
        for index in delimiterIndicies + [len(row)]:
            # Step through each column separator position and a
            # 'fake separator' which is at the end of the row
            # (to include the last cell).
            # split from the last column separator (+1 for exclusive
            # split) up to this column separator
            # use .strip() to remove trailing whitespace
            cells.append(row[lastIndex + 1:index].strip())
            lastIndex = index
        data.append(cells)
    headers = [cell.strip() for cell in header.split(delimiter)]
    print("Parsed lsf data")
    crashEvent.setupLsfData(data, headers)  # save it to the database


def queryGanglia(hostAddress, crashEvent):
    'queries and saves the graphs from ganglia'
    # host must be of the form hostABC.jc.rl.ac.uk
    assert "." in hostAddress
    totalBytesDownloaded = 0  # record the number of bytes downloaded
    # define the query string keys for ganglia graphs
    REPORT_KEY = "&g="  # report plots = with multiple data points (coloured)
    BASIC_KEY = "&m="  # basic plots = with only one (grey)
    HOST_KEY = "&h="  # the host is full form suffix 'jc.rl.ac.uk'
    TIME_KEY = "&r="  # the time is one of the periods definied below
    # the part of the query string that doesn't seem to change between graphs
    qs = "z=xlarge&c=JASMIN+Cluster"
    # the two types of plot are the same url but with different key value pairs
    # so just join the two lists into pairs with their respective keys
    gangliaPlots = ([(REPORT_KEY, value) for value in GANGLIA_REPORTS] +
                    [(BASIC_KEY, value) for value in GANGLIA_BASIC])
    for plotKey, plot in gangliaPlots:
        # step through the different types of plot and the key for that plot
        for t in GANGLIA_TIMES:
            # step through different graph periods
            # create a database instance
            d = crashEvent.gangliagraph_set.create(plotType=plot, timePeriod=t)
            # save it
            d.save()
            # deal with getting the image
            extra = TIME_KEY + t + HOST_KEY + hostAddress + plotKey + plot
            url = (GANGLIA_ROOT + qs + extra)
            print("Ganglia get {}".format(extra))
            # download the image to a file
            response = requests.get(url).content
            totalBytesDownloaded += len(response)  # add to the total
            output = BytesIO()
            output.write(response)
            # save in django db
            # placeholder is used because the database model converts it
            # 'File' is used to convert the in memory file to a django format
            # output
            d.image.save("placeholder", File(output))
            print("Written Image")
        # example ganglia urls - both report style
        # graph.php?r=hour&z=large&h=host064.jc.rl.ac.uk&m=load_one&s=by+name&mc=2&g=load_report&c=JASMIN+Cluster
        # graph.php?r=8hr&z=large&h=host064.jc.rl.ac.uk&m=load_one&s=by+name&mc=2&g=load_report&c=JASMIN+Cluster
    # convert totalBytesDownloaded to MB with 1dp and print it
    numMB = int(totalBytesDownloaded / (10 ** 5)) / 10
    print("Finished all graphs. Total downloaded {:3.1f}MB".format(numMB))


if __name__ == "__main__":
    # if this is isn't being imported
    # script is called as 'python3 mon.py host ...'
    # this sets argv = ["mon.py", host ...]
    # only continue if one argument (host) is passed
    assert len(argv) == 2
    runThroughCrash(argv[1])
