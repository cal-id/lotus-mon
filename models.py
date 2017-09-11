from django.db import models
from django.dispatch import receiver  # for catching deleted database objects
from monitor.conf import (GANGLIA_TIMES_DEFAULT, GANGLIA_BASIC_DEFAULT,
                          GANGLIA_REPORTS_DEFAULT, LSF_FIELDS_INDEX_COMMAND,
                          LSF_FIELDS_INDEX_USER, LSF_FIELDS_INDEX_QUEUE)
from django.conf import settings
import shutil
import os
from io import StringIO  # for writing to a buffer before using django file
import csv  # to save the lsf output
from django.core.files.base import File  # for saving files to database
from monitor import commandAnalyse
import json


class Host(models.Model):
    '''A database model for storing data about specific hosts.
        - address = full host address eg "host100.jc.rl.ac.uk"'''
    address = models.CharField("Full Address", max_length=100, unique=True)

    def getHostName(self):
        '''Gets the host name from the host address eg "hostXYZ" from the
        full address'''
        return self.address.split(".")[0]

    def __str__(self):
        return self.address


def addToSavedCommands(commandText, user, crash):
    '''Takes information about a command from lsf and updates a similar
    command with the new data (if there is one). Otherwise, a new command is
    created with this data. The user and crash should be django database
    instances'''
    # create a word distribution
    distribution = commandAnalyse.analyseCommand(commandText)
    # this acts as a tollerance as nothing is saved unless its diffence is
    # smaller than this
    lowestDifference = 0.7
    lowestCommand = False
    # this becomes the command if lowestDifference is beaten when comparing
    # word distributions
    for command in Command.objects.iterator():
        difference = commandAnalyse.difference(command.getDistribution(),
                                               distribution)
        if difference < lowestDifference:
            # If the two commands are more similar than commands we have
            # already compared or the original tollerance then store this
            # command to update later if no better one is found
            lowestCommand = command
    if lowestCommand is False:
        print("Creating new command")
        # if no command was found better than the tollerance then create one
        lowestCommand = Command(text=commandText)
        lowestCommand.setDistribution(distribution)
        # save it so data can be added later
        lowestCommand.save()
    else:
        print("Linking to command {}".format(command.text[0:50]))
    # add the user and the crash event to the command associated with this text
    # if the user or crash is already in the list then this command does
    # nothing
    lowestCommand.users.add(user)
    print("Linked Command to user {}".format(user.name))
    lowestCommand.crashes.add(crash)
    lowestCommand.save()


def getUploadDir(instance):
    'returns the upload folder for a class instance'
    assert instance.pk  # the CrashEvent must be saved before
    n = type(instance).__name__
    if n == "CrashEvent":
        host = instance.host
        i = instance.pk
    elif n == "GangliaGraph":
        host = instance.crashEvent.host
        i = instance.crashEvent.pk
    else:
        # this function shouldn't be called on an instance which is not defined
        raise Exception("Wrong class, update getUploadDir")
    return os.path.join(host.address, str(i))


def getUploadPath(instance, filename=""):
    'function to get the file save path from a class instance'
    # filename should be overwritten, it is just passed in by django
    # file uploaded to MEDIA_ROOT/host/id/<filename>
    n = type(instance).__name__
    if n == "CrashEvent":
        filename = instance.LSF_NAME
    elif n == "GangliaGraph":
        filename = "{}-{}.png".format(instance.timePeriod,
                                      instance.plotType)
    else:
        raise Exception("Wrong class, update getUploadPath")
    return os.path.join(getUploadDir(instance), filename)


class CrashEvent(models.Model):
    '''A database model for a crash event.
        - date = date of registering crash
        - host = the host object that the crash occured on
        - lsfCommonEnding = info about where to find the csv file of lsf data
        - gangliagraph_set = associated ganglia graphs
        - user_set = associated user objects according to lsf
        - command_set = associated command objects according to lsf'''
    # lsf name for use when saving a file
    LSF_NAME = "lsf.csv"
    date = models.DateTimeField('Occurred At')
    host = models.ForeignKey(Host, on_delete=models.CASCADE)
    lsfData = models.FileField(upload_to=getUploadPath)

    def setupLsfData(self, data, headers):
        '''sets up the class based on the parsed lsf data
            - headers = list of table headers for the  data
            - data = list of rows which each includes a list of data for each
                     header
            eg: headers =  [type of animal, age, width]
                data    = [[cat           , 10,  30]
                           [dog           , 7 ,  50]]
            ^ but with lsf data of course...

        This should only be called when a crash is registered to get the csv
        file and some specific data into the database.

        The function also updates / creates user and command objects as
        required.'''
        # Write data to csv
        out = StringIO()  # create an in-memory-file-like object
        lsfWriter = csv.writer(out)
        # write headers
        lsfWriter.writerow(headers)
        for row in data:
            # step through each row and write it
            lsfWriter.writerow(row)
        # 'placeholder filename' is used because a filename is required but
        # it gets overwritten by 'getUploadPath/getUploadDir'
        self.lsfData.save("Placeholder Filename", File(out))
        # if the conf file chose to select user
        for row in data:
            # Step through each row of data (one for each job)
            # create / update the queue
            thisQueue = row[LSF_FIELDS_INDEX_QUEUE]
            queue, justCreated = Queue.objects.get_or_create(name=thisQueue)
            if justCreated:
                queue.save()
            self.queue_set.add(queue)
            print("Linked to queue {}".format(thisQueue))
            # create / update a user
            thisUser = row[LSF_FIELDS_INDEX_USER]
            user, justCreated = User.objects.get_or_create(name=thisUser)
            if justCreated:
                user.save()
            self.user_set.add(user)
            print("Linked to user {}".format(thisUser))
            # create / update this command
            addToSavedCommands(row[LSF_FIELDS_INDEX_COMMAND], user, self)
            # No need to save the crash event itself because this should be
            # called from mon.py which saves this database later.

    def __str__(self):
        'formats the class as a string for command line / admin panel'
        return "{} at {}".format(self.host.address, self.date)


class User(models.Model):
    '''A database model for storing data about a specific user.
        - name = the username given by lsf
        - crashes = all CrashEvents that this user was running on
        - command_set = associated command objects according to lsf'''
    # A list of all crashes that this user was involved in
    # many to many because multiple users per crash and multiple crashes per
    # user
    crashes = models.ManyToManyField(CrashEvent)
    # index the name because it will be looked up every time adding a new crash
    name = models.CharField("Name", max_length=100, db_index=True, unique=True)

    def __str__(self):
        return "{}: #{}".format(self.name, self.crashes.count())


class Command(models.Model):
    '''A database model for storing information about a command.
        - text = the exact command returned by lsf
        - crashes = the crashes associated with this command
        - users = the useres associated with this command
        - distribution = the word distribution of this command found using
                         monitor.commandAnalyse.py (stored using json)'''
    text = models.CharField("Text", max_length=4096, unique=True)
    crashes = models.ManyToManyField(CrashEvent)
    users = models.ManyToManyField(User)
    # a large max length is needed because it is a dictionary stored as json
    distribution = models.CharField("Json Distribution", max_length=10000,
                                    unique=True)

    # the getter and setters below should be used to properly set the
    # distribution attribute
    def getDistribution(self):
        return json.loads(self.distribution)

    def setDistribution(self, distribution):
        self.distribution = json.dumps(distribution)

    def __str__(self):
        return self.shortText(maxLength=60)

    def parsedLinesOfText(self):
        'Returns the text as it should be before lsf replaced the \n with ;'
        return commandAnalyse.parseLsfLineBreaks(self.text)

    def shortText(self, maxLength=300):
        # Neatly truncates the text into a specific number of slices at a max
        # length
        t = self.text
        padding = " ....... "
        if len(t) <= maxLength:
            return t
        numSections = 3
        eachSection = ((maxLength - len(padding) * (numSections - 1)) //
                       numSections)
        start = t[:eachSection]
        end = padding + t[-eachSection:]
        middle = ""
        largeSection = (maxLength - (2 * eachSection)) // (numSections - 1)
        for middleBit in range(1, numSections - 1):
            centre = middleBit * largeSection + eachSection
            middle += padding + t[centre - eachSection // 2:
                                  centre + eachSection // 2]
        return start + middle + end


class Queue(models.Model):
    '''A database model for storing crashes linked to each queue.
        - name = the name of the queue eg par-single
        - crashes = the associated crashes for this queue'''
    crashes = models.ManyToManyField(CrashEvent)
    name = models.CharField("Name", max_length=100, db_index=True, unique=True)

    def __str__(self):
        return "{} #{}".format(self.name, self.crashes.count())


class GangliaGraph(models.Model):
    '''A database model for storing a ganglia graph.
        - crashEvent = the associated crash for this graph
        - commonEnding = the shared part of the URL / save path
        - plotType = what the plot shows (choices in conf file)
        - timePeriod = the time period that the graph displays (choices in
            conf file)'''
    # commonEnding is the shared part of the URL and save path for this file
    # <PATH_TO_SAVE><commonEnding> = save path
    # <BASE_URL><commonEnding>     = url
    image = models.FileField(upload_to=getUploadPath)
    # get the plot types from the conf file
    plotTypes = GANGLIA_BASIC_DEFAULT + GANGLIA_REPORTS_DEFAULT
    plotTypeChoices = [(plotType, plotType) for plotType in plotTypes]
    plotType = models.CharField(max_length=max(len(t) for t in plotTypes),
                                choices=plotTypeChoices, default=plotTypes[0])
    # do time periods from the conf file
    timePeriodChoices = [(timeP, timeP) for timeP in GANGLIA_TIMES_DEFAULT]
    timePeriod = models.CharField(max_length=max(len(t) for t in
                                                 GANGLIA_TIMES_DEFAULT),
                                  choices=timePeriodChoices,
                                  default=GANGLIA_TIMES_DEFAULT[0])
    # each ganglia graph is linked to a crash event
    crashEvent = models.ForeignKey(CrashEvent, on_delete=models.CASCADE)

    def __str__(self):
        return "Graph: {} over {}".format(self.plotType, self.timePeriod)


@receiver(models.signals.pre_delete)
def autoDeleteFile(sender, instance, **kwargs):
    'Deletes the file on disk when the database object is deleted'
    className = sender.__name__  # eg 'GangliaGraph'
    if className in ("GangliaGraph", "CrashEvent"):
        # if the class is one with a file
        if sender.__name__ == "GangliaGraph":
            # if its a ganlia graph then we can just delete the file
            filePath = os.path.join(settings.MEDIA_ROOT,
                                    getUploadPath(instance))
            if os.path.isfile(filePath):
                os.remove(filePath)
        elif sender.__name__ == "CrashEvent":
            # if its a crash event then delete the whole directory
            fileDir = os.path.join(settings.MEDIA_ROOT,
                                   getUploadDir(instance))
            if os.path.isdir(fileDir):
                # if it is a directory remove it and everything beneath
                shutil.rmtree(fileDir)
