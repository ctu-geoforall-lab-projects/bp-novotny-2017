import csv

class ReadCSV():
    def __init__(self):
        self._data = []
        
    def read(self, csv_file):
        """Read CSV file into table
        """
        with open(csv_file, 'rb') as f:
            # assuming that first line contains column names
            self._data = csv.reader(f)
            dic_name = dict((row[0], row[1]) for row in self._data)
            return dic_name
        
    def value(self, dictionary, key):
        """Get value from table.

        :param dictionary: dictionary name
        :param key: row of key
        """
        value = dictionary.get(key)
        return value
