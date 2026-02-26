import csv
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

## import dataset

data = pd.read_csv('data.csv')
## explore dataset: data types, shape

print(data.head())
data.info()
print(data.shape)
print(data.describe())
# print out the unique values of the Flag column
print(data.nunique())
## validate dataset: NAs, correct data types

# count NAs
data.isnull().sum()


##- --> there are only a few columns with more than one unique values: Area Code (M49), Area Code, Element Code, Element, Year Code, Year, Value
