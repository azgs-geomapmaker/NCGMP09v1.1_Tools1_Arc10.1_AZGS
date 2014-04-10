# ncgmp09v1.1_10.0_CreateDatabase_1.py
#   Python script to create an empty NCGMP09-style
#   ArcGIS 10 geodatabase for geologic map data
#
#   Ralph Haugerud, USGS
#  Modified by Janel Day, AZGS, Spring 2014:
#        Topology added
#        Domains added
#        Coordinate System added as create feature dataset parameter 
#           Tool originally written to create feature dataset with undefined SRS and then
#           to later be assigned an SRS using define projection management function.
#           Assigning SRS after dataset is created causes spatial reference/indexing 
#           problems     
#        Cartographic Representations added 
#
#   Takes 4 arguments: <outputDir>  <geoDataBaseName> <coordSystem> <number of cross sections>
#     to use local directory, use # for outputDir
#     # accepted for <coordSystem>
#     if geoDatabaseName ends in .gdb, a file geodatabase will be created
#     if geoDatabaseName ends in .mdb, a personal geodatabase will be created
#	coordSystem is a filename for an ESRI coordinate system definition (look 
#	in directory arcgis/Coordinate Systems). Use # to define coordinate system
#     later
#
#   Requires that ncgmp09_definition.py be present in the local directory 
#     or in the appropriate Python library directory.
#
#   On my laptop, this takes many minutes to run and creates a 
#      ~0.5GB file/directory
#
# To use this:
#   	1) run script, e.g.
#		C:\myworkspace> ncgmp09_CreateDatabase.py # newgeodatabase.gdb # 1 false false
#	2) Open newgeodatabase in ArcCatalog, doubleclick on feature data set GeologicMap,
#	   and assign a spatial reference system
#	3) If you use the CorrelationOfMapUnits feature data set, note that you will have to 
#	   manually create the annotation feature class CMUText and add field ParagraphStyle.
#	   (I haven't yet found a way to script the creation of an annotation feature class.)
#	4) If there will be non-standard point feature classes (photos, mineral occurrences,
#	   etc.), copy/paste/rename feature class GenericPoint or GenericSample, as appropriate,
#	   and add necessary fields to new feature class
#	5) Delete any unneeded feature classes and feature data sets
#	6) Load data. Edit as needed
#
#  NOTE: CAN ALSO BE RUN AS TOOLBOX SCRIPT FROM ARCCATALOG

import arcpy, sys, os
from NCGMP09v11_Definition import tableDict

versionString = 'NCGMP09v1.1_CreateDatabase_Arc10.0.py, version of 20 September 2012'

default = '#'

#cartoReps = False # False if cartographic representations will not be used

transDict =     { 'String': 'TEXT',
			'Single': 'FLOAT',
			'Double': 'DOUBLE',
			'NoNulls':'NON_NULLABLE',
			'NullsOK':'NULLABLE',
			'Date'  : 'DATE',
			'Short': 'SHORT'}

usage = """Usage:
   systemprompt> ncgmp09_create.py <directory> <geodatabaseName> <coordSystem>
                <OptionalElements> <#XSections> <AddRepresentations> <AddLTYPE>
   <directory> is existing directory in which new geodatabaseName is to 
      be created, use # for current directory
   <geodatabaseName> is name of gdb to be created, with extension
      .gdb causes a file geodatabase to be created
      .mdb causes a personal geodatabase to be created
   <coordSystem> is a fully-specified ArcGIS coordinate system
   <OptionalElements> is either # or a semicolon-delimited string specifying
      which non-required elements should be created (e.g.,
      OrientationPoints;CartographicLines;RepurposedSymbols )
   <#XSections> is an integer (0, 1, 2, ...) specifying the intended number of
      cross-sections
   <AddRepresentations> is either true or false (default is false). If true, add
      fields for Cartographic representions to all feature classes
   <AddLTYPE> is either true or false (default is false). If true, add LTYPE field
      to feature classes ContactsAndFaults and GeologicLines and add PTTYPE field
      to feature class OrientationData    

  Then, in ArcCatalog:
  * If you use the CorrelationOfMapUnits feature data set, note that you will 
    have to manually create the annotation feature class CMUText and add field 
    ParagraphStyle. (I haven't yet found a way to script the creation of an 
    annotation feature class.)
  * If there will be non-standard point feature classes (photos, mineral 
    occurrences, etc.), copy/paste/rename feature class GenericPoint or 
    GenericSample, as appropriate, rename the _ID field, and add necessary
    fields to the new feature class.
  * Load data, if data already are in GIS form. 
  Edit data as needed.

"""

def addMsgAndPrint(msg, severity=0): 
    # prints msg to screen and adds msg to the geoprocessor (in case this is run as a tool) 
    #print msg 
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

def createFeatureClass(thisDB,featureDataSet,featureClass,shapeType,fieldDefs):
    addMsgAndPrint('    Creating feature class '+featureClass+'...')
    try:
        arcpy.env.workspace = thisDB
        arcpy.CreateFeatureclass_management(featureDataSet,featureClass,shapeType)
        thisFC = thisDB+'/'+featureDataSet+'/'+featureClass
        for fDef in fieldDefs:
            try:
                if fDef[1] == 'String':
                    arcpy.AddField_management(thisFC,fDef[0],transDict[fDef[1]],'#','#',fDef[3],'#',transDict[fDef[2]])
                else:
                    arcpy.AddField_management(thisFC,fDef[0],transDict[fDef[1]],'#','#','#','#',transDict[fDef[2]])
            except:
                addMsgAndPrint('Failed to add field '+fDef[0]+' to feature class '+featureClass)
                addMsgAndPrint(arcpy.GetMessages(2))
    except:
        addMsgAndPrint(arcpy.GetMessages())
        addMsgAndPrint('Failed to create feature class '+featureClass+' in dataset '+featureDataSet)
        
        
def main(thisDB,coordSystem,nCrossSections):
	# create domains
	arcpy.CreateDomain_management(thisDB, 'd_Confidence', 'Confidence Terms', 'TEXT', 'CODED')
	arcpy.CreateDomain_management(thisDB, 'd_DataSources', 'Data Sources', 'TEXT', 'CODED')
	arcpy.CreateDomain_management(thisDB, 'd_StationIDs', 'Station Identifiers', 'TEXT', 'CODED')
	arcpy.CreateDomain_management(thisDB, 'd_YesNo', 'Yes and No', 'TEXT', 'CODED')
	# add coded values to d_Confidence domain
	arcpy.AddCodedValueToDomain_management(thisDB, 'd_Confidence', 'certain', 'certain')
	arcpy.AddCodedValueToDomain_management(thisDB, 'd_Confidence', 'questionable', 'questionable')
	arcpy.AddCodedValueToDomain_management(thisDB, 'd_Confidence', 'unspecified', 'unspecified')
	# add coded values to d_Confidence domain
	arcpy.AddCodedValueToDomain_management(thisDB, 'd_YesNo', 'Y', 'yes')
	arcpy.AddCodedValueToDomain_management(thisDB, 'd_YesNo', 'N', 'no')
	
	# create feature dataset GeologicMap
	addMsgAndPrint('  Creating feature dataset GeologicMap...')
	try:
		arcpy.CreateFeatureDataset_management(thisDB,'GeologicMap', coordSystem)
	except:
		addMsgAndPrint(arcpy.GetMessages(2))

	# create feature classes in GeologicMap
	# poly feature classes
	featureClasses = ['MapUnitPolys','DataSourcePolys','OtherPolys']
##	for fc in ['']:
##            if fc in OptionalElements:
##                featureClasses.append(fc)
	for featureClass in featureClasses:
            fieldDefs = tableDict[featureClass]
            createFeatureClass(thisDB,'GeologicMap',featureClass,'POLYGON',fieldDefs)
                
	# line feature classes
	featureClasses = ['ContactsAndFaults','GeologicLines','CartographicLines']
	for fc in ['IsoValueLines']:
            if fc in OptionalElements:
                featureClasses.append(fc)
	for featureClass in featureClasses:
            fieldDefs = tableDict[featureClass]
            if featureClass in ['ContactsAndFaults','GeologicLines'] and addLTYPE:
                fieldDefs.append(['LTYPE','String','NullsOK',255])
            createFeatureClass(thisDB,'GeologicMap',featureClass,'POLYLINE',fieldDefs)

	# point feature classes
	featureClasses = ['OrientationPoints','GeochronPoints','MapUnitPoints','Stations',
		      'GenericSamples','GenericPoints']
	for fc in ['FossilPoints']:
            if fc in OptionalElements:
                featureClasses.append(fc)
        for featureClass in featureClasses:
            if featureClass == 'MapUnitPoints': 
                fieldDefs = tableDict['MapUnitPolys']
            else:	
                fieldDefs = tableDict[featureClass]
                if addLTYPE and featureClass in ['OrientationPoints']:
                    fieldDefs.append(['PTTYPE','String','NullsOK',255])
            createFeatureClass(thisDB,'GeologicMap',featureClass,'POINT',fieldDefs)
	
	# topology
	try:
		arcpy.CreateTopology_management(thisDB + '//GeologicMap', 'GeologicMapTopology')
		arcpy.AddFeatureClassToTopology_management(thisDB+'//GeologicMap//GeologicMapTopology', thisDB+'//GeologicMap//ContactsAndFaults')
		arcpy.AddFeatureClassToTopology_management(thisDB+'//GeologicMap//GeologicMapTopology', thisDB+'//GeologicMap//MapUnitPolys')				
		arcpy.AddRuleToTopology_management(thisDB+'//GeologicMap//GeologicMapTopology', 'Must Not Overlap (Line)', thisDB+'//GeologicMap//ContactsAndFaults')
		arcpy.AddRuleToTopology_management(thisDB+'//GeologicMap//GeologicMapTopology', 'Must Not Self-Intersect (Line)', thisDB+'//GeologicMap//ContactsAndFaults')
		arcpy.AddRuleToTopology_management(thisDB+'//GeologicMap//GeologicMapTopology', 'Must Not Have Dangles (Line)', thisDB+'//GeologicMap//ContactsAndFaults')
		arcpy.AddRuleToTopology_management(thisDB+'//GeologicMap//GeologicMapTopology', 'Must Not Overlap (Area)',thisDB+'//GeologicMap//MapUnitPolys')
		arcpy.AddRuleToTopology_management(thisDB+'//GeologicMap//GeologicMapTopology', 'Must Not Have Gaps (Area)',thisDB+'//GeologicMap//MapUnitPolys')
		arcpy.AddRuleToTopology_management(thisDB+'//GeologicMap//GeologicMapTopology', 'Boundary Must Be Covered By (Area-Line)',thisDB+'//GeologicMap//MapUnitPolys', '#', thisDB+'//GeologicMap//ContactsAndFaults')
	except:
		pass

	# create feature dataset CorrelationOfMapUnits
	cmu = []
	for cmu in ['CorrelationOfMapUnits']:
		if cmu in OptionalElements:
			addMsgAndPrint('  Creating feature dataset CorrelationOfMapUnits...')
			arcpy.CreateFeatureDataset_management(thisDB,'CorrelationOfMapUnits', coordSystem)
			fieldDefs = tableDict['CMUMapUnitPolys']
			createFeatureClass(thisDB,'CorrelationOfMapUnits','CMUMapUnitPolys','POLYGON',fieldDefs)
			fieldDefs = tableDict['CMULines']
			createFeatureClass(thisDB,'CorrelationOfMapUnits','CMULines','POLYLINE',fieldDefs)
			fieldDefs = tableDict['CMUPoints']
			createFeatureClass(thisDB,'CorrelationOfMapUnits','CMUPoints','POINT',fieldDefs)      
		else:
			pass
	
		# create CrossSections
	if nCrossSections > 26:
	    nCrossSections = 26
	if nCrossSections < 0:
            nCrossSections = 0
	# note space in position 0
	alphabet = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ'
	
	for n in range(1,nCrossSections+1):
            xsLetter = alphabet[n]
            xsName = 'CrossSection'+xsLetter
            xsN = 'CS'+xsLetter
            #create feature dataset CrossSectionA
            addMsgAndPrint('  Creating feature data set CrossSection'+xsLetter+'...')
            arcpy.CreateFeatureDataset_management(thisDB,xsName, coordSystem)
            fieldDefs = tableDict['MapUnitPolys']
            fieldDefs[0][0] = xsN+'MapUnitPolys_ID'
            createFeatureClass(thisDB,xsName,xsN+'MapUnitPolys','POLYGON',fieldDefs)
            fieldDefs = tableDict['ContactsAndFaults']
            if addLTYPE:
                fieldDefs.append(['LTYPE','String','NullsOK',50])
            fieldDefs[0][0] = xsN+'ContactsAndFaults_ID'
            createFeatureClass(thisDB,xsName,xsN+'ContactsAndFaults','POLYLINE',fieldDefs)
            fieldDefs = tableDict['OrientationPoints']
            if addLTYPE:
                fieldDefs.append(['PTTYPE','String','NullsOK',50]) 
            fieldDefs[0][0] = xsN+'OrientationPoints_ID'
            createFeatureClass(thisDB,xsName,xsN+'OrientationPoints','POINT',fieldDefs)
            # if cartoReps = True, add cartographic representations to all feature classses
            if cartoReps:
                rootPath = os.path.dirname(sys.argv[0])
                addMsgAndPrint('  Adding cartographic representations to '+ xsN+'ContactsAndFaults...')
                try:
                        arcpy.AddRepresentation_cartography(thisDB + '//' + xsName + '//' + '//' + xsN+'ContactsAndFaults', xsN+'ContactsAndFaults' + "_Rep",'RuleID','Override',default, rootPath + '\\CartoReps\\ContactsAndFaults.lyr','NO_ASSIGN')
                except:
                        addMsgAndPrint(arcpy.GetMessages(2))
            else:
                pass

	# create tables
	tables = ['DescriptionOfMapUnits','DataSources','Glossary','StandardLithology','ExtendedAttributes','GeologicEvents','Notes','SysInfo']
	for tb in ['RepurposedSymbols']:
            if tb in OptionalElements:
                tables.append(tb)
	for table in tables:
            addMsgAndPrint('  Creating table '+table+'...')
            try:
                arcpy.CreateTable_management(thisDB,table)
                fieldDefs = tableDict[table]
                for fDef in fieldDefs:
                    try:
                        if fDef[1] == 'String':
                            arcpy.AddField_management(thisDB+'/'+table,fDef[0],transDict[fDef[1]],'#','#',fDef[3],'#',transDict[fDef[2]])
                        else:
                            arcpy.AddField_management(thisDB+'/'+table,fDef[0],transDict[fDef[1]],'#','#','#','#',transDict[fDef[2]])
                    except:
                        addMsgAndPrint('Failed to add field '+fDef[0]+' to table '+table)
                        addMsgAndPrint(arcpy.GetMessages(2))		    
            except:
                addMsgAndPrint(arcpy.GetMessages())
				
	# assign confidence domains to field
	fields = ['ExistenceConfidence','IdentityConfidence']
	arcpy.env.workspace = thisDB
	datasets = arcpy.ListDatasets()
	for dataset in datasets:
			arcpy.env.workspace = thisDB+'/'+dataset
			fcs = arcpy.ListFeatureClasses()
			for featureClass in fcs:
				field = arcpy.ListFields(featureClass)
				for field in fields:
					try:
						arcpy.AssignDomainToField_management(featureClass, field, 'd_Confidence')
						addMsgAndPrint('  Assigning domain to Existence Confidence and Identity Confidence fields, '+featureClass+ 'feature class ...')
					except:
						pass
						
	# assign data source domains to field - feature class
	fields = ['DataSourceID']
	arcpy.env.workspace = thisDB
	datasets = arcpy.ListDatasets()
	for dataset in datasets:
			arcpy.env.workspace = thisDB+'/'+dataset
			fcs = arcpy.ListFeatureClasses()
			for featureClass in fcs:
				field = arcpy.ListFields(featureClass)
				for field in fields:
					try:
						arcpy.AssignDomainToField_management(featureClass, field, 'd_DataSources')
						addMsgAndPrint('  Assigning domain to DataSourceID field, '+featureClass+ 'feature class ...')
					except:
						pass 
						
	# assign data source domains to field - tables
	fields = ['DataSourceID', 'DescriptionSourceID', 'DataSources_ID']
	arcpy.env.workspace = thisDB
	tables = arcpy.ListTables()
	for table in tables:
		field = arcpy.ListFields(table)
		for field in fields:
			try:
				arcpy.AssignDomainToField_management(table, field, 'd_DataSources')
				addMsgAndPrint('  Assigning domain to sources field, '+table+ 'table ...')
			except:
				pass
						
	# assign StationID domains to field
	fields = ['StationID']
	arcpy.env.workspace = thisDB
	datasets = arcpy.ListDatasets()
	for dataset in datasets:
			arcpy.env.workspace = thisDB+'/'+dataset
			fcs = arcpy.ListFeatureClasses()
			for featureClass in fcs:
				field = arcpy.ListFields(featureClass)
				for field in fields:
					try:
						arcpy.AssignDomainToField_management(featureClass, field, 'd_StationIDs')
						addMsgAndPrint('  Assigning domain to StationID field, '+ featureClass+ 'feature class ...')
					except:
						pass
						
	# assign isConcealed domains to field
	fields = ['IsConcealed']
	arcpy.env.workspace = thisDB
	datasets = arcpy.ListDatasets()
	for dataset in datasets:
			arcpy.env.workspace = thisDB+'/'+dataset
			fcs = arcpy.ListFeatureClasses()
			for featureClass in fcs:
				field = arcpy.ListFields(featureClass)
				for field in fields:
					try:
						arcpy.AssignDomainToField_management(featureClass, field, 'd_YesNo')
						addMsgAndPrint('  Assigning domain to isConcealed field, '+ featureClass+ 'feature class ...')
					except:
						pass

	# if cartoReps = True, add cartographic representations to all feature classses
	featureClasses = ['ContactsAndFaults', 'GeologicLines', 'OrientationPoints']
	rootPath = os.path.dirname(sys.argv[0])
	if cartoReps:
		arcpy.env.workspace = thisDB
		datasets = arcpy.ListDatasets()
		for dataset in datasets:
			arcpy.env.workspace = thisDB+'/'+dataset
			fcs = arcpy.ListFeatureClasses()
			for fc in fcs:
				for i in featureClasses:
					if fc == i:
						newPath = rootPath + '\\CartoReps\\' + fc + '.lyr'
						addMsgAndPrint('  Adding cartographic representations to '+ fc)
						try:
							arcpy.AddRepresentation_cartography(fc, fc + "_Rep",'RuleID','Override',default,newPath,'NO_ASSIGN')
						except:
							addMsgAndPrint(arcpy.GetMessages(2))
					else:
						pass                                           

def createDatabase(outputDir,thisDB):
    addMsgAndPrint('  Creating geodatabase '+thisDB+'...')		
    try:
        if thisDB[-4:] == '.mdb':
            arcpy.CreatePersonalGDB_management(outputDir,thisDB)
        if thisDB[-4:] == '.gdb':
            arcpy.CreateFileGDB_management(outputDir,thisDB)
        return True
    except:
        addMsgAndPrint('Failed to create geodatabase '+outputDir+'/'+thisDB)
        addMsgAndPrint(arcpy.GetMessages(2))
        return False

#########################################
    
addMsgAndPrint(versionString)

if len(sys.argv) >= 6:
    addMsgAndPrint('Starting script')

    try:
        outputDir = sys.argv[1]
        if outputDir == '#':
            outputDir = os.getcwd()
        outputDir = outputDir.replace('\\','/')

        thisDB = sys.argv[2]
        # test for extension; if not given, default to personal geodatabase
        if not thisDB[-4:].lower() in ('.gdb','.mdb'):
            thisDB = thisDB+'.gdb'

        coordSystem = sys.argv[3]

        if sys.argv[4] == '#':
            OptionalElements = []
        else:
            OptionalElements = sys.argv[4].split(';')
        
        nCrossSections = int(sys.argv[5])

        try:
            if sys.argv[6] == 'true':
                cartoReps = True
            else:
                cartoReps = False
        except:
            cartoReps = False

        try:
            if sys.argv[7] == 'true':
                addLTYPE = True
            else:
                addLTYPE = False
        except:
            addLTYPE = False
            
        # create personal gdb in output directory and run main routine
        if createDatabase(outputDir,thisDB):
            thisDB = outputDir+'/'+thisDB
            arcpy.RefreshCatalog(thisDB)
            main(thisDB,coordSystem,nCrossSections)
    
        # try to write a readme within the .gdb
        if thisDB[-4:] == '.gdb':
            try:
                arcpy.env.workspace = ''
                versionFile = open(thisDB+'/00readme.txt','w')
                versionFile.write('Geodatabase created by '+versionString+'\n')
                versionFile.close()
            except:
                addMsgAndPrint('Failed to write '+thisDB+'/00readme.txt')

    except:
	addMsgAndPrint('Failed.')
else:
    addMsgAndPrint(usage)
