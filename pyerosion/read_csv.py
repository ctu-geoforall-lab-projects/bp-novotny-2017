import csv

class ReadCSV():
    def __init__(self):
        self._data = []
        
    def read(self, csv_file):
        """Read CSV file info table
        """
        with open(csv_file, 'rb') as f:
            # assuming that first line contains column names
            self._data = csv.reader(f)

    def value(self, key, value):
        """Get value from table.

        :param key: column name used as key
        :param value: column name used as value
        """        
        pass
