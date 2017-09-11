'''A python script to analyse the commands submitted to lsf, they need to be
analysed so that they can be grouped according to similaries based on the
distribution of words in the command. A function in this script is also used
to render the command formatted correctly as lsf replaces \n with ;'''

import re
import csv


def parseLsfLineBreaks(strToParse):
    'lsf converts the string into one line by replacing \n with ;, revert this'
    return strToParse.replace(";", "\n")


def removeComments(strToParse):
    'Removes the bash-style comments from each line'
    # go through each line, create a list of lines which don't start with an
    # amount of whitespace and then a #
    # join these lines as a return
    return "\n".join([line for line in strToParse.splitlines()
                      if re.match(r'^\s*#', line) is None])


def getWords(strToParse):
    'Gets a list of words according to some rules to do with characters'
    regexWordBreak = r'[^a-zA-Z0-9_\-$\{\}]'
    return [word for word in re.split(regexWordBreak, strToParse)
            if word != '' and re.search(r'[a-zA-Z0-9]', word) is not None]


def getDistribution(listOfWords):
    '''Returns a distribution from a list of words as a dictionary of word
    against its proportion in the list'''
    total = len(listOfWords)
    return dict((uniqueWord, listOfWords.count(uniqueWord) / total)
                for uniqueWord in set(listOfWords))


def analyseCommand(commandString):
    '''Calls each of the funcitons above to create a word distribution from the
    command.'''
    muliline = parseLsfLineBreaks(commandString)
    noComments = removeComments(muliline)
    return getDistribution(getWords(noComments))


def basicGraph(distribution):
    'Draws a CLI graph of a distribution'
    keys = []
    vals = []
    for k, v in distribution.items():
        keys.append(k)
        vals.append(v)

    maxKeyLength = max(len(key) for key in keys)
    rJustKeys = [key + " " * (maxKeyLength - len(key) + 1) for key in keys]
    maxVals = max(vals)
    spaceLeft = 140 - (maxKeyLength + 1)
    # draw
    for key, val in zip(rJustKeys, vals):
        print(key + ("#" * int((spaceLeft * val / maxVals))))


def difference(dist1, dist2):
    'Calculates the sum of absolute error of the two distributions'
    sumError = 0
    wordsIn1 = set(dist1)
    wordsIn2 = set(dist2)
    # the intersect of the sets are the words in both
    wordsInBoth = wordsIn2 & wordsIn1
    # add the error between the words that are in both
    sumError += sum(abs(dist1[word] - dist2[word]) for word in wordsInBoth)
    # add the value (error) of the words in the individual ones
    sumError += sum(dist1[word] for word in wordsIn1 - wordsInBoth)
    sumError += sum(dist2[word] for word in wordsIn2 - wordsInBoth)
    return sumError


# ############################### TESTING #####################################


def getLsfCommandsInDB():
    'Returns the commands saved in the django database lsf files'
    from .models import CrashEvent
    CMD_INDEX = 12
    cmds = []
    for crash in CrashEvent.objects.all():
        try:
            # change from the default of 'rb'
            crash.lsfData.read()
            crash.lsfData.close()
            crash.lsfData.open(mode="r")
            crash.lsfData.seek(0)
        except ValueError as e:
            pass
        else:
            for i, row in enumerate(csv.reader(crash.lsfData)):
                if i > 0:  # exclude headers
                    cmds.append(row[CMD_INDEX])
            crash.lsfData.close()
    return cmds


def go():
    'A function to parse the data quicker'
    a = getLsfCommandsInDB()
    b = [analyseCommand(c) for c in a]
    return a, b


def buildMostCommonWords():
    'Create a sorted list of the most common words, for information only'
    cmds, aCmds = go()
    largeDict = dict()
    for aCmd in aCmds:
        for key, value in aCmd.items():
            if key in largeDict:
                largeDict[key] += value
            else:
                largeDict[key] = value
    return sorted(largeDict.items(), key=lambda a: a[1])


def testBounds(aCmds, lower, upper):
    '''A function that prints any pairs of saved commands that are within the
    bounds passed as arguments. Used to investigate a good boundary for
    deciding whether commands are similar enough.'''
    for iX, x in enumerate(aCmds):
        for i, y in enumerate(aCmds[iX + 1:]):
            iY = i + iX + 1
            d = difference(x, y)
            if lower < d < upper and x != {} and y != {}:
                print(iX, iY, d)
