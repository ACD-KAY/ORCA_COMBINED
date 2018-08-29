from __future__ import division
import numpy as np 
import pandas as pd
import json
from .util import *

class Contract():

  def __init__(self, df, key):
    self.T = len(df)
    self.index = df.index
    self.key = key

    for k,v in json.load(open('cord/contracts/%s_properties.json' % key)).items():
        setattr(self,k,v)
	
	#daily state variables for contract allocation & availability
    self.allocation = np.zeros(self.T)
    self.storage_pool = np.zeros(self.T)
    self.available_water = np.zeros(self.T)
	
    #keep track of deliveries made daily/annually from the contract
    self.annual_deliveries = np.zeros((self.index.year[self.T-1]-self.index.year[0]))
    self.flood_deliveries = np.zeros((self.index.year[self.T-1]-self.index.year[0]))
    self.daily_deliveries = 0.0
	
    self.tot_carryover = 0.0#contract carryover
    self.lastYearForecast = self.maxForecastValue#last year's allocation forecast (used to make forecast during the beginning of the year)
    self.projected_carryover = 0.0#projecting the carryover storage for next year (based on individual district storage accounts)
    self.max_allocation = self.total#full allocation for the contract
    self.tot_new_alloc = 0.0#carryover water that is transferred to next year's allocation (rather than district carryover)
	
	#dictionaries to keep track of data for output
    self.daily_supplies = {}
    self.annual_supplies = {}
    supply_types = ['contract', 'carryover', 'turnback', 'flood']
    for x in supply_types:
      self.daily_supplies[x] = np.zeros(self.T)
      self.annual_supplies[x] = np.zeros((self.index.year[self.T-1]-self.index.year[0]))


  def calc_allocation(self, t, dowy, forecast_available, priority_allocation, secondary_allocation, wyt):
    #this function calculates the contract allocation based on snowpack-based flow forecast
	#before March, allocations are assumed to be equal to last year's allocation (capped at some level)
	#unless the snowpack is large enough to expect larger flows (i.e., low snowpack early in the year doesn't
	#cause contracts to predict super-low allocations
    #if dowy < 150:
      #if forecast_available > self.maxForecastValue:
        #if self.allocation_priority == 1:
          #forecast_used = forecast_available*self.total/priority_allocation
        #else:#if the contract doesn't have priority, the allocation is the available water minus all priority allocations
          #forecast_used = (forecast_available - priority_allocation)*self.total/secondary_allocation
      #elif self.lastYearForecast < forecast_available:
        #if self.allocation_priority == 1:
          #forecast_used = forecast_available*self.total/priority_allocation
        #else:#if the contract doesn't have priority, the allocation is the available water minus all priority allocations
          #forecast_used = (forecast_available - priority_allocation)*self.total/secondary_allocation
      #else:
        #if self.allocation_priority == 1:
          #forecast_used = min(self.lastYearForecast, self.maxForecastValue)*self.total/priority_allocation
          #forecast_used = forecast_available*self.total/priority_allocation
        #else:#if the contract doesn't have priority, the allocation is the available water minus all priority allocations
          #forecast_used = (forecast_available - priority_allocation)*self.total/secondary_allocation
          #forecast_used = (min(self.lastYearForecast, self.maxForecastValue)- priority_allocation)*self.total/secondary_allocation
    #else:
      #if the contract has priority, the allocation is just the available (forecasted) water
    if self.allocation_priority == 1:
      forecast_used = forecast_available*self.total/priority_allocation
    else:#if the contract doesn't have priority, the allocation is the available water minus all priority allocations
      forecast_used = (forecast_available - priority_allocation)*self.total/secondary_allocation
    
    if dowy == 360:
      forecast_used = forecast_available
      self.lastYearForecast = forecast_available
      #if self.lastYearForecast > self.maxForecastValue:
        #self.lastYearForecast = self.maxForecastValue
    if forecast_used > self.max_allocation:
      forecast_used = self.max_allocation
	  
    self.allocation[t] = min(forecast_used,self.total*self.reduction[wyt])
	
  def find_storage_pool(self, t, wateryear, total_water, reservoir_storage, priority_storage):
    #this function finds the storage pool for each contract, given the 'total water'
	#that has come into a given reservoir (storage + deliveries) and the total priority
	#storage that must be filled before this contract's storage
    if self.storage_priority == 1:
      #what is the fraction of the allocation that is available to the contract right now
	  #all contracts with priority storage share the 'total_water' - i.e. if 1/2 of the priority storage
	  #has already come into the reservoir, then 1/2 of the contract's allocation is 'currently available'
      self.storage_pool[t] = min(1.0, total_water/priority_storage)*(self.allocation[t] + self.tot_carryover)
      self.available_water[t] = reservoir_storage * (self.allocation[t] + self.tot_carryover)/priority_storage
    else:
      #if the contract doesn't have priority, the contract has to wait for the total_water to be greater than the
	  #priority storage before any of that water is available to them
      self.storage_pool[t] = min(self.allocation[t] + self.tot_carryover, max(total_water - priority_storage, 0.0))
      self.available_water[t] = min(total_water - priority_storage, self.allocation[t] + self.tot_carryover, reservoir_storage)
	  
  def adjust_accounts(self, contract_deliveries, search_type, wateryear):
    #this function records deliveries made on a contract by year - for use in determining if 
    if search_type == "flood":
      self.flood_deliveries[wateryear] += contract_deliveries
    else:
      self.annual_deliveries[wateryear] += contract_deliveries
      self.daily_deliveries += contract_deliveries
	  
  def accounting(self, t, da, m, wateryear, deliveries, carryover, turnback, flood):
    contract_deliveries = max(deliveries - max(carryover, 0.0) - max(turnback, 0.0), 0.0)
    carryover_deliveries = max(min(carryover, deliveries), 0.0)
    turnback_deliveries = max(min(turnback, deliveries - carryover), 0.0)
    flood_deliveries = flood
	
	#we want to 'stack' the different kinds of deliveries for plotting in an area chart
    self.daily_supplies['contract'][t] += contract_deliveries
    self.daily_supplies['carryover'][t] += carryover_deliveries + contract_deliveries
    self.daily_supplies['turnback'][t] += turnback_deliveries + carryover_deliveries + contract_deliveries
    self.daily_supplies['flood'][t] += flood_deliveries + turnback_deliveries + carryover_deliveries + contract_deliveries
    if m == 9 and da == 30:
      self.annual_supplies['contract'][wateryear] += max(deliveries - max(carryover, 0.0) - max(turnback, 0.0), 0.0)
      self.annual_supplies['carryover'][wateryear] += max(min(carryover, deliveries), 0.0)
      self.annual_supplies['turnback'][wateryear] += max(min(turnback, deliveries - carryover), 0.0)
      self.annual_supplies['flood'][wateryear] += flood
	  
  def accounting_as_df(self, index):
    df = pd.DataFrame()
    for n in self.daily_supplies:    
      df['%s_%s' % (self.key,n)] = pd.Series(self.daily_supplies[n], index = index)
    return df
	
  def annual_results_as_df(self):
    df = pd.DataFrame()
    for n in self.annual_supplies:
      df['%s_%s' % (self.key,n)] = pd.Series(self.annual_supplies[n])
    return df



