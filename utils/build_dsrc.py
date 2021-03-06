#!/usr/bin/python
# Created by seefo
import Queue as queue
import os
import os.path
import subprocess
import sys
import threading
import time
import datetime
import copy

q = queue.Queue()
completedFileCount = 0
completedFiles = []
failedTasks = []
lastTickStatus = lambda: None

def displayQueueStatus():
    while q.qsize() > 0:
        completedTasks = totalTaskCount - q.qsize()
        progressPercent = (float(completedTasks) / float(totalTaskCount)) * 100.0

        # get stats between last tick
        tasksCompletedSinceLastTick = completedTasks - lastTickStatus.completedTasks
        timeSinceLastTick = time.time() - lastTickStatus.time

        # calculate eta
        speed = float(tasksCompletedSinceLastTick) / float(timeSinceLastTick)
        eta = float(q.qsize()) / max(speed, 1)

        # update tick object
        if timeSinceLastTick >= lastTickSampleRate:
            lastTickStatus.completedTasks = completedTasks
            lastTickStatus.time = time.time()

        # print current progress
        print '\x1b[2K\r', "Progress: %.2f%% [%d / %d] ETA %s (%d tasks/second)" % (progressPercent , completedTasks, totalTaskCount, str(datetime.timedelta(seconds=eta)).split(".")[0], speed),
        sys.stdout.flush()
        time.sleep(0.1)
    q.join()

def processTask( task ):
    toolCmd = task[0]
    srcFile = task[1]
    dstFile = task[2]
    toolCwd = task[3]

    if srcFile in completedFiles:
        return

    # remove dst file so we can validate successful creation
    if os.path.isfile(dstFile):
        os.remove(dstFile)

    # prepare tool run command
    cmd = toolCmd.replace("$srcFile", srcFile).replace("$dstFile", dstFile)
	

    # mif files require all instances of the toolCwd to be replaced
    if "DataTableTool" in toolCmd: 
        cmd = cmd.replace(toolCwd, "./", 1)
    elif "Miff" in toolCmd: 
        cmd = cmd.replace(toolCwd, "./", 2)
    else:
        cmd = cmd.replace(toolCwd, "./")

    # make sure destination folder exists
    dstFolder = os.path.dirname(dstFile)
    try:
        if not os.path.exists(dstFolder):
            os.makedirs(dstFolder)
    except:
        pass

    # run the tool
    retcode = -1

	# only one .mif file can be compiled at a time
    if "Miff" in toolCmd:
        if not os.path.exists(".mif_lock"):
            open(".mif_lock", 'a').close()
        else:
            time.sleep(0.5)
            failedTasks.append(task)
            return
	
    if displayCmdOutput:
        print "> [%s] %s" % (toolCwd, cmd)
        retcode = subprocess.call(cmd, shell=True, cwd=toolCwd, stderr=subprocess.STDOUT)
    else:
        FNULL = open(os.devnull, 'w')
        retcode = subprocess.call(cmd, shell=True, cwd=toolCwd, stdout=FNULL, stderr=subprocess.STDOUT)

    # remove .mif_lock if we were building a .mif file
    if "Miff" in toolCmd: os.remove(".mif_lock")
		
    # validate dst file was successfully created and no errorcode
    if os.path.isfile(dstFile) is False or retcode is not 0 or os.stat(dstFile).st_size == 0:
        failedTasks.append(task)
    else:
        global completedFileCount
        completedFileCount += 1

    completedFiles.append(srcFile)

def queueWorker():
    while True:
        task = q.get()
        processTask(task)
        q.task_done()

def startQueueWorkers():
    for i in range(numberOfWorkerThreads):
        t = threading.Thread(target=queueWorker)
        t.daemon = True
        t.start()

def walkAndCompareAndRun( src, dst, srcExt, dstExt, runCmd, toolCwd ):

    for root, dirs, files in os.walk(toolCwd + src):
        path = root.split(os.sep)

        for f in files:
            file = "%s/%s" % (root, f)
            ext = os.path.splitext(file)[1]

            if ext == srcExt and not file in ignoredFiles:
                dstFile = file.replace(src, dst).replace(srcExt, dstExt)

                if os.path.isfile(dstFile):
                    srcStat = os.stat(file)
                    dstStat = os.stat(dstFile)

                    if srcStat.st_mtime > dstStat.st_mtime or buildAllFiles or os.stat(dstFile).st_size == 0:
                        print "FILE %s NEEDS TO BE REBUILT" % (file)
                        q.put([runCmd, file, dstFile, toolCwd])

                else:
                    print "FILE %s NEEDS TO BE BUILT" % (file)
                    q.put([runCmd, file, dstFile, toolCwd])

# program settings
numberOfWorkerThreads = 8   # number of concurrent builder threads
lastTickSampleRate = 10     # sample rate in seconds, for eta/speed
buildAllFiles = False       # enable to skip modification time comparison
displayCmdOutput = False    # enable to display output of tools

ignoredFiles = [
    "content/sku.0/dsrc/sys.shared/built/game/misc/quest_crc_string_table.tab",
    "content/sku.0/dsrc/sys.server/built/game/misc/object_template_crc_string_table.tab",
    "content/sku.0/dsrc/sys.client/built/game/misc/object_template_crc_string_table.tab"
]

# Collect our content skus and prepare them to be built
skus = next(os.walk('content'))[1]
skus.sort()

# create the content.cfg so server can load data for the set of skus
contentCfg = "content/content.cfg"
with open(contentCfg, 'w') as cfg:
    cfg.write("[SharedFile]\n")
    for sku in skus:
        skuPath = "content/%s/" % (sku)

        sharedCompiled = "data/sys.shared/compiled/game"
        sharedBuilt = "data/sys.shared/built/game"

        serverCompiled = "data/sys.server/compiled/game"
        serverBuilt = "data/sys.server/built/game"

        clientCompiled = "data/sys.client/compiled/game"

        if os.path.exists(skuPath + sharedCompiled):
            cfg.write("searchPath2=../%s%s\n" % (skuPath, sharedCompiled))

        if os.path.exists(skuPath + sharedBuilt):
            cfg.write("searchPath2=../%s%s\n" % (skuPath, sharedBuilt))

        if os.path.exists(skuPath + serverCompiled):
            cfg.write("searchPath1=../%s%s\n" % (skuPath, serverCompiled))

        if os.path.exists(skuPath + serverBuilt):
            cfg.write("searchPath1=../%s%s\n" % (skuPath, serverBuilt))

        if os.path.exists(skuPath + clientCompiled):
            cfg.write("searchPath0=../%s%s\n" % (skuPath, clientCompiled))

    cfg.close()

# build javac classpath and sourcepath
dataPaths = []
dsrcPaths = []

for sku in skus:
    skuPath = os.path.abspath("./content/%s/" % (sku))

    sysShared = "sys.shared/compiled/game"
    sysServer = "sys.server/compiled/game"

    skuDataPath = skuPath + "/data/"
    skuDsrcPath = skuPath + "/dsrc/"

    try:
        if not os.path.exists(skuDataPath + sysShared): os.makedirs(skuDataPath + sysShared)
        if not os.path.exists(skuDataPath + sysServer): os.makedirs(skuDataPath + sysServer)
    except:
        pass

    dataPaths.append("%s%s" % (skuDataPath, sysShared))
    dataPaths.append("%s%s" % (skuDataPath, sysServer))
    dsrcPaths.append("%s%s" % (skuDsrcPath, sysServer))

# prepare search path for SWG tools
searchPath = "-- -s SharedFile"
for path in dataPaths: searchPath += " searchPath10=" + path

# build dsrc for each sku
for sku in skus:
    print "[*] Scanning sku: %s" % (sku)

    skuPath = "content/%s/" % (sku)

    # build datatables
    walkAndCompareAndRun("dsrc/", "data/",
                         ".tab", ".iff",
                         "../../configs/bin/DataTableTool -i $srcFile " + searchPath,
                         skuPath)

    # build objects
    walkAndCompareAndRun("dsrc/", "data/",
                         ".tpf", ".iff",
                         "../../configs/bin/TemplateCompiler -compile $srcFile",
                         skuPath)

    # build miff
    walkAndCompareAndRun("dsrc/", "data/",
                         ".mif", ".iff",
                         "../../configs/bin/Miff -i $srcFile -o $dstFile " + searchPath,
                         skuPath)

    # build scripts
    javaOutputPath = "data/sys.server/compiled/game"
    javaClassPath = ":".join(dataPaths)
    javaSourcePath = ":".join(dsrcPaths)
    javaCommand = 'javac -Xlint:-options -encoding utf8 ' \
                  '-classpath "%s" ' \
                  '-d "%s" ' \
                  '-sourcepath "%s" ' \
                  '-g -deprecation $srcFile' \
                  % (javaClassPath, javaOutputPath, javaSourcePath)

    walkAndCompareAndRun("dsrc/sys.server/compiled/game/script/",
                         "data/sys.server/compiled/game/script/",
                         ".java", ".class",
                         javaCommand, skuPath)

# prepare to start working
totalTaskCount = q.qsize()
print "[***] Need to process %d build tasks" % (totalTaskCount)
startQueueWorkers()

start = time.time()
lastTickStatus.completedTasks = 0
lastTickStatus.time = start

# start processing our queue of build tasks while there are tasks
displayQueueStatus()

# reprocess failed tasks incase it was the result of a dependency issue
if len(failedTasks) > 0:
    previousFailedTaskCount = len(failedTasks) + 1

    while previousFailedTaskCount > len(failedTasks) or os.path.exists(".mif_lock"):
        previousFailedTaskCount = len(failedTasks)
        failedTasksCopy = copy.deepcopy(failedTasks)

        completedFiles = []
        failedTasks = []

        for task in failedTasksCopy:
            q.put(task)

        displayQueueStatus()

    # no more files were built so prepare for final output
    if len(failedTasks) == previousFailedTaskCount: print ""


# display our final results
end = time.time()
print "[***] Successfully built %d files in %d seconds" % (completedFileCount, end - start)

# display results
print "[***] Failed to build %d tasks" % (len(failedTasks))
for task in failedTasks: print "FAILED TO BUILD %s" % (task[1])
