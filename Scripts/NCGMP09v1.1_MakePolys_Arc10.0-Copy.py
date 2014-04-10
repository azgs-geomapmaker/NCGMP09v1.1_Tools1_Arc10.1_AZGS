# script to
#   * Make polys from ContactsAndFaults without concealed lines
#   * Use any mix of previously-tagged polys and labelpoints to
#     tag polys
#   * Identify conflicts between labelpoints and (or) previously
#     polys
# 	Ralph Haugerud
#	USGS, Seattle
#
#  Usage:
#  prompt> NCGMP09v1.1_MakePolys_Arc10.0.py <geodatabaseName> <saveMUPs> <polyLayer>
#
#	<geodatabaseName> can be either a personal geodatabase or a file 
#	geodatabase, .mdb or .gdb. The filename extension must be included. 
#	<GeodatabaseName> must be an NCGMP09-style database with feature 
#	data set GeologicMap that contains feature classes ContactsAndFaults,
#	MapUnitPolys, and MapUnitPoints.
#
#       <saveMUPs> (optional, default is FALSE) is a flag (true or false) that
#       causes saving of existing MapUnitPolys to MapUnitPolys001, ...0002, etc.
#
#       <PolyLayer> (optional) is the name of the PolyLayer in the current ArcMap
#       session. It is saved, deleted, and then re-added to the map layout to avoid
#       locking problems when running MakePolys during an ArcMap session. 
#
#	MapUnitPolys will be rebuilt from ContactsAndFaults (except for concealed
#	lines), with polygon attributes obtained from existing polygons in
#	MapUnitPolys and MapUnitPoints.
#
#	Output also includes 4 new feature classes within GeologicMap. Any
#	existing feature classes with these names will be overwritten:
#	     badPolys
#	     badLabels
#	     blankPolys
#	     excessContacts
#	This code also writes (overwrites) and deletes feature classes
#	   xxPolys, templabels, and xxLabels
#
#       Assumes field IsConcealed in ContactsAndFaults has values of 'Y' and 'N'
#
# 12/12/12 - minor edit by Evan Thoms, USGS starting at line 147. Mostly works well from
# within ArcMap now. There are still occasional hiccups when trying to overwrite 'MapUnitPolys'


import arcpy, sys, os.path

debug = False

versionString = 'NCGMP09v1.1_MakePolys_Arc10.0.py, version of 12 December 2012'

xxPolys = 'xxxpolys'
xxLabels = 'xxxlabels'
tempLabels = 'xxxtlabels'
mupLayer2 = 'xxxMupLayer2'
cafLayer = 'cafLayer'

default = ''

def addMsgAndPrint(msg, severity=0): 
	# prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool) 
	try: 
	  for string in msg.split('\n'): 
		# Add appropriate geoprocessing message 
		if severity == 0: 
			arcpy.AddMessage(string) 
		elif severity == 1: 
			arcpy.AddWarning(string) 
		elif severity == 2: 
			arcpy.AddError(string) 
	except: 
		pass
	
def testAndDelete(fc):
    if arcpy.Exists(fc):
        if debug: addMsgAndPrint('    deleting '+fc)
        arcpy.Delete_management(fc)
    return

def writeLayerNames(lyr):
    if lyr.supports('datasetName'): addMsgAndPrint('datasetName: '+lyr.datasetName)
    if lyr.supports('dataSource'):  addMsgAndPrint(' dataSource: '+lyr.dataSource)
    if lyr.supports('longName'):    addMsgAndPrint('   longName: '+lyr.longName)
    if lyr.supports('name'):        addMsgAndPrint('       name: '+lyr.name)
    
#added by ET for more functionality in ArcMap
def findLyr(lname):
    if debug: addMsgAndPrint('lname = '+lname)
    mxd = arcpy.mapping.MapDocument('CURRENT')
    for df in arcpy.mapping.ListDataFrames(mxd):
        lList = arcpy.mapping.ListLayers(mxd, '*', df)
        #lyrNames = ''
        #for lyr in lList:
        #    lyrNames = lyrNames+' '+lyr.name
        #addMsgAndPrint(lname+'  '+lyrNames)
        if debug:
            for lyr in lList:
                writeLayerNames(lyr)
        for lyr in lList:
            # either layer is a group, datasetName is not supported, and we match lyr.name
            # or (and) we match datasetName, which cannot be aliased as lyr.name may be
            if ( lyr.supports('datasetName') and lyr.datasetName == lname ) or lyr.name  == lname:
                #addMsgAndPrint('str(lyr) is '+str(lyr))    
                pos = lList.index(lyr)
                if pos == 0:
                    refLyr = lList[pos + 1]
                    insertPos = "BEFORE"
                else:
                    refLyr = lList[pos - 1]
                    insertPos = "AFTER"
                return [lyr, df, refLyr, insertPos]

def main(dbfds):
    arcpy.env.workspace = dbfds
  #try:
    # identify mup and caf feature classes
    addMsgAndPrint('  identifying MapUnitPolys and ContactsAndFaults feature classes:')
    fcs = arcpy.ListFeatureClasses()
    for fcName in 'MapUnitPolys','ContactsAndFaults':
        mups = []
        for fc in fcs:
            if fc.find(fcName) > -1 and arcpy.Describe(fc).featureType == 'Simple' and fc[-6:] == fcName[-6:]:
                mups.append(fc)
        if len(mups) == 1:
            if fcName == 'MapUnitPolys':
                mup = mups[0]
                addMsgAndPrint('    '+mup)
            else:
                caf = mups[0]
                addMsgAndPrint('    '+caf)
        else:
            addMsgAndPrint('Cannot identify '+fcName+' featureclass. Candidates are '+str(mups))
            sys.exit()

    addMsgAndPrint('  checking for _ID fields')
    for fc in mup,caf:
        fcFields = arcpy.ListFields(fc)
        fcFieldNames = []
        for fcF in fcFields:
            fcFieldNames.append(fcF.name)
        if not fc+'_ID' in fcFieldNames and not fc+'.'+fc+'_ID' in fcFieldNames:
            addMsgAndPrint(str(fcFieldNames))
            addMsgAndPrint('Field '+fc+'_ID is not present in feature class '+fc)
            sys.exit()

    # assign output feature class names
    prefix = mup.replace('MapUnitPolys','')
    badLabels = 'errors_'+prefix+'multilabels'
    badPolys = 'errors_'+prefix+'multilabelPolys'
    blankPolys = 'errors_'+prefix+'unlabeledPolys'
    excessContacts = 'errors_'+prefix+'excessContacts'
    idCAF = 'edit_'+prefix+'CAFwithPolys'
    
    #******************
    #ET - I added the code below (and later in the script) in order to accommodate my
    #workflow of editing lines and polygons in ArcMap and expecting the properties of my
    #MapUnitPolygons layer to not change, eg symbolization based on a join with
    #DescriptionOfMapunits. 
    #The layer disappears from ArcMap if the data source is deleted in realtime. 
    #This additional code unhooks datasource from the layer and then hooks it back up
    # after the new MapUnitPolygons has been created
    #first see if the MapUnitsPolygon layer parameter was specified
    #the form control is only enabled if MapDocument("CURRENT") exists.
    ## RH: I further modified this to search, save, and delete
    ## any layers with sources (see definitions above):
    ##      badLabels, blankPolys, excessContacts, idCAF
    editLayers = [mup,badLabels,badPolys,blankPolys,excessContacts,idCAF]
    savedLayers = []
    layerN = 1
    for aLyr in editLayers:
        layerFound = True
        while layerFound:  # repeat to look for multiple layers with fc of interest
            try:
                lyr,df,refLyr,insertPos = findLyr(aLyr)
                # if layer is part of a layer group, get layer group instead
                while lyr.longName.find('\\') > 0:
                    groupLyrName = lyr.longName[:lyr.longName.find('\\')]
                    lyr,df,refLyr,insertPos = findLyr(groupLyrName)
            except:  # crashes because there is no matching layer
                layerFound = False
            if layerFound:
                scriptHome = os.path.dirname(sys.argv[0])
                grandhome = os.path.dirname(scriptHome)
                docsPath = os.path.join(grandhome, 'Docs')
                # WHY OH WHY do we let Windoze programmers build our tools?
                lyrName = lyr.name.replace('\\','_')
                lyrPath = os.path.join(docsPath, lyrName + str(layerN) + '.lyr')
                #save to a layer file on disk so that customizations can be retrieved layer
                if arcpy.Exists(lyrPath):
                    os.remove(lyrPath)
                arcpy.SaveToLayerFile_management(lyr, lyrPath, "RELATIVE")
                #and now remove the layer so that the rest of Ralph's code works
                arcpy.mapping.RemoveLayer(df, lyr)
                savedLayers.append([lyrPath,df,refLyr,insertPos,lyr])
                addMsgAndPrint('  layer '+lyrName+' saved and removed from map composition')
                layerN = layerN+1
    ##raise arcpy.ExecuteError
    #******************

    # check for and delete scratch stuff
    addMsgAndPrint('  deleting temporary and output feature classes...')
    for fc in badPolys,badLabels,blankPolys,tempLabels,xxPolys,xxLabels,excessContacts,idCAF,cafLayer,mupLayer2:
        testAndDelete(fc)

    # make tempLabels from existing MapUnitPolys, 
    # then select and delete those labels with MapUnit = ''
    addMsgAndPrint('  making temporary labels from existing mapunit polygons')
    arcpy.FeatureToPoint_management(mup,tempLabels,'INSIDE')
    sqlQuery = arcpy.AddFieldDelimiters(dbfds,'MapUnit') +  " == ''"
    if debug: addMsgAndPrint(sqlQuery)
    arcpy.MakeFeatureLayer_management(tempLabels,mupLayer2,sqlQuery)
    arcpy.DeleteRows_management(mupLayer2)

    # append MapUnitPoints to tempLabels
    if arcpy.Exists('MapUnitPoints'):
        addMsgAndPrint('  appending MapUnitPoints to temporary labels')
        arcpy.Append_management('MapUnitPoints',tempLabels,'NO_TEST')

    # create layer view from ContactsAndFaults w/o concealed lines
    sqlQuery = arcpy.AddFieldDelimiters(dbfds,'IsConcealed') + " NOT IN ('Y','y')"
    if debug: addMsgAndPrint(caf + ' ' + sqlQuery)
    arcpy.MakeFeatureLayer_management(caf,cafLayer,sqlQuery)

    # either move polys out of the way or delete it
    mupPath = os.path.join(arcpy.env.workspace, mup)
    if saveMUP:
        # get new name
        pfcs = arcpy.ListFeatureClasses(mup+'*')
        maxN = 0
        for pfc in pfcs:
            try:
                n = int(pfc.replace(mup,''))
                if n > maxN:
                    maxN = n
            except:
                pass
        oldPolys = mup+str(maxN+1).zfill(3)
        oldPolysPath = os.path.join(arcpy.env.workspace, oldPolys)
        addMsgAndPrint('  saving '+mup+' to '+oldPolys)
        try:
            arcpy.Copy_management(mupPath, oldPolysPath)
        except:
            addMsgAndPrint(" arcpy.Copy_management(mup,oldPolys) failed. Maybe you need to close ArcMap?")
            raise arcpy.ExecuteError
    arcpy.Delete_management(mupPath)

    # rebuild polys
    addMsgAndPrint('  creating new MapUnitPolys from ContactsAndFaults w/o concealed lines')
    arcpy.FeatureToPolygon_management('cafLayer',mup,'','ATTRIBUTES',tempLabels)

    addMsgAndPrint('  intersecting (IDENTITY) points and polys...')
    arcpy.Identity_analysis(tempLabels, mup, xxLabels)

    FIDpolys = 'FID_'+mup
    #FIDpoints = 'FID_'+tempLabels
    FieldList = ''
    SortFields = FIDpolys+' A'
    excessPoints = []
    badPolyList = []
    ## this next section (~24 lines) might be replaced by select MUP <> MUP_1,
    ##   asel IdCon <> IdCon_1, etc. and then listing the selected set
    addMsgAndPrint('  finding mapunit polygons with conflicting label points')
    rows = arcpy.SearchCursor(xxLabels,"","","",SortFields)
    lastPoly = -2
    lastMU = ''
    lastIdCon = ''
    lastDataSource = ''
    lastMUPID = ''
    row = rows.next()
    while row:
        if row.getValue(FIDpolys) == lastPoly:
            if str(row.getValue('MapUnit')) <> lastMU or \
               str(row.getValue('IdentityConfidence')) <> lastIdCon or \
               str(row.getValue('DataSourceID')) <> lastDataSource or \
               str(row.getValue(mup+'_ID')) <> lastMUPID:
                   badPolyList.append(row.getValue(FIDpolys))
        else:
            lastPoly = row.getValue(FIDpolys)
            lastMU = str(row.getValue('MapUnit'))
            lastIdCon = str(row.getValue('IdentityConfidence'))
            lastDataSource = str(row.getValue('DataSourceID'))
            lastMUPID = str(row.getValue(mup+'_ID'))
        row = rows.next()
    badPolyList = list(set(badPolyList))
    ### end section that could be replaced
    addMsgAndPrint('  copying MapUnitPolys to '+xxPolys)
    
    #ET - as described above, we need full paths for copy_management to work
    #I think - for some reason - this is because ArcMap is open
    srcPath = os.path.join(arcpy.env.workspace, mup)
    desPath = os.path.join(arcpy.env.workspace, xxPolys)
    arcpy.Copy_management(srcPath, desPath)
    
    OidName = arcpy.Describe(xxPolys).OIDFieldName
    addMsgAndPrint('  adding field MultipleLabels to '+badPolys)
    arcpy.AddField_management(xxPolys,'MultipleLabels','TEXT',default,default,5)
    addMsgAndPrint('  adding field MultipleLabels to '+badLabels)
    arcpy.AddField_management(xxLabels,'MultipleLabels','TEXT',default,default,5)
    addMsgAndPrint('  iterating through '+xxPolys)
    rows = arcpy.UpdateCursor(xxPolys)
    row = rows.next()
    while row:
        if row.getValue(OidName)in badPolyList:
            row.setValue('MultipleLabels','YES')
            rows.updateRow(row)
        row = rows.next()
    addMsgAndPrint('  iterating through '+xxLabels)
    rows = arcpy.UpdateCursor(xxLabels)
    row = rows.next()
    while row:
        if row.getValue(FIDpolys) in badPolyList:
            row.setValue('MultipleLabels','YES')
            rows.updateRow(row)
        row = rows.next()

    query = arcpy.AddFieldDelimiters(dbfds,'MultipleLabels') + " = 'YES'"
    addMsgAndPrint('  selecting multi-label polys to '+badPolys)
    testAndDelete(badPolys)
    arcpy.Select_analysis(xxPolys,badPolys,query)
    addMsgAndPrint('  selecting multiple labels to '+badLabels)
    testAndDelete(badLabels)
    arcpy.Select_analysis(xxLabels,badLabels,query)
    query = arcpy.AddFieldDelimiters(dbfds,'MapUnit') + " = ''"
    addMsgAndPrint('  selecting unlabeled polys to '+blankPolys)
    testAndDelete(blankPolys)
    arcpy.Select_analysis(mup,blankPolys,query)

    # Identity to get polys that adjoin each line
    addMsgAndPrint('  IDENTITYing '+caf+' with '+mup+' to get adjoining polys')
    arcpy.Identity_analysis(caf,mup,idCAF,'ALL','','KEEP_RELATIONSHIPS')
    ##for f in arcpy.ListFields(idCAF):
    ##    print f.name
    # select those arcs that are not concealed, not faults, and have same map unit in both sides
    query = arcpy.AddFieldDelimiters(dbfds,'Type') + " = 'contact' and " + arcpy.AddFieldDelimiters(dbfds,'IsConcealed')
    query = query + " = 'N' and "+arcpy.AddFieldDelimiters(dbfds,'Left_MapUnit')+" = "+arcpy.AddFieldDelimiters(dbfds,'Right_MapUnit')
    if debug:
            addMsgAndPrint('  selecting contacts with same map unit on both sides to '+excessContacts)
    testAndDelete(excessContacts)
    arcpy.Select_analysis(idCAF,excessContacts,query)
    
    #ET- add the saved layer file to the document
    ## RH--Restore all saved layers
    #we get the data frame and layer position from findLyr
    addMsgAndPrint('  restoring saved layers')
    savedLayers.reverse()
    for savedLayer in savedLayers:
        lyrPath,dataFrame,refLyr,insertPos,lyr = savedLayer
        addMsgAndPrint('    layer '+lyr.name)
        addLyr = arcpy.mapping.Layer(lyrPath)
        arcpy.mapping.AddLayer(dataFrame, addLyr)

        # if refLyr is part of a layer group, substiture layer group 
        refLyrName = refLyr.longName
        while refLyrName.find('\\') > 0:
                groupLyrName = refLyrName[:refLyrName.find('\\')]
                refLyr = findLyr(groupLyrName)[0]
                refLyrName = refLyr.longName

        try:
            arcpy.mapping.InsertLayer(dataFrame, refLyr, addLyr, insertPos)
        except:
            addMsgAndPrint('    failed to insert '+str(addLyr)+' '+insertPos+' refLyr '+str(refLyr))
            mxd = arcpy.mapping.MapDocument('CURRENT')
            for df in arcpy.mapping.ListDataFrames(mxd):
                lList = arcpy.mapping.ListLayers(mxd, '*', df)
                for lyr in lList:
                    addMsgAndPrint('      '+str(lyr)+', matches refLyr = '+str(lyr == refLyr))
                    if str(lyr) == str(refLyr):
                        writeLayerNames(lyr)
                        writeLayerNames(refLyr)                    

        arcpy.Delete_management(lyrPath)

    # cleanup
    addMsgAndPrint('  cleaning up')
    del row, rows
    for fc in (xxPolys,xxLabels,tempLabels,cafLayer,mupLayer2):
        testAndDelete(fc)
        
    # report results    
    for fc in (badPolys,badLabels,blankPolys,excessContacts):
        nrows = int(arcpy.GetCount_management(fc).getOutput(0))
        addMsgAndPrint('  '+str(nrows)+' rows in '+fc)

"""
  except:
    lineNo = str(sys.exc_traceback.tb_lineno)
    addMsgAndPrint('Error on line ' + lineNo)
    #some cleanup
    try:
        arcpy.Delete_management('cafLayer')
    except:
        raise arcpy.ExecuteError
    try:
        del mup
    except:
        raise arcpy.ExecuteError
"""
   

### START HERE ###
addMsgAndPrint(versionString)
if len(sys.argv) > 2 and sys.argv[2].upper() == 'FALSE':
        saveMUP = False
else:
        saveMUP = True
dbfds = sys.argv[1]
addMsgAndPrint('  testing for schema lock...')
if arcpy.TestSchemaLock(dbfds):
        main(dbfds)
else:
        addMsgAndPrint('  '+sys.argv[1]+' is locked. Stop editing (ArcMap) or close ArcCatalog?')
        sys.exit()

