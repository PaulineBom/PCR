#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# PCR-GLOBWB (PCRaster Global Water Balance) Global Hydrological Model
#
# Copyright (C) 2016, Ludovicus P. H. (Rens) van Beek, Edwin H. Sutanudjaja, Yoshihide Wada,
# Joyce H. C. Bosmans, Niels Drost, Inge E. M. de Graaf, Kor de Jong, Patricia Lopez Lopez,
# Stefanie Pessenteiner, Oliver Schmitz, Menno W. Straatsma, Niko Wanders, Dominik Wisser,
# and Marc F. P. Bierkens,
# Faculty of Geosciences, Utrecht University, Utrecht, The Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import shutil
import datetime

import pcraster as pcr
from pcraster.framework import DynamicModel
from pcraster.framework import DynamicFramework

from configuration import Configuration
from currTimeStep import ModelTime
from reporting import Reporting
from spinUp import SpinUp

from pcrglobwb import PCRGlobWB

import logging
logger = logging.getLogger(__name__)

import disclaimer

class DeterministicRunner(DynamicModel):

    def __init__(self, configuration, modelTime, initialState = None, system_argument = None):
        DynamicModel.__init__(self)

        self.modelTime = modelTime        
        self.model = PCRGlobWB(configuration, modelTime, initialState)
        self.reporting = Reporting(configuration, self.model, modelTime)
        
        # the model paramaters may be modiffied
        if ((system_argument != None) or ("-adjparm" in list(system_argument)) or ('prefactorOptions' in configuration.allSections)): 
            self.adusting_parameters(configuration, system_argument)

        # option to include merging processes for pcraster maps and netcdf files:
        self.with_merging = True
        if ('with_merging' in configuration.globalOptions.keys()) and (configuration.globalOptions['with_merging'] == "False"):
            self.with_merging = False

        # make the configuration available for the other method/function
        self.configuration = configuration
        
        
    def adusting_parameters(self, configuration, system_argument): 

        # global pre-multipliers given in the argument:
        if "-adjparm" in list(system_argument):
            
            # starting adjustment index (sai)
            sai = system_argument.index("-adjparm")
            
            logger.info("Adjusting some model parameters based on given values in the system argument.")

		    # pre-multipliers for minSoilDepthFrac, kSat, recessionCoeff, storCap and degreeDayFactor
            multiplier_for_minSoilDepthFrac = float(system_argument[sai + 1])  # linear scale
            multiplier_for_kSat             = float(system_argument[sai + 2])  # log scale
            multiplier_for_recessionCoeff   = float(system_argument[sai + 3])  # log scale
            multiplier_for_storCap          = float(system_argument[sai + 4])  # linear scale
            multiplier_for_degreeDayFactor  = float(system_argument[sai + 5])  # linear scale
		    
		    # pre-multiplier for the reference potential ET
            self.multiplier_for_refPotET    = float(system_argument[sai + 6])  # linear scale
        
		    # pre-multiplier for manningsN
            multiplier_for_manningsN        = float(system_argument[sai + 7]) # linear scale
            
            # modification for storGroundwaterIni
            storGroundwaterIni_file         =   str(system_argument[sai + 8])

        # it is also possible to define prefactors via the ini/configuration file: 
        # - this will be overwrite any previous given pre-multipliers
        if 'prefactorOptions' in configuration.allSections:
            
            logger.info("Adjusting some model parameters based on given values in the ini/configuration file.")

            self.multiplier_for_refPotET    = float(configuration.prefactorOptions['linear_multiplier_for_refPotET'        ])  # linear scale  # Note that this one does NOT work for the changing WMIN or Joyce land cover options.
            multiplier_for_degreeDayFactor  = float(configuration.prefactorOptions['linear_multiplier_for_degreeDayFactor' ])  # linear scale
            multiplier_for_minSoilDepthFrac = float(configuration.prefactorOptions['linear_multiplier_for_minSoilDepthFrac'])  # linear scale
            multiplier_for_kSat             = float(configuration.prefactorOptions['log_10_multiplier_for_kSat'            ])  # log scale
            multiplier_for_storCap          = float(configuration.prefactorOptions['linear_multiplier_for_storCap'         ])  # linear scale
            multiplier_for_recessionCoeff   = float(configuration.prefactorOptions['log_10_multiplier_for_recessionCoeff'  ])  # log scale
            multiplier_for_manningsN        = float(configuration.prefactorOptions['multiplier_for_manningsN'              ])  # linear scale
            
            storGroundwaterIni_file = str(configuration.prefactorOptions['storGroundwaterIni_file'])  # file location (please use full path)
        
        # saving global pre-multipliers to the log file:
        msg  = "\n" 
        msg += "\n" 
        msg += "Multiplier values used: "+"\n" 
        msg += "For minSoilDepthFrac           : "+str(multiplier_for_minSoilDepthFrac)+"\n"
        msg += "For kSat (log-scale)           : "+str(multiplier_for_kSat            )+"\n"
        msg += "For recessionCoeff (log-scale) : "+str(multiplier_for_recessionCoeff  )+"\n"
        msg += "For storCap                    : "+str(multiplier_for_storCap         )+"\n"
        msg += "For degreeDayFactor            : "+str(multiplier_for_degreeDayFactor )+"\n"
        msg += "For refPotET                   : "+str(self.multiplier_for_refPotET   )+"\n"
        msg += "For multiplier_for_manningsN   : "+str(multiplier_for_manningsN       )+"\n"
        msg += "For storGroundwaterIni_file    : "+str(storGroundwaterIni_file        )+"\n"
        logger.info(msg)
        # - also to a txt file 
        f = open("multiplier.txt", "w") # this will be stored in the "map" folder of the 'outputDir' (as we set the current working directory to this "map" folder, see configuration.py)
        f.write(msg)
        f.close()

        # adjust storGroundwaterIni
        if storGroundwaterIni_file != "Default":
            #~ self.model.groundwater.storGroundwater = pcr.readmap(storGroundwaterIni_file)
            self.model.groundwater.storGroundwater    = vos.readPCRmapClone(storGroundwaterIni_file,\
                                                                            configuration.cloneMap,\
                                                                            configuration.tmpDir)
            self.model.groundwater.storGroundwater    = pcr.ifthen(self.landmask, \
                                                                   pcr.cover(self.model.groundwater.storGroundwater, 0.0))
        pcr.report(self.model.groundwater.storGroundwater, "storGroundwaterIni.map") 
        
        # set parameter "manningsN" based on the given pre-multiplier
        # - also saving the adjusted parameter maps to pcraster files
        # - these will be stored in the "map" folder of the 'outputDir' (as we set the current working directory to this "map" folder, see configuration.py)
        # "manningsN"
        # minimum value is zero and using log-scale
        self.model.routing.manningsN = multiplier_for_manningsN * self.model.routing.manningsN
        # report the map
        pcr.report(self.model.routing.manningsN, "manningsN.map")

        # set parameter "recessionCoeff" based on the given pre-multiplier
        # - also saving the adjusted parameter maps to pcraster files
        # - these will be stored in the "map" folder of the 'outputDir' (as we set the current working directory to this "map" folder, see configuration.py)
        # "recessionCoeff"
        # minimum value is zero and using log-scale
        self.model.groundwater.recessionCoeff = pcr.max(0.0, (10**(multiplier_for_recessionCoeff)) * self.model.groundwater.recessionCoeff)
        self.model.groundwater.recessionCoeff = pcr.min(1.0, self.model.groundwater.recessionCoeff)
        # report the map
        pcr.report(self.model.groundwater.recessionCoeff, "recessionCoeff.map")
        
        # set parameters "kSat", "storCap", "minSoilDepthFrac", and "degreeDayFactor" based on the given pre-multipliers
        for coverType in self.model.landSurface.coverTypes:

            # "degreeDayFactor"
            self.model.landSurface.landCoverObj[coverType].degreeDayFactor  = pcr.max(0.0, multiplier_for_degreeDayFactor  *\
                                                           self.model.landSurface.landCoverObj[coverType].degreeDayFactor)
            # report the map
            pcraster_filename = "degreeDayFactor" + "_" + coverType + ".map" 
            pcr.report(self.model.landSurface.landCoverObj[coverType].degreeDayFactor , pcraster_filename)

            # "kSat" and "storCap" for 2 layer model
            if self.model.landSurface.numberOfSoilLayers == 2:

                # "kSat"
			    # minimum value is zero and using-log-scale
                self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp = \
                       pcr.max(0.0, (10**(multiplier_for_kSat)) * self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp)
                self.model.landSurface.landCoverObj[coverType].parameters.kSatLow = \
                       pcr.max(0.0, (10**(multiplier_for_kSat)) * self.model.landSurface.landCoverObj[coverType].parameters.kSatLow)
                # report the maps
                pcraster_filename = "kSatUpp"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp, pcraster_filename)
                pcraster_filename = "kSatLow"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.kSatLow, pcraster_filename)

                # "storCap"
                # minimum value is zero
                self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp = pcr.max(0.0, multiplier_for_storCap*\
                                                                                                    self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp)
                self.model.landSurface.landCoverObj[coverType].parameters.storCapLow = pcr.max(0.0, multiplier_for_storCap*\
                                                                                                    self.model.landSurface.landCoverObj[coverType].parameters.storCapLow)
                # report the maps
                pcraster_filename = "storCapUpp"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp, pcraster_filename)
                pcraster_filename = "storCapLow"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.storCapLow, pcraster_filename)
            
            # "kSat" and "storCap" for 3 layer model
            if self.model.landSurface.numberOfSoilLayers == 3:

                # "kSat"
			    # minimum value is zero and using-log-scale
                self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp000005 = \
                       pcr.max(0.0, (10**(multiplier_for_kSat)) * self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp000005)
                self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp005030 = \
                       pcr.max(0.0, (10**(multiplier_for_kSat)) * self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp005030)
                self.model.landSurface.landCoverObj[coverType].parameters.kSatLow030150 = \
                       pcr.max(0.0, (10**(multiplier_for_kSat)) * self.model.landSurface.landCoverObj[coverType].parameters.kSatLow030150)
                # report the maps
                pcraster_filename = "kSatUpp000005"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp000005, pcraster_filename)
                pcraster_filename = "kSatUpp005030"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.kSatUpp005030, pcraster_filename)
                pcraster_filename = "kSatLow030150"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.kSatLow030150, pcraster_filename)

                # "storCap"
                # minimum value is zero
                self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp000005 = pcr.max(0.0, multiplier_for_storCap*\
                                                                                                          self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp000005)
                self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp005030 = pcr.max(0.0, multiplier_for_storCap*\
                                                                                                          self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp005030)
                self.model.landSurface.landCoverObj[coverType].parameters.storCapLow030150 = pcr.max(0.0, multiplier_for_storCap*\
                                                                                                          self.model.landSurface.landCoverObj[coverType].parameters.storCapLow030150)
                # report the maps
                pcraster_filename = "storCapUpp000005"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp000005, pcraster_filename)
                pcraster_filename = "storCapUpp005030"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp005030, pcraster_filename)
                pcraster_filename = "storCapLow030150"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.storCapLow030150, pcraster_filename)


			# re-calculate rootZoneWaterStorageCap as the consequence of the modification of "storCap"
            # This is WMAX in the oldcalc script.
            if self.model.landSurface.numberOfSoilLayers == 2:
                self.model.landSurface.landCoverObj[coverType].parameters.rootZoneWaterStorageCap = self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp +\
                                                                                                    self.model.landSurface.landCoverObj[coverType].parameters.storCapLow
            if self.model.landSurface.numberOfSoilLayers == 3:
                self.model.landSurface.landCoverObj[coverType].parameters.rootZoneWaterStorageCap = self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp000005 +\
                                                                                                    self.model.landSurface.landCoverObj[coverType].parameters.storCapUpp005030 +\
																									self.model.landSurface.landCoverObj[coverType].parameters.storCapLow030150
			# report the map
            pcraster_filename = "rootZoneWaterStorageCap"+ "_" + coverType + ".map" 
            pcr.report(self.model.landSurface.landCoverObj[coverType].parameters.rootZoneWaterStorageCap, pcraster_filename)
            
            # "minSoilDepthFrac"
            if multiplier_for_minSoilDepthFrac != 1.0:
                
                # minimum value is zero
                self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac = pcr.max(0.0, multiplier_for_minSoilDepthFrac*\
                                                               self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac)
                # for minSoilDepthFrac - values will be limited by maxSoilDepthFrac
                self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac = pcr.min(\
                                                               self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac,\
                                                               self.model.landSurface.landCoverObj[coverType].maxSoilDepthFrac)
                # maximum value is 1.0
                self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac = pcr.min(1.0, self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac)
                # report the map
                pcraster_filename = "minSoilDepthFrac"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac, pcraster_filename)
                
                # re-calculate arnoBeta (as the consequence of the modification of minSoilDepthFrac)
                self.model.landSurface.landCoverObj[coverType].arnoBeta = pcr.max(0.001,\
                     (self.model.landSurface.landCoverObj[coverType].maxSoilDepthFrac-1.)/(1.-self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac)+\
                                               self.model.landSurface.landCoverObj[coverType].parameters.orographyBeta-0.01)
                self.model.landSurface.landCoverObj[coverType].arnoBeta = pcr.cover(pcr.max(0.001,\
                      self.model.landSurface.landCoverObj[coverType].arnoBeta), 0.001)
                # report the map
                pcraster_filename = "arnoBeta"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].arnoBeta, pcraster_filename)
                
                # re-calculate rootZoneWaterStorageMin (as the consequence of the modification of minSoilDepthFrac)
                # This is WMIN in the oldcalc script.
                # WMIN (unit: m): minimum local soil water capacity within the grid-cell
                self.model.landSurface.landCoverObj[coverType].rootZoneWaterStorageMin = self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac *\
                                                                                         self.model.landSurface.landCoverObj[coverType].parameters.rootZoneWaterStorageCap 
                # report the map
                pcraster_filename = "rootZoneWaterStorageMin"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].rootZoneWaterStorageMin, pcraster_filename)
                
                # re-calculate rootZoneWaterStorageRange (as the consequence of the modification of rootZoneWaterStorageRange and minSoilDepthFrac)
                # WMAX - WMIN (unit: m)
                self.model.landSurface.landCoverObj[coverType].rootZoneWaterStorageRange = self.model.landSurface.landCoverObj[coverType].parameters.rootZoneWaterStorageCap -\
                                                                                           self.model.landSurface.landCoverObj[coverType].rootZoneWaterStorageMin
                # report the map
                pcraster_filename = "rootZoneWaterStorageRange"+ "_" + coverType + ".map" 
                pcr.report(self.model.landSurface.landCoverObj[coverType].rootZoneWaterStorageRange, pcraster_filename)

    def initial(self): 
        pass

    def dynamic(self):

        # re-calculate current model time using current pcraster timestep value
        self.modelTime.update(self.currentTimeStep())

        # read model forcing (will pick up current model time from model time object)
        self.model.read_forcings()
        
		# adjust the reference potential ET according to the given pre-multiplier
        self.model.meteo.referencePotET = self.model.meteo.referencePotET * self.multiplier_for_refPotET
		
        # update model (will pick up current model time from model time object)
        # - for a run coupled to MODFLOW, water balance checks are not valid due to lateral flow. 
        if self.configuration.online_coupling_between_pcrglobwb_and_modflow:
            self.model.update(report_water_balance = False)
        else:
            self.model.update(report_water_balance = True)
		
        # do any needed reporting for this time step        
        self.reporting.report()

        # at the last day of the month, stop calculation until modflow and related merging process are ready (only for a run with modflow) 
        if self.modelTime.isLastDayOfMonth() and (self.configuration.online_coupling_between_pcrglobwb_and_modflow or\
                                                  self.with_merging):
            
            # wait until modflow files are ready
            if self.configuration.online_coupling_between_pcrglobwb_and_modflow:
                modflow_is_ready = False
                self.count_check = 0
                while modflow_is_ready == False:
                    if datetime.datetime.now().second == 14 or\
                       datetime.datetime.now().second == 29 or\
                       datetime.datetime.now().second == 34 or\
                       datetime.datetime.now().second == 59:\
                       modflow_is_ready = self.check_modflow_status()
                
            # wait until merged files are ready
            merged_files_are_ready = False
            while merged_files_are_ready == False:
                self.count_check = 0
                if datetime.datetime.now().second == 14 or\
                   datetime.datetime.now().second == 29 or\
                   datetime.datetime.now().second == 34 or\
                   datetime.datetime.now().second == 59:\
                   merged_files_are_ready = self.check_merging_status()

    def check_modflow_status(self):

        status_file = str(self.configuration.main_output_directory) + "/modflow/transient/maps/modflow_files_for_" + str(self.modelTime.fulldate) + "_are_ready.txt"
        msg = 'Waiting for the file: ' + status_file
        if self.count_check == 1: logger.info(msg)
        if self.count_check < 7:
            #~ logger.debug(msg)			# INACTIVATE THIS AS THIS MAKE A HUGE DEBUG (dbg) FILE
            self.count_check += 1
        status = os.path.exists(status_file)
        if status == False: return status	
        if status: self.count_check = 0            
        return status

    def check_merging_status(self):

        status_file = str(self.configuration.main_output_directory) + "/global/maps/merged_files_for_"    + str(self.modelTime.fulldate) + "_are_ready.txt"
        msg = 'Waiting for the file: ' + status_file
        if self.count_check == 1: logger.info(msg)
        if self.count_check < 7:
            #~ logger.debug(msg)			# INACTIVATE THIS AS THIS MAKE A HUGE DEBUG (dbg) FILE
            self.count_check += 1
        status = os.path.exists(status_file)
        if status == False: return status	
        if status: self.count_check = 0            
        return status
 
 
def modify_ini_file(original_ini_file,
                    system_argument): 

    # created by Edwin H. Sutanudjaja on August 2020 for the Ulysses project
    
    # open and read ini file
    file_ini = open(original_ini_file, "rt")
    file_ini_content = file_ini.read()
    file_ini.close()
    
    # system argument for replacing outputDir (-mod) ; this is always required
    main_output_dir = system_argument[system_argument.index("-mod") + 1]
    file_ini_content = file_ini_content.replace("MAIN_OUTPUT_DIR", main_output_dir)
    msg = "The output folder 'outputDir' is set based on the system argument (-mod): " + main_output_dir
    logger.info(msg)
    
    # optional system arguments for modifying startTime (-sd) and endTime (-ed)
    if "-sd" in system_argument:
        starting_date = system_argument[system_argument.index("-sd") + 1]
        file_ini_content = file_ini_content.replace("STARTING_DATE", starting_date)
        msg = "The starting date 'startTime' is set based on the system argument (-sd): " + starting_date
        logger.info(msg)
    if "-ed" in system_argument:
        end_date = system_argument[system_argument.index("-ed") + 1]
        file_ini_content = file_ini_content.replace("END_DATE", end_date)
        msg = "The end date 'END_DATE' is set based on the system argument (-ed): " + end_date
        logger.info(msg)
        
    # optional system arguments for initial condition files
    # - main initial state folder
    if "-misd" in system_argument:
        main_initial_state_folder = system_argument[system_argument.index("-misd") + 1]        
        file_ini_content = file_ini_content.replace("MAIN_INITIAL_STATE_FOLDER", main_initial_state_folder)
        msg = "The main folder for all initial states is set based on the system argument (-misd): " + main_initial_state_folder
        logger.info(msg)
    # - date for initial states 
    if "-dfis" in system_argument:
        date_for_initial_state = system_argument[system_argument.index("-dfis") + 1]        
        file_ini_content = file_ini_content.replace("DATE_FOR_INITIAL_STATE", date_for_initial_state)
        msg = "The date for all initial state files is set based on the system argument (-dfis): " + date_for_initial_state
        logger.info(msg)
    
    # optional system argument for modifying forcing files
    if "-pff" in system_argument:
        precipitation_forcing_file = system_argument[system_argument.index("-pff") + 1]
        file_ini_content = file_ini_content.replace("PRECIPITATION_FORCING_FILE", precipitation_forcing_file)
        msg = "The precipitation forcing file 'precipitationNC' is set based on the system argument (-pff): " + precipitation_forcing_file
        logger.info(msg)
    if "-tff" in system_argument:
        temperature_forcing_file = system_argument[system_argument.index("-tff") + 1]
        file_ini_content = file_ini_content.replace("TEMPERATURE_FORCING_FILE", temperature_forcing_file)
        msg = "The temperature forcing file 'temperatureNC' is set based on the system argument (-tff): " + temperature_forcing_file
        logger.info(msg)
    if "-rpetff" in system_argument:
        ref_pot_et_forcing_file = system_argument[system_argument.index("-rpetff") + 1]
        file_ini_content = file_ini_content.replace("REF_POT_ET_FORCING_FILE", ref_pot_et_forcing_file)
        msg = "The reference potential ET forcing file 'refETPotFileNC' is set based on the system argument (-tff): " + ref_pot_et_forcing_file
        logger.info(msg)

    # folder for saving original and modified ini files
    folder_for_ini_files = os.path.join(main_output_dir, "ini_files")
    # - for a run that is part of a set of parallel (clone) runs
    if system_argument[2] == "parallel" or system_argument[2] == "debug_parallel" or system_argument[2] == "debug-parallel":
        clone_code = str(system_argument[3])
        output_folder_with_clone_code = "M%07i" %int(clone_code)
        folder_for_ini_files = os.path.join(main_output_dir, output_folder_with_clone_code, "ini_files") 
    
   # create folder
    if os.path.exists(folder_for_ini_files): shutil.rmtree(folder_for_ini_files)
    os.makedirs(folder_for_ini_files)
    
    # save/copy the original ini file
    shutil.copy(original_ini_file, os.path.join(folder_for_ini_files, os.path.basename(original_ini_file) + ".original"))
    
    # save the new ini file
    new_ini_file_name = os.path.join(folder_for_ini_files, os.path.basename(original_ini_file) + ".modified_and_used")
    new_ini_file = open(new_ini_file_name, "w")
    new_ini_file.write(file_ini_content)
    new_ini_file.close()
            
    return new_ini_file_name


def main():
    
    # get the full path of configuration/ini file given in the system argument
    iniFileName   = os.path.abspath(sys.argv[1])
    
    # modify ini file and return it in a new location 
    if "-mod" in sys.argv:
        iniFileName = modify_ini_file(original_ini_file = iniFileName, \
                                      system_argument = sys.argv)
    
    # debug option
    debug_mode = False
    if len(sys.argv) > 2: 
        if sys.argv[2] == "debug" or sys.argv[2] == "debug_parallel" or sys.argv[2] == "debug-parallel": debug_mode = True
    
    # parallel option
    this_run_is_part_of_a_set_of_parallel_run = False    
    if len(sys.argv) > 2: 
        if sys.argv[2] == "parallel" or sys.argv[2] == "debug_parallel" or sys.argv[2] == "debug-parallel": this_run_is_part_of_a_set_of_parallel_run = True

    # object to handle configuration/ini file
    configuration = Configuration(iniFileName = iniFileName, \
                                  debug_mode = debug_mode, \
                                  no_modification = False)      

    
    # for a non parallel run (usually 30min), a specific directory given in the system argument (sys.argv[3]) will be assigned for a given parameter combination:
    if this_run_is_part_of_a_set_of_parallel_run == False:
        # modfiying 'outputDir' (based on the given system argument)
        configuration.globalOptions['outputDir'] += "/"+str(sys.argv[3])+"/" 

    # for a parallel run (e.g. usually for 5min and 6min runs), we assign a specific directory based on the clone number/code:
    if this_run_is_part_of_a_set_of_parallel_run:
        # modfiying outputDir, clone-map landmask, etc (based on the given system arguments)
        # - clone code in string
        clone_code = str(sys.argv[3])
        # - output folder
        output_folder_with_clone_code = "M%07i" %int(clone_code)
        configuration.globalOptions['outputDir'] += output_folder_with_clone_code 
        # - clone map
        configuration.globalOptions['cloneMap'] = configuration.globalOptions['cloneMap'] %(clone_code)
        # - landmask for model calculation
        if configuration.globalOptions['landmask'] != "None":
            configuration.globalOptions['landmask']   = configuration.globalOptions['landmask'] %(clone_code)
        # - landmask for reporting
        if configuration.reportingOptions['landmask_for_reporting'] != "None":
            configuration.reportingOptions['landmask_for_reporting'] = configuration.reportingOptions['landmask_for_reporting'] %(clone_code)

    # set configuration
    configuration.set_configuration(system_arguments = sys.argv)
    
    #~ UNTIL_THIS_PART
    
#~ 
    #~ # timeStep info: year, month, day, doy, hour, etc
    #~ currTimeStep = ModelTime() 
#~ 
    #~ # object for spin_up
    #~ spin_up = SpinUp(configuration)            
    #~ 
    #~ # spinning-up 
    #~ noSpinUps = int(configuration.globalOptions['maxSpinUpsInYears'])
    #~ initial_state = None
    #~ if noSpinUps > 0:
        #~ 
        #~ logger.info('Spin-Up #Total Years: '+str(noSpinUps))
#~ 
        #~ spinUpRun = 0 ; has_converged = False
        #~ while spinUpRun < noSpinUps and has_converged == False:
            #~ spinUpRun += 1
            #~ currTimeStep.getStartEndTimeStepsForSpinUp(
                    #~ configuration.globalOptions['startTime'],
                    #~ spinUpRun, noSpinUps)
            #~ logger.info('Spin-Up Run No. '+str(spinUpRun))
            #~ deterministic_runner = DeterministicRunner(configuration, currTimeStep, initial_state, sys.argv)
            #~ 
            #~ all_state_begin = deterministic_runner.model.getAllState() 
            #~ 
            #~ dynamic_framework = DynamicFramework(deterministic_runner,currTimeStep.nrOfTimeSteps)
            #~ dynamic_framework.setQuiet(True)
            #~ dynamic_framework.run()
            #~ 
            #~ all_state_end = deterministic_runner.model.getAllState() 
            #~ 
            #~ has_converged = spin_up.checkConvergence(all_state_begin, all_state_end, spinUpRun, deterministic_runner.model.routing.cellArea)
            #~ 
            #~ initial_state = deterministic_runner.model.getState()
    #~ #
    #~ # Running the deterministic_runner (excluding DA scheme)
    #~ currTimeStep.getStartEndTimeSteps(configuration.globalOptions['startTime'],
                                      #~ configuration.globalOptions['endTime'])
    #~ 
    #~ logger.info('Transient simulation run started.')
    #~ deterministic_runner = DeterministicRunner(configuration, currTimeStep, initial_state, sys.argv)
    #~ 
    #~ dynamic_framework = DynamicFramework(deterministic_runner,currTimeStep.nrOfTimeSteps)
    #~ dynamic_framework.setQuiet(True)
    #~ dynamic_framework.run()

if __name__ == '__main__':
    # print disclaimer
    disclaimer.print_disclaimer(with_logger = True)
    sys.exit(main())
